"""O QUESTIONÁRIO da aba Objetivo (spec §3.2).

É a coleta única do Coaching Premium: as perguntas que ficavam espalhadas
(onboarding + "Como eu monto seu treino" na aba Treino) passam a morar aqui,
em 6 etapas. A lógica de coleta é a que o app já tinha — o que muda é o lugar
e a experiência, não a inteligência por trás.

Este módulo é a FONTE ÚNICA da estrutura: o app monta a tela a partir daqui e o
backend valida com as mesmas regras. Sem isso, as opções da tela e as aceitas
pela API divergem na primeira mudança.
"""

from __future__ import annotations

from typing import Any

from app.coaching import training_brain
from app.models.user_profile import (
    ActivityLevel,
    BiologicalSex,
    ExperienceLevel,
    Goal,
    GoalPace,
    TrainingLocation,
)

# Tipos de campo que o app sabe desenhar.
TEXT = "text"
NUMBER = "number"
SINGLE = "single"     # escolha única (radio)
MULTI = "multi"       # múltipla escolha (checkbox)
BOOL = "bool"

DIAS_SEMANA = [
    ("seg", "Segunda"), ("ter", "Terça"), ("qua", "Quarta"), ("qui", "Quinta"),
    ("sex", "Sexta"), ("sab", "Sábado"), ("dom", "Domingo"),
]

RESTRICOES = [
    ("vegetariano", "Vegetariano"), ("vegano", "Vegano"), ("sem_lactose", "Sem lactose"),
    ("sem_gluten", "Sem glúten"), ("sem_ovo", "Sem ovo"), ("sem_frutos_do_mar", "Sem frutos do mar"),
    ("low_carb", "Low carb"), ("halal", "Halal"), ("kosher", "Kosher"),
]


def _opts(pairs) -> list[dict]:
    return [{"value": v, "label": label} for v, label in pairs]


def _enum_opts(enum_cls, labels: dict[str, str]) -> list[dict]:
    return [{"value": m.value, "label": labels.get(m.value, m.value)} for m in enum_cls]


GOAL_LABELS = {
    "emagrecimento": "Emagrecimento", "hipertrofia": "Hipertrofia", "manutencao": "Manutenção",
    "performance": "Performance", "recomposicao": "Recomposição",
}
PACE_LABELS = {"slow": "Devagar e sustentável", "normal": "Equilibrado (recomendado)", "fast": "Mais rápido"}
EXP_LABELS = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}
LOCAL_LABELS = {
    "academia_completa": "Academia completa", "academia_basica": "Academia básica",
    "casa_com_equipamento": "Em casa, com equipamento", "casa_sem_equipamento": "Em casa, sem equipamento",
}
ACTIVITY_LABELS = {
    "sedentary": "Sedentário", "light": "Leve", "moderate": "Moderado",
    "active": "Ativo", "very_active": "Muito ativo",
}
SEX_LABELS = {"female": "Feminino", "male": "Masculino"}


def steps() -> list[dict]:
    """As 6 etapas, na ordem da spec §3.2. Cada campo diz seu tipo, se é
    obrigatório e as opções — o app não precisa saber nada além disto."""
    return [
        {
            "key": "objetivo",
            "title": "Objetivo e dados corporais",
            "subtitle": "É daqui que saem suas metas de caloria, o ritmo e o tipo de treino.",
            "fields": [
                {"key": "goal", "label": "Seu objetivo principal", "type": SINGLE, "required": True,
                 "options": _enum_opts(Goal, GOAL_LABELS)},
                {"key": "goal_pace", "label": "Ritmo", "type": SINGLE, "required": False,
                 "options": _enum_opts(GoalPace, PACE_LABELS),
                 "help": "O ritmo escala o déficit ou o superávit. Devagar preserva mais músculo e é mais fácil de sustentar."},
                {"key": "biological_sex", "label": "Sexo biológico", "type": SINGLE, "required": True,
                 "options": _enum_opts(BiologicalSex, SEX_LABELS),
                 "help": "Usado só no cálculo do gasto energético."},
                {"key": "age", "label": "Idade", "type": NUMBER, "required": True, "suffix": "anos", "min": 13, "max": 100},
                {"key": "height_cm", "label": "Altura", "type": NUMBER, "required": True, "suffix": "cm", "min": 100, "max": 250},
                {"key": "weight_kg", "label": "Peso atual", "type": NUMBER, "required": True, "suffix": "kg",
                 "min": 30, "max": 300, "decimal": True},
                {"key": "target_weight_kg", "label": "Peso-alvo (opcional)", "type": NUMBER, "required": False,
                 "suffix": "kg", "min": 30, "max": 300, "decimal": True},
                {"key": "activity_level", "label": "Nível de atividade fora do treino", "type": SINGLE,
                 "required": True, "options": _enum_opts(ActivityLevel, ACTIVITY_LABELS)},
                {"key": "calorie_goal_mode", "label": "Como definir sua meta calórica", "type": SINGLE,
                 "required": True,
                 "options": [
                     {"value": "auto", "label": "Automática",
                      "desc": "O Coaching calcula pra você a partir do seu objetivo, ritmo e dados acima."},
                     {"value": "manual", "label": "Manual",
                      "desc": "Você define as calorias e a divisão dos macros em porcentagem."},
                 ],
                 "help": "Isto substitui a tela de ajuste de meta — a partir de agora ela mora só aqui."},
                {"key": "manual_kcal", "label": "Calorias por dia", "type": NUMBER, "required": True,
                 "suffix": "kcal", "min": 800, "max": 8000,
                 "shows_if": {"field": "calorie_goal_mode", "equals": "manual"}},
                {"key": "manual_pct_protein", "label": "Proteína (%)", "type": NUMBER, "required": True,
                 "suffix": "%", "min": 0, "max": 100, "decimal": True,
                 "shows_if": {"field": "calorie_goal_mode", "equals": "manual"}},
                {"key": "manual_pct_carbs", "label": "Carboidratos (%)", "type": NUMBER, "required": True,
                 "suffix": "%", "min": 0, "max": 100, "decimal": True,
                 "shows_if": {"field": "calorie_goal_mode", "equals": "manual"}},
                {"key": "manual_pct_fat", "label": "Gordura (%)", "type": NUMBER, "required": True,
                 "suffix": "%", "min": 0, "max": 100, "decimal": True,
                 "shows_if": {"field": "calorie_goal_mode", "equals": "manual"},
                 "help": "A soma de proteína, carboidratos e gordura precisa fechar 100%."},
            ],
        },
        {
            "key": "experiencia",
            "title": "Experiência e histórico de treino",
            "subtitle": "Quanto tempo de treino você tem e onde treina.",
            "fields": [
                {"key": "experience_level", "label": "Sua experiência", "type": SINGLE, "required": True,
                 "options": _enum_opts(ExperienceLevel, EXP_LABELS)},
                {"key": "training_location", "label": "Onde você treina", "type": SINGLE, "required": True,
                 "options": _enum_opts(TrainingLocation, LOCAL_LABELS)},
                {"key": "training_history", "label": "Histórico de treino (opcional)", "type": TEXT,
                 "required": False, "multiline": True,
                 "placeholder": "Há quanto tempo treina, pausas, o que já funcionou pra você..."},
            ],
        },
        {
            "key": "disponibilidade",
            "title": "Disponibilidade e rotina",
            "subtitle": "É isto que define quantos treinos eu monto e de que tamanho.",
            "fields": [
                {"key": "training_days_per_week", "label": "Quantos dias por semana você pode treinar",
                 "type": SINGLE, "required": True,
                 "options": [{"value": str(n), "label": f"{n} dias"} for n in training_brain.TRAINING_DAYS_OPTIONS]},
                {"key": "available_days", "label": "Quais dias (opcional)", "type": MULTI, "required": False,
                 "options": _opts(DIAS_SEMANA)},
                {"key": "session_length", "label": "Tempo por sessão", "type": SINGLE, "required": True,
                 "options": [{"value": v, "label": label, "desc": faixa}
                             for v, label, faixa, _ in training_brain.SESSION_LENGTHS]},
            ],
        },
        {
            "key": "pontos",
            "title": "Pontos fortes, fracos e limitações",
            "subtitle": "O que priorizar e o que evitar. Isso muda os exercícios e o volume de verdade.",
            "fields": [
                {"key": "weak_points", "label": f"Pontos fracos a priorizar (até {training_brain.WEAK_POINTS_MAX})",
                 "type": MULTI, "required": False, "max_selected": training_brain.WEAK_POINTS_MAX,
                 "options": _opts(training_brain.WEAK_POINTS),
                 "help": "Grupos que recebem mais volume. O resto é reduzido pra caber na sua recuperação."},
                {"key": "strong_points", "label": "Pontos já desenvolvidos (opcional)", "type": MULTI,
                 "required": False, "max_selected": training_brain.WEAK_POINTS_MAX,
                 "options": _opts(training_brain.WEAK_POINTS),
                 "help": "Ficam perto do volume mínimo — manter custa menos que crescer."},
                {"key": "injuries_limitations", "label": "Lesões ou limitações (opcional)", "type": TEXT,
                 "required": False, "multiline": True,
                 "placeholder": "Ex.: dor no ombro direito em supino reto, hérnia lombar..."},
                # Virou opção: texto livre aqui era guardado e nunca lido por
                # nada, então "prefiro máquinas" não mudava treino nenhum. Cada
                # opção abaixo tem efeito determinístico na escolha dos
                # exercícios (ver methods_engine._proibido_por_preferencia).
                {"key": "exercise_prefs", "label": "Preferências de exercício (opcional)", "type": MULTI,
                 "required": False,
                 "options": [{"value": v, "label": label, "desc": desc}
                             for v, label, desc in training_brain.EXERCISE_PREFS],
                 "help": "Isto muda os exercícios que eu escolho pra você, não só o texto do plano."},
                {"key": "exercise_preferences", "label": "Mais alguma preferência? (opcional)", "type": TEXT,
                 "required": False, "multiline": True,
                 "placeholder": "Exercício específico que você gosta ou não quer.",
                 "help": "O que não coube nas opções acima. Eu levo em conta na conversa e ao ajustar o plano."},
            ],
        },
        {
            "key": "alimentacao",
            "title": "Alimentação e restrições",
            "subtitle": "Base da dieta em PDF e das suas metas de calorias e macros.",
            "fields": [
                {"key": "dietary_restrictions", "label": "Restrições alimentares", "type": MULTI,
                 "required": False, "options": _opts(RESTRICOES)},
                {"key": "meals_per_day", "label": "Refeições por dia", "type": SINGLE, "required": False,
                 "options": [{"value": str(n), "label": f"{n} refeições"} for n in (3, 4, 5, 6)]},
                {"key": "food_dislikes", "label": "Alimentos que você não come (opcional)", "type": TEXT,
                 "required": False, "multiline": True, "placeholder": "Ex.: fígado, jiló, peixe..."},
            ],
        },
        {
            "key": "recuperacao",
            "title": "Recuperação e informações finais",
            "subtitle": "Sono, cardio e o que mais eu precisar saber pra ajustar o plano.",
            "fields": [
                {"key": "sleep_hours", "label": "Quanto você dorme por noite", "type": NUMBER,
                 "required": False, "suffix": "h", "min": 3, "max": 14, "decimal": True},
                {"key": "wants_cardio", "label": "Quer cardio no plano?", "type": BOOL, "required": False},
                {"key": "periodization", "label": "Periodização", "type": SINGLE, "required": False,
                 "options": [{"value": v, "label": label, "desc": desc}
                             for v, label, desc in training_brain.PERIODIZATIONS]},
                {"key": "medications", "label": "Medicamentos ou hormônios (opcional)", "type": TEXT,
                 "required": False, "multiline": True,
                 "help": "Só como contexto pro coach — isto não é avaliação médica e não substitui seu médico.",
                 "placeholder": "Se preferir não informar, tudo bem."},
                {"key": "notes", "label": "Mais alguma coisa? (opcional)", "type": TEXT, "required": False,
                 "multiline": True, "placeholder": "Qualquer coisa que eu deva levar em conta."},
            ],
        },
    ]


def required_keys() -> list[str]:
    return [f["key"] for s in steps() for f in s["fields"] if f.get("required")]


def _visivel(field: dict, answers: dict[str, Any]) -> bool:
    """Campo condicional (ex.: os de meta manual só valem quando a pessoa
    escolheu "manual"). Sem `shows_if`, o campo sempre vale."""
    cond = field.get("shows_if")
    if not cond:
        return True
    return str(answers.get(cond["field"])) == str(cond["equals"])


def macro_split_error(answers: dict[str, Any]) -> str | None:
    """Só quando a meta é manual: proteína + carbo + gordura precisa fechar
    100% (spec §9.2) — sem isso os gramas não batem com as calorias informadas."""
    if answers.get("calorie_goal_mode") != "manual":
        return None
    try:
        soma = round(
            float(answers.get("manual_pct_protein") or 0)
            + float(answers.get("manual_pct_carbs") or 0)
            + float(answers.get("manual_pct_fat") or 0),
            1,
        )
    except (TypeError, ValueError):
        return "A divisão de macros da meta manual está inválida."
    if soma != 100:
        return f"A divisão de macros da meta manual precisa somar 100% (está em {soma}%)."
    return None


def missing_required(answers: dict[str, Any]) -> list[str]:
    """Campos obrigatórios ainda em branco — o app usa pra impedir a conclusão
    (spec §3.1) e o backend recusa a ativação sem eles. Campos condicionais
    (`shows_if`) só entram na conta quando estão visíveis pras respostas atuais."""
    faltando = []
    for s in steps():
        for f in s["fields"]:
            if not f.get("required") or not _visivel(f, answers):
                continue
            v = answers.get(f["key"])
            if v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, list) and not v):
                faltando.append(f["key"])
    return faltando


# Rótulo humano de cada campo, pro resumo e pro "o que mudou".
FIELD_LABELS: dict[str, str] = {
    f["key"]: f["label"] for s in steps() for f in s["fields"]
}

# A qual etapa cada campo pertence — a visualização por categoria da §3.4.
FIELD_STEP: dict[str, str] = {
    f["key"]: s["title"] for s in steps() for f in s["fields"]
}
