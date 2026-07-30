"""Geração e ATIVAÇÃO ATÔMICA do plano do Coaching (spec §4, §12).

A regra que este módulo existe pra garantir:

    O novo plano só se torna ativo quando treino, metas nutricionais, dieta em
    PDF, periodização e análise tiverem sido gerados com sucesso.

Antes, cada peça se aplicava por conta própria. Dava pra sair de uma
atualização com o treino novo e a meta antiga — cada aba mostrando uma versão
diferente da verdade, e ninguém sabendo qual valia. Aqui é tudo-ou-nada: falhou
no meio, o plano anterior continua exatamente como estava e as respostas ativas
não são tocadas.

O outro princípio é ATUALIZAÇÃO CONSERVADORA (§12): comparar as respostas
antigas com as novas e mexer só no que foi impactado. Se mudou só o horário,
não refaz a divisão do treino; se mudou uma restrição alimentar, ajusta os
alimentos, não as metas.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coaching import questionnaire, training_brain, workout_builder
from app.models.calorie_goal import CalorieGoal, GoalMode

# Densidade energética de cada macro — igual à conversão usada na tela antiga
# de meta manual (agora só no questionário).
_KCAL_PER_G = {"protein": 4, "carbs": 4, "fat": 9}
from app.models.coaching_plan import CoachingPlan, PlanStatus, QuestionnaireDraft
from app.models.user import User
from app.models.user_profile import (
    ActivityLevel,
    BiologicalSex,
    ExperienceLevel,
    Goal,
    GoalPace,
    TrainingLocation,
    UserProfile,
)
from app.models.weight_log import WeightLog
from app.services.nutrition_calc import compute_auto_goal

# Que componentes cada resposta impacta. É o coração da atualização
# conservadora: mudar o horário do treino não pode refazer a dieta.
_IMPACTO: dict[str, tuple[str, ...]] = {
    # Objetivo e corpo mexem em tudo.
    "goal": ("treino", "metas", "dieta", "periodizacao", "analise"),
    "goal_pace": ("metas", "dieta"),
    "biological_sex": ("metas", "dieta"),
    "age": ("metas", "dieta"),
    "height_cm": ("metas", "dieta"),
    "weight_kg": ("metas", "dieta"),
    "target_weight_kg": ("metas",),
    "activity_level": ("metas", "dieta"),
    "calorie_goal_mode": ("metas", "dieta"),
    "manual_kcal": ("metas", "dieta"),
    "manual_pct_protein": ("metas", "dieta"),
    "manual_pct_carbs": ("metas", "dieta"),
    "manual_pct_fat": ("metas", "dieta"),
    # Treino.
    "experience_level": ("treino", "periodizacao"),
    "training_location": ("treino",),
    "training_history": (),
    "training_days_per_week": ("treino",),
    "available_days": (),  # só o horário: não refaz divisão nenhuma
    "session_length": ("treino",),
    "weak_points": ("treino",),
    "strong_points": ("treino",),
    "injuries_limitations": ("treino",),
    "exercise_preferences": ("treino",),
    "exercise_prefs": ("treino",),
    # Alimentação.
    "dietary_restrictions": ("dieta",),
    "meals_per_day": ("dieta",),
    "food_dislikes": ("dieta",),
    # Recuperação.
    "sleep_hours": ("analise",),
    "wants_cardio": ("treino",),
    "allow_advanced_techniques": ("treino",),
    "periodization": ("treino", "periodizacao"),
    "medications": ("analise",),
    "notes": ("analise",),
}

TODOS_COMPONENTES = ("treino", "metas", "dieta", "periodizacao", "analise")


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
def active_plan(db: Session, user_id: int) -> CoachingPlan | None:
    return db.execute(
        select(CoachingPlan)
        .where(CoachingPlan.user_id == user_id, CoachingPlan.status == PlanStatus.ACTIVE)
        .order_by(CoachingPlan.version.desc())
        .limit(1)
    ).scalar_one_or_none()


def plan_history(db: Session, user_id: int, limit: int = 20) -> list[CoachingPlan]:
    return list(
        db.execute(
            select(CoachingPlan)
            .where(CoachingPlan.user_id == user_id)
            .order_by(CoachingPlan.version.desc())
            .limit(limit)
        ).scalars()
    )


def get_draft(db: Session, user_id: int) -> QuestionnaireDraft | None:
    return db.execute(
        select(QuestionnaireDraft).where(QuestionnaireDraft.user_id == user_id)
    ).scalar_one_or_none()


def save_draft(db: Session, user_id: int, answers: dict, step: int) -> QuestionnaireDraft:
    """Salva o progresso a cada avanço/volta (spec §3.1). Não commita."""
    draft = get_draft(db, user_id)
    if draft is None:
        draft = QuestionnaireDraft(user_id=user_id, answers=answers, step=step)
        db.add(draft)
    else:
        draft.answers = answers
        draft.step = step
    return draft


def answers_from_profile(db: Session, user: User) -> dict[str, Any]:
    """Pré-preenche o questionário com o que o app JÁ sabe da pessoa (perfil +
    preferências de treino). Ninguém deveria redigitar altura e idade."""
    p: UserProfile | None = user.profile
    if p is None:
        return {}
    peso = db.execute(
        select(WeightLog.weight_kg)
        .where(WeightLog.user_id == user.id)
        .order_by(WeightLog.recorded_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    goal = db.execute(
        select(CalorieGoal)
        .where(CalorieGoal.user_id == user.id)
        .order_by(CalorieGoal.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    meta_atual = _goal_answers(goal)
    return {
        "goal": p.goal.value if p.goal else None,
        "goal_pace": p.goal_pace.value if p.goal_pace else None,
        "biological_sex": p.biological_sex.value if p.biological_sex else None,
        "age": p.age,
        "height_cm": p.height_cm,
        "weight_kg": peso,
        "target_weight_kg": p.target_weight_kg,
        "activity_level": p.activity_level.value if p.activity_level else None,
        "experience_level": p.experience_level.value if p.experience_level else None,
        "training_location": p.training_location.value if p.training_location else None,
        "training_days_per_week": str(p.training_days_per_week) if p.training_days_per_week else None,
        "available_days": list(p.available_days or []),
        "session_length": p.session_length,
        "weak_points": training_brain.resolve_weak_points(p),
        "dietary_restrictions": list(p.dietary_restrictions or []),
        "injuries_limitations": p.injuries_limitations,
        "wants_cardio": p.wants_cardio,
        "allow_advanced_techniques": p.allow_advanced_techniques,
        "periodization": p.periodization or "auto",
        **meta_atual,
    }


def _goal_answers(goal: CalorieGoal | None) -> dict[str, Any]:
    """Meta vigente convertida pros campos do questionário — pra editar a
    meta manual mostrar a divisão ATUAL (derivada dos gramas), não um padrão
    genérico. Mesmo arredondamento "a sobra vai pro maior macro" que a antiga
    tela de meta usava, pra não abrir já acusando '99%' numa meta que fecha."""
    if goal is None:
        return {"calorie_goal_mode": "auto"}
    modo = goal.mode.value if hasattr(goal.mode, "value") else str(goal.mode)
    if modo != "manual" or not goal.kcal:
        return {"calorie_goal_mode": modo}
    pct = lambda gramas, kcal_por_g: round((gramas * kcal_por_g) / goal.kcal * 100)  # noqa: E731
    vals = {
        "protein": pct(goal.protein_g, _KCAL_PER_G["protein"]),
        "carbs": pct(goal.carbs_g, _KCAL_PER_G["carbs"]),
        "fat": pct(goal.fat_g, _KCAL_PER_G["fat"]),
    }
    sobra = 100 - sum(vals.values())
    if sobra != 0 and abs(sobra) <= 2:
        maior = max(vals, key=vals.get)
        vals[maior] += sobra
    return {
        "calorie_goal_mode": "manual",
        "manual_kcal": round(goal.kcal),
        "manual_pct_protein": vals["protein"],
        "manual_pct_carbs": vals["carbs"],
        "manual_pct_fat": vals["fat"],
    }


# ---------------------------------------------------------------------------
# Diff conservador
# ---------------------------------------------------------------------------
def _igual(a: Any, b: Any) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return sorted(map(str, a or [])) == sorted(map(str, b or []))
    if a is None or b is None:
        return a is b or (a is None and b is None)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) < 1e-6
    return str(a) == str(b)


def diff_answers(antigas: dict, novas: dict) -> list[dict]:
    """O que mudou, campo a campo, com rótulo humano — vira o "resumo das
    mudanças" que a pessoa lê depois de atualizar (§3.6)."""
    mudancas: list[dict] = []
    for key in questionnaire.FIELD_LABELS:
        de, para = antigas.get(key), novas.get(key)
        if _igual(de, para):
            continue
        mudancas.append({
            "field": key,
            "label": questionnaire.FIELD_LABELS.get(key, key),
            "section": questionnaire.FIELD_STEP.get(key, ""),
            "from": de,
            "to": para,
        })
    return mudancas


def impacted_components(mudancas: list[dict]) -> list[str]:
    """Só os componentes que as mudanças realmente afetam (§12). Preservar o
    que continua adequado é metade do trabalho de um coach de verdade."""
    afetados: set[str] = set()
    for m in mudancas:
        afetados.update(_IMPACTO.get(m["field"], TODOS_COMPONENTES))
    return [c for c in TODOS_COMPONENTES if c in afetados]


# ---------------------------------------------------------------------------
# Aplicação das respostas no perfil
# ---------------------------------------------------------------------------
def _enum_or_none(enum_cls, value):
    try:
        return enum_cls(value) if value else None
    except ValueError:
        return None


def apply_answers_to_profile(db: Session, user: User, answers: dict) -> None:
    """Escreve as respostas nos campos que o resto do app já lê (perfil e
    preferências de treino). Não commita — quem chama controla a transação."""
    p = user.profile
    if p is None:
        raise ValueError("Complete seu cadastro antes de responder o questionário.")

    if (v := _enum_or_none(Goal, answers.get("goal"))) is not None:
        p.goal = v
    if (v := _enum_or_none(GoalPace, answers.get("goal_pace"))) is not None:
        p.goal_pace = v
    if (v := _enum_or_none(BiologicalSex, answers.get("biological_sex"))) is not None:
        p.biological_sex = v
    if (v := _enum_or_none(ActivityLevel, answers.get("activity_level"))) is not None:
        p.activity_level = v
    if (v := _enum_or_none(ExperienceLevel, answers.get("experience_level"))) is not None:
        p.experience_level = v
    if (v := _enum_or_none(TrainingLocation, answers.get("training_location"))) is not None:
        p.training_location = v

    for campo, chave in (("age", "age"), ("height_cm", "height_cm"), ("target_weight_kg", "target_weight_kg")):
        val = answers.get(chave)
        if val is not None:
            setattr(p, campo, val)

    p.training_days_per_week = training_brain.valid_training_days(
        int(answers["training_days_per_week"]) if str(answers.get("training_days_per_week") or "").isdigit() else None
    )
    p.session_length = training_brain.valid_session_length(answers.get("session_length"))
    p.weak_points = training_brain.valid_weak_points(answers.get("weak_points"))
    p.periodization = training_brain.valid_periodization(answers.get("periodization"))
    if answers.get("wants_cardio") is not None:
        p.wants_cardio = bool(answers["wants_cardio"])
    # None é resposta VÁLIDA aqui (= "não escolheu"), e nesse caso vale o padrão
    # por nível de training_brain.advanced_allowed: iniciante não recebe técnica
    # avançada, os demais recebem. Por isso o `is not None` — sem ele, quem
    # deixasse a pergunta em branco zeraria a escolha anterior.
    if answers.get("allow_advanced_techniques") is not None:
        p.allow_advanced_techniques = bool(answers["allow_advanced_techniques"])
    if answers.get("available_days") is not None:
        p.available_days = list(answers["available_days"] or [])
    if answers.get("dietary_restrictions") is not None:
        p.dietary_restrictions = list(answers["dietary_restrictions"] or [])
    if answers.get("injuries_limitations") is not None:
        p.injuries_limitations = answers["injuries_limitations"] or None

    # Respostas que ANTES eram descartadas. Elas constavam do mapa de impacto
    # (mudá-las remontava o plano), mas nada as gravava — quem respondia
    # "prefiro máquinas e exercícios estáveis" via o coach montar agachamento
    # livre do mesmo jeito. exercise_prefs muda a escolha de exercícios de
    # verdade; os textos entram no contexto do coach de IA.
    if answers.get("exercise_prefs") is not None:
        p.exercise_prefs = training_brain.valid_exercise_prefs(answers.get("exercise_prefs"))
    if answers.get("strong_points") is not None:
        p.strong_points = training_brain.valid_weak_points(answers.get("strong_points"))
    for campo, chave in (
        ("exercise_preferences_text", "exercise_preferences"),
        ("training_history", "training_history"),
        ("food_dislikes", "food_dislikes"),
        ("medications", "medications"),
        ("extra_notes", "notes"),
    ):
        if answers.get(chave) is not None:
            setattr(p, campo, (answers.get(chave) or "").strip() or None)

    # Peso é histórico append-only: um valor novo vira um registro novo, nunca
    # sobrescreve o anterior (regra 4 — é a base dos gráficos de evolução).
    peso = answers.get("weight_kg")
    if peso:
        ultimo = db.execute(
            select(WeightLog.weight_kg)
            .where(WeightLog.user_id == user.id)
            .order_by(WeightLog.recorded_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if ultimo is None or abs(float(ultimo) - float(peso)) >= 0.05:
            db.add(WeightLog(user_id=user.id, weight_kg=float(peso),
                             recorded_at=datetime.now(timezone.utc)))
    db.add(p)


def _rebuild_goals(db: Session, user: User, answers: dict[str, Any]) -> int:
    """Recalcula e aplica as metas de calorias/macros. Devolve o id da meta.

    A escolha auto/manual agora mora no questionário (ajuste pós-v36, item 1) —
    não existe mais uma tela separada de "ajustar meta calórica"."""
    if answers.get("calorie_goal_mode") == "manual":
        erro = questionnaire.macro_split_error(answers)
        if erro:
            raise ValueError(erro)
        kcal = float(answers["manual_kcal"])
        pp = float(answers["manual_pct_protein"])
        pc = float(answers["manual_pct_carbs"])
        pf = float(answers["manual_pct_fat"])
        goal = CalorieGoal(
            user_id=user.id, mode=GoalMode.MANUAL, kcal=kcal,
            protein_g=round(kcal * pp / 100 / _KCAL_PER_G["protein"]),
            carbs_g=round(kcal * pc / 100 / _KCAL_PER_G["carbs"]),
            fat_g=round(kcal * pf / 100 / _KCAL_PER_G["fat"]),
        )
        db.add(goal)
        db.flush()
        return goal.id

    p = user.profile
    peso = db.execute(
        select(WeightLog.weight_kg)
        .where(WeightLog.user_id == user.id)
        .order_by(WeightLog.recorded_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if peso is None:
        raise ValueError("Preciso do seu peso pra calcular as metas.")
    auto = compute_auto_goal(
        biological_sex=p.biological_sex, weight_kg=float(peso), height_cm=p.height_cm,
        age=p.age, activity_level=p.activity_level, goal=p.goal,
    )
    goal = CalorieGoal(
        user_id=user.id, mode=GoalMode.AUTO, kcal=auto["kcal"],
        protein_g=auto["protein_g"], carbs_g=auto["carbs_g"], fat_g=auto["fat_g"],
    )
    db.add(goal)
    db.flush()
    return goal.id


# ---------------------------------------------------------------------------
# Ativação atômica
# ---------------------------------------------------------------------------
def activate(db: Session, user: User, answers: dict, *, reason: str = "atualizacao") -> CoachingPlan:
    """Gera TODOS os componentes e só então ativa o plano novo (§4, §12).

    Se qualquer componente falhar, nada é ativado: o plano nasce FAILED, a
    transação volta atrás e o plano anterior — junto das respostas ativas —
    continua intacto. Erro aqui não pode deixar a pessoa com meia verdade.
    """
    faltando = questionnaire.missing_required(answers)
    if faltando:
        rotulos = ", ".join(questionnaire.FIELD_LABELS.get(k, k) for k in faltando)
        raise ValueError(f"Faltam informações essenciais: {rotulos}.")
    erro_macros = questionnaire.macro_split_error(answers)
    if erro_macros:
        raise ValueError(erro_macros)

    anterior = active_plan(db, user.id)
    respostas_antigas = dict(anterior.answers or {}) if anterior else {}
    mudancas = diff_answers(respostas_antigas, answers) if anterior else []
    componentes_alvo = impacted_components(mudancas) if anterior else list(TODOS_COMPONENTES)
    proxima_versao = (anterior.version + 1) if anterior else 1

    # O plano descreve o ESTADO ATIVO inteiro, não só o delta: o que não foi
    # regerado é herdado da versão anterior. Sem isso, uma atualização que só
    # mexe na dieta apagaria o treino do resumo — a pessoa abriria a aba
    # Objetivo e não veria mais o treino que continua valendo.
    componentes: dict[str, Any] = dict(anterior.components or {}) if anterior else {}
    try:
        # 1) Respostas -> perfil. Ainda dentro da transação: se algo abaixo
        #    falhar, o rollback desfaz isto também.
        apply_answers_to_profile(db, user, answers)
        db.flush()

        # 2) Metas nutricionais (base da dieta em PDF e dos gráficos da aba Dieta).
        if "metas" in componentes_alvo:
            componentes["calorie_goal_id"] = _rebuild_goals(db, user, answers)

        # 3) Treino. Reaproveita o montador existente — não recria a
        #    inteligência do coach, só a chama na hora certa.
        if "treino" in componentes_alvo:
            resultado = workout_builder.build_and_save(db, user)
            componentes["workout"] = {
                "method_name": resultado["method_name"],
                "days": resultado["days"],
                "total_exercises": resultado["total_exercises"],
                "routines": resultado["routines"],
            }

        # 4) Periodização + dieta em PDF + análise não geram artefato próprio
        #    aqui: são derivados (a periodização vem do perfil, o PDF é montado
        #    sob demanda a partir das metas, a análise é recalculada a cada
        #    leitura). O que importa registrar é que a base deles ficou pronta.
        componentes["periodizacao"] = training_brain.valid_periodization(user.profile.periodization)
        componentes["dieta_pdf"] = "metas" in componentes_alvo or anterior is None
        componentes["gerados"] = componentes_alvo

        plano = CoachingPlan(
            user_id=user.id, version=proxima_versao, status=PlanStatus.ACTIVE,
            answers=answers, changes=mudancas, components=componentes, reason=reason,
            activated_at=datetime.now(timezone.utc),
        )
        db.add(plano)

        # 5) Só AGORA o anterior sai de cena — depois de tudo ter dado certo.
        if anterior is not None:
            anterior.status = PlanStatus.ARCHIVED
            anterior.archived_at = datetime.now(timezone.utc)

        # 6) O rascunho vira as respostas ativas: não há mais pendência.
        draft = get_draft(db, user.id)
        if draft is not None:
            draft.answers = answers
            draft.completed = True
            draft.step = 0

        db.commit()
        db.refresh(plano)
        return plano

    except Exception as exc:
        db.rollback()
        # Registra a falha pra auditoria, em transação separada — o plano
        # anterior continua ACTIVE e as respostas ativas, intocadas.
        falho = CoachingPlan(
            user_id=user.id, version=proxima_versao, status=PlanStatus.FAILED,
            answers=answers, changes=[], components={}, reason=reason, error=str(exc)[:2000],
        )
        db.add(falho)
        db.commit()
        raise
