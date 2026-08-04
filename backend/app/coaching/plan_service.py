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
    TrainingStylePreference,
    UserProfile,
)
from app.models.weight_log import WeightLog
from app.services.nutrition_calc import calculate_bmr, calculate_tdee, compute_auto_goal

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
    # Experiência. `training_time` substituiu a auto-avaliação de nível, e é dele
    # que o experience_level passa a sair — por isso herdou o mesmo impacto.
    "training_time": ("treino", "periodizacao"),
    "rir_accuracy": ("treino",),
    "failure_comfort": ("treino",),
    "load_preference": ("treino",),
    # Onde e quando.
    "training_location": ("treino",),
    "home_equipment": ("treino",),
    "training_days_per_week": ("treino",),
    "session_length": ("treino",),
    # Divisão preferida: desde que `methods.coach_split_for` passou a lê-la, ela
    # decide qual blueprint cai em cada dia. Sem esta linha o diff não marcaria
    # "treino" como impactado e a mudança viraria plano novo com treino velho.
    "split_preference": ("treino",),
    # Saúde: tira exercício do plano, então refaz o treino.
    "has_injury": ("treino",),
    "injury_regions": ("treino",),
    "medical_clearance": ("treino",),
    "has_pain": ("treino",),
    "pain_regions": ("treino",),
    "pain_intensity": ("treino",),
    "limitations": ("treino",),
    "exercise_prefs": ("treino",),
    # Prioridades.
    "priority_1": ("treino",),
    "priority_2": ("treino",),
    "priority_3": ("treino",),
    "strong_points": ("treino",),
    "allow_advanced_techniques": ("treino",),
    "known_techniques": ("treino",),
    "periodization": ("treino", "periodizacao"),
    # Recuperação. As quatro viram o fator que desloca o VOLUME semanal
    # (training_brain.recovery_factor), então mexem no treino — não só na
    # análise, como era quando ninguém as lia.
    "sleep_quality": ("treino", "analise"),
    "stress_level": ("treino", "analise"),
    "recovery_between": ("treino", "analise"),
    "other_sport": ("treino", "analise"),
    "wants_cardio": ("treino",),
    # Alimentação.
    "dietary_restrictions": ("dieta",),
    "meals_per_day": ("dieta",),
    "food_dislikes_list": ("dieta",),
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


def plan_history_total(db: Session, user_id: int) -> int:
    """Quantas versões de plano a pessoa tem AO TODO — o número que a tela
    mostra. `plan_history` devolve só as mais recentes (teto de `limit`), e
    contar o tamanho daquela lista congelava o total no teto."""
    from sqlalchemy import func

    return int(
        db.execute(
            select(func.count(CoachingPlan.id)).where(CoachingPlan.user_id == user_id)
        ).scalar_one()
    )


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
        # Sem perfil ainda (o questionário é o cadastro — ver
        # apply_answers_to_profile). Mesmo assim o nome da conta já vai
        # preenchido: é a única resposta que o app JÁ sabe nesse momento, e
        # devolver {} fazia a pessoa redigitar o próprio nome na primeira tela.
        return {"display_name": user.display_name}
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
        # Vem preenchido com o nome da conta — a pessoa só ajusta se quiser ser
        # chamada de outro jeito pelo coach.
        "display_name": user.display_name,
        "goal": p.goal.value if p.goal else None,
        "goal_pace": p.goal_pace.value if p.goal_pace else None,
        "biological_sex": p.biological_sex.value if p.biological_sex else None,
        "age": p.age,
        "height_cm": p.height_cm,
        "weight_kg": peso,
        "target_weight_kg": p.target_weight_kg,
        "activity_level": p.activity_level.value if p.activity_level else None,
        "training_location": p.training_location.value if p.training_location else None,
        "training_days_per_week": str(p.training_days_per_week) if p.training_days_per_week else None,
        "session_length": p.session_length,
        "dietary_restrictions": list(p.dietary_restrictions or []),
        "wants_cardio": p.wants_cardio,
        "allow_advanced_techniques": p.allow_advanced_techniques,
        "periodization": p.periodization or "auto",
        # A fila de prioridade sai da lista ordenada do perfil e volta pros três
        # campos da tela.
        **questionnaire.priorities_to_answers(training_brain.resolve_weak_points(p)),
        "strong_points": list(p.strong_points or []),
        "exercise_prefs": list(p.exercise_prefs or []),
        # Respostas estruturadas do questionário novo. `training_time` é
        # obrigatório e não existia antes: pra quem já usava o app, ele nasce do
        # nível que a auto-avaliação antiga tinha gravado, senão a pessoa ficaria
        # travada fora do próprio plano até responder tudo de novo.
        "training_time": p.training_time
        or training_brain.training_time_from_experience(
            p.experience_level.value if p.experience_level else None
        ),
        "rir_accuracy": p.rir_accuracy,
        "failure_comfort": p.failure_comfort,
        "load_preference": p.load_preference,
        "home_equipment": list(p.home_equipment or []),
        "gym_crowding": p.gym_crowding,
        "split_preference": p.split_preference,
        "avoid_mixing_upper_lower": p.avoid_mixing_upper_lower,
        "has_injury": p.has_injury,
        "injury_regions": list(p.injury_regions or []),
        "medical_clearance": p.medical_clearance,
        "has_pain": p.has_pain,
        "pain_regions": list(p.pain_regions or []),
        "pain_intensity": p.pain_intensity,
        "limitations": list(p.limitations or []),
        "known_techniques": list(p.known_techniques or []),
        "sleep_quality": p.sleep_quality,
        "stress_level": p.stress_level,
        "recovery_between": p.recovery_between,
        "other_sport": p.other_sport,
        "food_dislikes_list": list(p.food_dislikes_list or []),
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


# Campos que o questionário ATUAL usa pra decidir o treino. Um plano salvo que
# não conhece nenhum deles veio de um questionário anterior — ver `activate`.
#
# São chaves que só existem no esquema novo (não é o caso de "a pessoa deixou em
# branco": elas nem eram perguntadas antes), então a ausência de TODAS é o sinal
# de esquema defasado. Basta uma presente pra o plano ser considerado atual.
_CHAVES_DO_ESQUEMA_ATUAL = ("priority_1", "training_time", "has_injury")


def _de_esquema_antigo(respostas: dict) -> bool:
    """True quando as respostas salvas não conhecem nenhum campo do
    questionário atual — ou seja, vieram de uma versão anterior dele."""
    return not any(k in respostas for k in _CHAVES_DO_ESQUEMA_ATUAL)


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
        # O QUESTIONÁRIO É O CADASTRO. Antes isto era um erro ("complete seu
        # cadastro antes"), o que só fazia sentido quando todo mundo passava por
        # um onboarding obrigatório ao criar a conta. Agora criar conta não pede
        # nada: quem assina o Pro chega aqui SEM perfil, e é este questionário
        # que o cria. Os campos obrigatórios dele (sexo, idade, altura, peso,
        # atividade, objetivo) são exatamente os que o perfil precisa, e
        # `missing_required` já barrou a ativação se algum faltasse.
        # As colunas NOT NULL nascem com um padrão seguro ANTES das respostas
        # entrarem por cima. Sem isto, uma resposta ausente ou fora do
        # vocabulário (ex.: `training_time` que não casa com nenhuma opção, e aí
        # `experience_level` nunca é derivado) estourava NOT NULL no INSERT e a
        # pessoa via só "não consegui gerar seu plano agora" — um formulário
        # inteiro respondido e nenhuma pista do que faltava.
        p = UserProfile(
            user_id=user.id,
            biological_sex=BiologicalSex.MALE,
            age=30,
            height_cm=170.0,
            activity_level=ActivityLevel.MODERATE,
            goal=Goal.MANUTENCAO,
            experience_level=ExperienceLevel.INICIANTE,
            training_location=TrainingLocation.ACADEMIA_COMPLETA,
            training_style_preference=TrainingStylePreference.IA_DECIDE,
        )
        db.add(p)
        user.profile = p

    # O nome pelo qual a pessoa quer ser chamada mora no USUÁRIO (é o mesmo
    # display_name que aparece no app inteiro), não no perfil — por isso é
    # gravado aqui e não no bloco do UserProfile abaixo.
    if (nome := (answers.get("display_name") or "").strip()):
        user.display_name = nome[:40]
        db.add(user)

    if (v := _enum_or_none(Goal, answers.get("goal"))) is not None:
        p.goal = v
    if (v := _enum_or_none(GoalPace, answers.get("goal_pace"))) is not None:
        p.goal_pace = v
    if (v := _enum_or_none(BiologicalSex, answers.get("biological_sex"))) is not None:
        p.biological_sex = v
    if (v := _enum_or_none(ActivityLevel, answers.get("activity_level"))) is not None:
        p.activity_level = v
    # O nível de experiência não é mais perguntado — ele é DERIVADO do tempo de
    # treino consistente. Auto-avaliação é sistematicamente inflada, e o nível
    # vale 15% do volume semanal (volume_landmarks._LEVEL_FACTOR): quem se
    # promove a avançado sozinho ganha volume que a recuperação dele não banca.
    if (v := answers.get("training_time")) is not None:
        p.training_time = training_brain.one_of(v, training_brain.TRAINING_TIME_VALUES)
        if (nivel := training_brain.experience_from_training_time(p.training_time)) is not None:
            p.experience_level = ExperienceLevel(nivel)
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
    # A fila de prioridade vem dos TRÊS campos ordenados da tela, não de uma
    # lista de checkbox — a posição é a informação (ver questionnaire).
    training_brain.apply_weak_points(
        p, questionnaire.ordered_priorities(answers), datetime.now(timezone.utc)
    )
    p.periodization = training_brain.valid_periodization(answers.get("periodization"))
    if answers.get("wants_cardio") is not None:
        p.wants_cardio = bool(answers["wants_cardio"])
    # None é resposta VÁLIDA aqui (= "não escolheu"), e nesse caso vale o padrão
    # por nível de training_brain.advanced_allowed: iniciante não recebe técnica
    # avançada, os demais recebem. Por isso o `is not None` — sem ele, quem
    # deixasse a pergunta em branco zeraria a escolha anterior.
    if answers.get("allow_advanced_techniques") is not None:
        novo_valor = bool(answers["allow_advanced_techniques"])
        # Desligar reverte as dicas já ativas — senão a escolha "não" fica sem
        # efeito nenhum sobre o que já foi aplicado (ver
        # workout_builder.revert_technique_cues). Roda mesmo se o valor
        # anterior era None (nunca escolheu, valia o padrão por nível — que
        # para intermediário/avançado já podia ter criado dicas). Ligar não
        # precisa reverter nada: é só permitir de novo.
        if not novo_valor:
            workout_builder.revert_technique_cues(db, p.user_id)
        p.allow_advanced_techniques = novo_valor
    if answers.get("avoid_mixing_upper_lower") is not None:
        p.avoid_mixing_upper_lower = bool(answers["avoid_mixing_upper_lower"])
    if answers.get("dietary_restrictions") is not None:
        p.dietary_restrictions = list(answers["dietary_restrictions"] or [])
    if answers.get("exercise_prefs") is not None:
        p.exercise_prefs = training_brain.valid_exercise_prefs(answers.get("exercise_prefs"))
    if answers.get("strong_points") is not None:
        p.strong_points = training_brain.valid_weak_points(answers.get("strong_points"))

    # --- AS RESPOSTAS ESTRUTURADAS -----------------------------------------
    # Substituíram os 6 campos de texto livre do questionário antigo (histórico,
    # lesões, preferências, alimentos, medicamentos, observações), que eram
    # gravados e nunca lidos por regra nenhuma. Cada campo abaixo tem consumidor
    # determinístico — ver o bloco correspondente em models/user_profile.py.
    #
    # `is not None` em tudo: None significa "não respondeu" e preserva o valor
    # anterior. Sem isso, avançar uma etapa sem tocar num campo o apagaria.
    for campo, permitidos in (
        ("rir_accuracy", training_brain.RIR_ACCURACY_VALUES),
        ("failure_comfort", training_brain.FAILURE_COMFORT_VALUES),
        ("load_preference", training_brain.LOAD_PREFERENCE_VALUES),
        ("gym_crowding", training_brain.GYM_CROWDING_VALUES),
        ("split_preference", training_brain.SPLIT_PREFERENCE_VALUES),
        ("pain_intensity", training_brain.PAIN_INTENSITY_VALUES),
        ("sleep_quality", training_brain.SLEEP_QUALITY_VALUES),
        ("stress_level", training_brain.STRESS_LEVEL_VALUES),
        ("recovery_between", training_brain.RECOVERY_BETWEEN_VALUES),
        ("other_sport", training_brain.OTHER_SPORT_VALUES),
    ):
        if answers.get(campo) is not None:
            setattr(p, campo, training_brain.one_of(answers.get(campo), permitidos))

    for campo, permitidos in (
        ("injury_regions", training_brain.BODY_REGION_VALUES),
        ("pain_regions", training_brain.BODY_REGION_VALUES),
        ("limitations", training_brain.LIMITATION_VALUES),
        ("home_equipment", training_brain.HOME_EQUIPMENT_VALUES),
        ("known_techniques", training_brain.KNOWN_TECHNIQUE_VALUES),
    ):
        if answers.get(campo) is not None:
            setattr(p, campo, training_brain.many_of(answers.get(campo), permitidos))

    if answers.get("food_dislikes_list") is not None:
        p.food_dislikes_list = training_brain.many_of(
            answers.get("food_dislikes_list"), {v for v, _ in questionnaire.FOOD_DISLIKES}
        )

    # Lesão e dor: responder "não" precisa LIMPAR as regiões marcadas antes,
    # senão quem se recupera continua com exercício bloqueado pra sempre.
    for flag, dependentes in (
        ("has_injury", ("injury_regions", "medical_clearance")),
        ("has_pain", ("pain_regions", "pain_intensity")),
    ):
        if answers.get(flag) is None:
            continue
        marcado = bool(answers[flag])
        setattr(p, flag, marcado)
        if not marcado:
            for dep in dependentes:
                setattr(p, dep, [] if dep.endswith("_regions") else None)
    if answers.get("medical_clearance") is not None and p.has_injury:
        p.medical_clearance = bool(answers["medical_clearance"])

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
    # O gasto MEDIDO na pessoa entra no lugar do previsto pela fórmula, na
    # proporção da evidência que existe. Quem acabou de chegar recebe a fórmula
    # pura; quem já registrou semanas de comida e peso recebe o número dela.
    from app.coaching import adaptive

    aprendido = adaptive.energia_do_usuario(db, user.id, p, float(peso))
    tdee = aprendido.aplicar(
        calculate_tdee(calculate_bmr(p.biological_sex, float(peso), p.height_cm, p.age), p.activity_level)
    )
    auto = compute_auto_goal(
        biological_sex=p.biological_sex, weight_kg=float(peso), height_cm=p.height_cm,
        age=p.age, activity_level=p.activity_level, goal=p.goal,
        tdee_override=tdee,
    )
    goal = CalorieGoal(
        user_id=user.id, mode=GoalMode.AUTO, kcal=auto["kcal"],
        protein_g=auto["protein_g"], carbs_g=auto["carbs_g"], fat_g=auto["fat_g"],
    )
    db.add(goal)
    db.flush()
    return goal.id


CONSENT_VERSION = "1.0"


def _registrar_consentimentos(db: Session, user: User, answers: dict) -> None:
    """Grava o aceite como REGISTRO (append-only, com data e versão do texto).

    Não é um booleano no perfil: consentimento é prova, e prova precisa dizer
    QUANDO e a QUE TEXTO a pessoa disse sim. Só grava quando ainda não existe
    aceite da versão atual — reativar o plano não deve empilhar registros
    idênticos.
    """
    from app.models.consent import ConsentRecord, ConsentType

    alvos = (
        (ConsentType.LGPD_HEALTH_DATA, answers.get("accepted_lgpd_health_data")),
        (ConsentType.MEDICAL_DISCLAIMER, answers.get("accepted_medical_disclaimer")),
    )
    for tipo, aceito in alvos:
        if not aceito:
            continue
        ja_tem = db.execute(
            select(ConsentRecord).where(
                ConsentRecord.user_id == user.id,
                ConsentRecord.consent_type == tipo,
                ConsentRecord.version == CONSENT_VERSION,
                ConsentRecord.accepted.is_(True),
            ).limit(1)
        ).scalar_one_or_none()
        if ja_tem is None:
            db.add(ConsentRecord(
                user_id=user.id, consent_type=tipo, version=CONSENT_VERSION, accepted=True
            ))


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
    # Dado de saúde só entra com consentimento explícito (LGPD). Este
    # questionário é o cadastro do Coaching, então é aqui que a autorização é
    # dada — e sem ela nada é gerado.
    erro_consentimento = questionnaire.consent_error(answers)
    if erro_consentimento:
        raise ValueError(erro_consentimento)

    anterior = active_plan(db, user.id)
    respostas_antigas = dict(anterior.answers or {}) if anterior else {}
    mudancas = diff_answers(respostas_antigas, answers) if anterior else []
    # Plano de um questionário ANTERIOR ao atual: regera TUDO, sem confiar no
    # diff campo-a-campo.
    #
    # A atualização conservadora (só refaz o que mudou) pressupõe que os dois
    # lados falam a mesma língua. Quando o questionário é reescrito, o plano
    # antigo guarda respostas de um esquema que não existe mais — e o diff passa
    # a comparar campos novos contra o vazio. Isso já produziu o pior tipo de
    # falha: silenciosa. A pessoa respondia o questionário novo inteiro, o
    # sistema dizia "plano atualizado", e o TREINO continuava sendo o montado
    # pelo questionário velho, porque o componente "treino" não entrou na conta.
    #
    # A checagem é estrutural, não por versão: o plano é considerado defasado
    # quando não conhece os campos que HOJE decidem o treino. Assim ela continua
    # valendo na próxima vez que o questionário mudar, sem ninguém lembrar de
    # bumpar um número.
    if anterior is not None and _de_esquema_antigo(respostas_antigas):
        componentes_alvo = list(TODOS_COMPONENTES)
    else:
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

        # 7) Registra o consentimento (prova de que foi dado, com data e versão)
        #    e marca o cadastro como concluído — este questionário É o cadastro
        #    do Coaching, então concluí-lo é o que tira a pessoa da tela de
        #    cadastro. Sem isto ela responderia tudo e voltaria pro formulário.
        _registrar_consentimentos(db, user, answers)
        if not user.onboarding_completed:
            user.onboarding_completed = True
            db.add(user)

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
