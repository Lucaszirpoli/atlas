"""Aba OBJETIVO (Premium) — a casa do questionário e das versões do plano.

Spec §3, §4 e §12. A aba deixa de ser "uma área simples de meta" e passa a
concentrar: apresentação e questionário no primeiro acesso, painel-resumo
depois, visualização e edição das respostas, alterações pendentes, atualização
do plano e histórico das versões.

Tudo aqui é Premium. O plano Free continua sem esta aba e sem estes endpoints —
ele preenche manualmente o que já preenchia (regra de escopo §2).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.coaching import plan_service, questionnaire
from app.core.db import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.objective import (
    ObjectiveState,
    PlanSummary,
    QuestionnaireDraftUpdate,
    QuestionnaireSchema,
)

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

    respostas_ativas = dict(ativo.answers or {}) if ativo else {}
    # Sem rascunho e sem plano: começa do que o app já sabe (perfil), pra
    # ninguém redigitar altura, idade e objetivo.
    if draft is not None:
        rascunho = dict(draft.answers or {})
    elif ativo is not None:
        rascunho = dict(respostas_ativas)
    else:
        rascunho = plan_service.answers_from_profile(db, current_user)

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
