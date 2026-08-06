"""Aba OBJETIVO (Premium) — a casa do questionário e das versões do plano.

Spec §3, §4 e §12. A aba deixa de ser "uma área simples de meta" e passa a
concentrar: apresentação e questionário no primeiro acesso, painel-resumo
depois, visualização e edição das respostas, alterações pendentes, atualização
do plano e histórico das versões.

Tudo aqui é Premium. O plano Free continua sem esta aba e sem estes endpoints —
ele preenche manualmente o que já preenchia (regra de escopo §2).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.diet_engine import build_diet_plan
from app.coaching import plan_service, questionnaire
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.user_profile import Goal
from app.schemas.meal import MealLogCreate, MealLogItemCreate
from app.schemas.objective import (
    GoalChangeRequest,
    GoalChangeResult,
    ObjectiveState,
    PlanSummary,
    QuestionnaireDraftUpdate,
    QuestionnaireSchema,
)
from app.services import goal_service, meal_service

router = APIRouter(prefix="/objective", tags=["objective"])


def _require_pro(user: User) -> None:
    if getattr(user, "plan", None) != "pro":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="A aba Objetivo faz parte do Coaching, exclusivo do plano Pro.",
        )


def _plan_summary(p) -> PlanSummary:
    return PlanSummary(
        id=p.id,
        version=p.version,
        status=p.status.value,
        reason=p.reason,
        changes=p.changes or [],
        components=p.components or {},
        created_at=p.created_at,
        activated_at=p.activated_at,
        archived_at=p.archived_at,
        error=p.error,
    )


@router.get("/questionnaire", response_model=QuestionnaireSchema)
def get_questionnaire(current_user: User = Depends(get_current_user)) -> QuestionnaireSchema:
    """A estrutura das 6 etapas. O app desenha a tela a partir daqui, então
    mudar uma pergunta é mudar um lugar só."""
    _require_pro(current_user)
    return QuestionnaireSchema(steps=questionnaire.steps(), required=questionnaire.required_keys())


@router.get("", response_model=ObjectiveState)
def get_state(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ObjectiveState:
    """O estado inteiro da aba, numa chamada — é o que decide QUAL tela mostrar:

    - sem plano ativo  -> apresentação + questionário obrigatório (§3.1)
    - com plano ativo  -> painel-resumo (§3.3)
    - com pendências   -> painel-resumo + aviso de alterações pendentes (§3.5)
    """
    _require_pro(current_user)
    ativo = plan_service.active_plan(db, current_user.id)
    draft = plan_service.get_draft(db, current_user.id)

    # Tanto o rascunho quanto as respostas do plano ativo nascem do que o app já
    # sabe (perfil) e só então recebem por cima o que estiver salvo. Ninguém
    # redigita altura, idade e objetivo.
    #
    # O merge existe por causa do questionário novo: quem já tinha plano ativo
    # respondeu perguntas que não existem mais (o ponto fraco era uma lista sem
    # ordem, o nível era auto-avaliado) e não respondeu as que existem agora.
    # Sem a base do perfil, essa pessoa abriria a tela com os campos novos em
    # branco e travada num obrigatório, mesmo tendo a informação guardada.
    #
    # E a base precisa entrar DOS DOIS LADOS. Só no rascunho, o diff acusaria
    # como "alteração pendente" cada campo novo que a pessoa não mexeu — ela
    # abriria a aba com um aviso de mudanças que não fez. Os dois lados partindo
    # da mesma base, o diff volta a mostrar só o que ela mudou de verdade.
    base_perfil = plan_service.answers_from_profile(db, current_user)
    respostas_ativas = {**base_perfil, **dict(ativo.answers or {})} if ativo else {}
    rascunho = dict(base_perfil)
    if draft is not None:
        rascunho.update(dict(draft.answers or {}))
    elif ativo is not None:
        rascunho.update(respostas_ativas)

    pendentes = plan_service.diff_answers(respostas_ativas, rascunho) if ativo else []

    return ObjectiveState(
        has_plan=ativo is not None,
        active_plan=_plan_summary(ativo) if ativo else None,
        active_answers=respostas_ativas,
        draft_answers=rascunho,
        draft_step=draft.step if draft else 0,
        pending_changes=pendentes,
        impacted_components=plan_service.impacted_components(pendentes) if pendentes else [],
        missing_required=questionnaire.missing_required(rascunho),
        history=[_plan_summary(p) for p in plan_service.plan_history(db, current_user.id)],
        history_total=plan_service.plan_history_total(db, current_user.id),
    )


@router.put("/draft", response_model=ObjectiveState)
def save_draft(
    payload: QuestionnaireDraftUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ObjectiveState:
    """Salva o progresso ao avançar, voltar, minimizar ou fechar o app (§3.1).
    NÃO substitui as respostas ativas — elas só mudam na ativação (§3.5)."""
    _require_pro(current_user)
    plan_service.save_draft(db, current_user.id, payload.answers, payload.step)
    db.commit()
    return get_state(current_user, db)


@router.post("/draft/discard", response_model=ObjectiveState)
def discard_draft(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ObjectiveState:
    """"Descartar alterações": o rascunho volta a ser igual às respostas ativas.
    Só faz sentido com plano ativo — sem plano não há o que descartar pra."""
    _require_pro(current_user)
    ativo = plan_service.active_plan(db, current_user.id)
    if ativo is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você ainda não tem um plano — não há alterações a descartar.",
        )
    plan_service.save_draft(db, current_user.id, dict(ativo.answers or {}), 0)
    db.commit()
    return get_state(current_user, db)


@router.post("/activate", response_model=ObjectiveState)
def activate_plan(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ObjectiveState:
    """"Finalizar e gerar meu plano" / "Atualizar meu plano".

    Gera treino, metas, dieta em PDF, periodização e análise e só então ativa —
    tudo ou nada (§4). Em caso de erro, o plano atual e as respostas ativas
    ficam intactos e a pessoa pode tentar de novo.
    """
    _require_pro(current_user)
    draft = plan_service.get_draft(db, current_user.id)
    ativo = plan_service.active_plan(db, current_user.id)
    respostas = dict(draft.answers or {}) if draft else dict(ativo.answers or {}) if ativo else {}

    # Nada mudou: não faz sentido arquivar o plano atual pra criar um idêntico.
    # Versão sem mudança nenhuma só polui o histórico e faz a pessoa achar que
    # algo foi refeito quando não foi.
    if ativo is not None and not plan_service.diff_answers(dict(ativo.answers or {}), respostas):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Suas respostas estão iguais às que já estão valendo — não há o que atualizar.",
        )

    try:
        plan_service.activate(
            db, current_user, respostas, reason="primeiro_plano" if ativo is None else "atualizacao"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não consegui gerar seu plano completo agora, então não mudei nada — "
                "seu plano atual continua valendo. Pode tentar de novo."
            ),
        ) from exc
    return get_state(current_user, db)


@router.post("/goal", response_model=GoalChangeResult)
def change_goal(
    payload: GoalChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GoalChangeResult:
    """"Alterar meu objetivo" — troca SÓ o objetivo, sem refazer o questionário.

    Trocar de objetivo é a mudança mais comum e mais pesada que existe aqui:
    mexe no treino, nas metas, na dieta e na periodização. Antes, pra mudar
    "hipertrofia" pra "emagrecimento" a pessoa tinha que reabrir as 8 etapas e
    passar por todas de novo — e o caminho estava lá, então ela mexia em outras
    respostas sem querer.

    A meta de calorias NÃO vira a chave de uma vez: quando o alvo do objetivo
    novo está longe do que ela come hoje, `plan_service` aplica um degrau e abre
    a transição (ver `goal_service.stage_auto_goal`). O resto do plano — treino,
    dieta, periodização — é regerado inteiro, porque isso não tem meio-termo.
    """
    _require_pro(current_user)
    validos = {g.value for g in Goal}
    if payload.goal not in validos:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Objetivo inválido. Escolha um entre: {', '.join(sorted(validos))}.",
        )
    ativo = plan_service.active_plan(db, current_user.id)
    if ativo is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você ainda não tem um plano — responda o questionário primeiro.",
        )

    base = {**plan_service.answers_from_profile(db, current_user), **dict(ativo.answers or {})}
    if base.get("goal") == payload.goal:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse já é o seu objetivo atual.",
        )

    # Consentimento de dado de saúde é dado UMA VEZ, no questionário, e é
    # inegociável (LGPD). Quem tem plano de antes dessa etapa existir não tem o
    # aceite guardado — e este atalho não pode "assumir" a autorização por ela.
    # A mensagem diz onde resolver, em vez de repetir o erro genérico da
    # geração, que aqui pareceria um bug do botão.
    if questionnaire.consent_error(base):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Antes de trocar o objetivo eu preciso da sua autorização pra usar dados de saúde — "
                "ela é dada uma vez, na última etapa do questionário. Toque em 'Alterar respostas', "
                "vá até o fim e confirme; depois este botão funciona direto."
            ),
        )

    # Edição pendente do questionário não pode ser engolida pela troca: a
    # ativação transforma o rascunho nas respostas ativas, então guardo o que
    # estava pendente e devolvo depois, já com o objetivo novo por cima.
    draft = plan_service.get_draft(db, current_user.id)
    pendente = dict(draft.answers or {}) if draft else {}
    tinha_pendencia = bool(pendente) and bool(plan_service.diff_answers(base, pendente))

    antes = goal_service.get_current_goal(db, current_user.id)
    kcal_antes = round(antes.kcal) if antes else None

    try:
        plan_service.activate(
            db, current_user, {**base, "goal": payload.goal}, reason="troca_objetivo"
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não consegui montar seu plano com o objetivo novo agora, então não mudei nada — "
                "seu objetivo e seu plano atuais continuam valendo. Pode tentar de novo."
            ),
        ) from exc

    if tinha_pendencia:
        plan_service.save_draft(db, current_user.id, {**pendente, "goal": payload.goal}, 0)
        db.commit()

    agora = goal_service.get_current_goal(db, current_user.id)
    transicao = goal_service.active_transition(db, current_user.id)
    kcal_agora = round(agora.kcal) if agora else (kcal_antes or 0)
    alvo = round(transicao.target_kcal) if transicao is not None else kcal_agora
    return GoalChangeResult(
        state=get_state(current_user, db),
        goal_label=questionnaire.GOAL_LABELS.get(payload.goal, payload.goal),
        kcal_antes=kcal_antes,
        kcal_agora=kcal_agora,
        kcal_alvo=alvo,
        em_transicao=transicao is not None,
    )


def _build_personal_diet(current_user: User, db: Session):
    """A dieta que o Coaching monta PRA ESSA PESSOA: meta de macros da meta
    vigente + restrições/refeições do questionário ativo — nunca as dietas
    prontas genéricas (essas continuam só na aba Dieta). Ajuste pós-v36."""
    plano = plan_service.active_plan(db, current_user.id)
    if plano is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Você ainda não tem um plano — responda o questionário primeiro.",
        )
    target = goal_service.resolve_macro_target(db, current_user)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preciso da sua meta de calorias pra montar sua dieta.",
        )
    respostas = plano.answers or {}
    # As DUAS listas do questionário: restrições alimentares e "alimentos que
    # você não come". Só a primeira chegava aqui — era por isso que marcar
    # "sem whey protein" não impedia o whey de aparecer no cardápio.
    restricoes = [
        str(x)
        for chave in ("dietary_restrictions", "food_dislikes_list")
        for x in (respostas.get(chave) or [])
    ]
    try:
        refeicoes = int(respostas.get("meals_per_day") or 4)
    except (TypeError, ValueError):
        refeicoes = 4
    return build_diet_plan(db, target, restricoes, meals_per_day=refeicoes)


@router.get("/diet")
def get_personal_diet(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """A dieta personalizada da aba Objetivo — montada a partir da meta e do
    questionário, não uma dieta pronta. Só consulta, não registra nada."""
    _require_pro(current_user)
    plan = _build_personal_diet(current_user, db)
    d = plan.to_dict()
    return {
        "name": "Minha dieta",
        "tagline": "Montada pelo Coaching com base no seu questionário",
        "meals": d["meals"],
        "totals": d["totals"],
        # Etiquetas humanas: a tela mostrava o token cru ("sem_lactose",
        # "whey"), que é linguagem de banco de dados, não do usuário.
        "restrictions": questionnaire.food_token_labels(d["restrictions"]),
        "not_applied": questionnaire.food_token_labels(d["not_applied"]),
    }


@router.post("/diet/apply")
def apply_personal_diet(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    """Registra a dieta personalizada no diário de HOJE — mesmo padrão de
    /diet-templates/{id}/apply, mas a partir do plano montado pra ESSA
    pessoa, não de um molde genérico."""
    _require_pro(current_user)
    plan = _build_personal_diet(current_user, db)
    d = plan.to_dict()
    categories = {c.name: c for c in meal_service.ensure_default_categories(db, current_user.id)}
    db.flush()

    logged_meals = 0
    logged_items = 0
    now = datetime.now(timezone.utc)
    for meal in d["meals"]:
        cat = categories.get(meal["category"])
        if cat is None or not meal["items"]:
            continue
        meal_service.log_meal(
            db,
            current_user.id,
            MealLogCreate(
                meal_category_id=cat.id,
                logged_at=now,
                items=[MealLogItemCreate(food_id=i["food_id"], quantity_g=i["quantity_g"]) for i in meal["items"]],
            ),
        )
        logged_meals += 1
        logged_items += len(meal["items"])
    db.commit()

    return {
        "template_name": "Minha dieta",
        "meals_logged": logged_meals,
        "items_logged": logged_items,
        "totals": d["totals"],
    }
