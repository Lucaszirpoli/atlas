"""O QUESTIONÁRIO da aba Objetivo (spec §3.2).

É a coleta única do Coaching Premium: treino E dieta saem daqui. O app monta a
tela a partir deste módulo e o backend valida com as mesmas regras — sem isso, as
opções da tela e as aceitas pela API divergem na primeira mudança.

REGRA DESTE ARQUIVO, a partir da reescrita de 2026-07-31:

    Toda pergunta precisa mudar um número do plano. Se a resposta não altera
    nenhum exercício, série, caloria ou macro, ela não é perguntada.

O questionário anterior tinha 6 campos de TEXTO LIVRE (histórico de treino,
lesões, preferências de exercício, alimentos, medicamentos, observações). Todos
eram gravados no perfil e NENHUMA regra os lia: quem escrevia "dor no ombro
direito em supino reto" via o coach montar supino reto do mesmo jeito. Texto
livre o motor não consegue obedecer; opção ele consegue. Por isso agora tudo é
escolha única, múltipla escolha ou sim/não — os únicos campos numéricos que
sobraram são os que viram conta (idade, altura, peso, sono), porque faixa de
idade estragaria o cálculo de gasto energético.

As opções moram em `training_brain` (o motor lê de lá); aqui fica só a montagem
das etapas.
"""

from __future__ import annotations

from typing import Any

from app.coaching import training_brain
from app.models.user_profile import (
    ActivityLevel,
    BiologicalSex,
    Goal,
    GoalPace,
    TrainingLocation,
)

# Tipos de campo que o app sabe desenhar. TEXT continua existindo no
# renderizador, mas o questionário não usa mais nenhum — ver o docstring.
NUMBER = "number"
SINGLE = "single"     # escolha única (radio)
MULTI = "multi"       # múltipla escolha (checkbox)
BOOL = "bool"

RESTRICOES = [
    ("vegetariano", "Vegetariano"), ("vegano", "Vegano"), ("sem_lactose", "Sem lactose"),
    ("sem_gluten", "Sem glúten"), ("sem_ovo", "Sem ovo"), ("sem_frutos_do_mar", "Sem frutos do mar"),
    ("low_carb", "Low carb"), ("halal", "Halal"), ("kosher", "Kosher"),
]

# Alimentos que a pessoa não come. Era um campo de texto ("Ex.: fígado, jiló,
# peixe...") que o gerador de dieta não lia. Como lista, ele exclui de verdade.
# São os rejeitados mais comuns — o que não estiver aqui a pessoa simplesmente
# troca no plano, que é 1 toque.
FOOD_DISLIKES = [
    ("figado", "Fígado e miúdos"), ("peixe", "Peixe"), ("frutos_do_mar", "Frutos do mar"),
    ("ovo", "Ovo"), ("leite", "Leite puro"), ("queijo_forte", "Queijos fortes"),
    ("jilo", "Jiló e vegetais amargos"), ("brocolis", "Brócolis e couve-flor"),
    ("cogumelo", "Cogumelo"), ("tomate", "Tomate"), ("cebola", "Cebola"),
    ("pimentao", "Pimentão"), ("beterraba", "Beterraba"), ("abobrinha", "Abobrinha"),
    ("banana", "Banana"), ("mamao", "Mamão"), ("aveia", "Aveia"),
    ("batata_doce", "Batata-doce"), ("tapioca", "Tapioca"), ("whey", "Whey protein"),
]


def _opts(pairs) -> list[dict]:
    """Opções (value, label) — sem descrição."""
    return [{"value": v, "label": label} for v, label in pairs]


def _opts3(triples) -> list[dict]:
    """Opções (value, label, desc) — a descrição vira o subtítulo do card."""
    return [
        {"value": v, "label": label, **({"desc": desc} if desc else {})}
        for v, label, desc in triples
    ]


def _enum_opts(enum_cls, labels: dict[str, str]) -> list[dict]:
    return [{"value": m.value, "label": labels.get(m.value, m.value)} for m in enum_cls]


GOAL_LABELS = {
    "emagrecimento": "Emagrecimento", "hipertrofia": "Hipertrofia", "manutencao": "Manutenção",
    "performance": "Performance", "recomposicao": "Recomposição",
}
PACE_LABELS = {"slow": "Devagar e sustentável", "normal": "Equilibrado (recomendado)", "fast": "Mais rápido"}
LOCAL_LABELS = {
    "academia_completa": "Academia completa", "academia_basica": "Academia básica",
    "casa_com_equipamento": "Em casa, com equipamento", "casa_sem_equipamento": "Em casa, sem equipamento",
}
ACTIVITY_LABELS = {
    "sedentary": "Sedentário", "light": "Leve", "moderate": "Moderado",
    "active": "Ativo", "very_active": "Muito ativo",
}
SEX_LABELS = {"female": "Feminino", "male": "Masculino"}

# As três vagas da fila de prioridade muscular. São campos SEPARADOS de escolha
# única em vez de uma múltipla escolha porque a ORDEM é a informação: quem fica
# em 1º recebe o topo da faixa de volume, o 2º um pouco menos, o 3º menos ainda
# (volume_landmarks._WEAK_TOP_BY_RANK). Uma lista de checkbox não tem ordem.
PRIORITY_KEYS = ("priority_1", "priority_2", "priority_3")
_PRIORITY_LABELS = ("1ª prioridade", "2ª prioridade", "3ª prioridade")
_NENHUM = {"value": "", "label": "Nenhum"}


def _priority_field(i: int) -> dict:
    return {
        "key": PRIORITY_KEYS[i],
        "label": _PRIORITY_LABELS[i],
        "type": SINGLE,
        "required": False,
        "options": ([] if i == 0 else [_NENHUM]) + _opts(training_brain.WEAK_POINTS),
    }


def steps() -> list[dict]:
    """As etapas, na ordem em que a pessoa responde. Cada campo diz seu tipo, se
    é obrigatório e as opções — o app não precisa saber nada além disto.

    São 8 etapas curtas, e não 3 longas, de propósito: a mesma quantidade de
    perguntas numa tela só parece um formulário de cadastro; divididas, cada tela
    tem 3 a 7 escolhas e leva segundos.
    """
    return [
        # --- 1 -------------------------------------------------------------
        {
            "key": "objetivo",
            "title": "Seu objetivo",
            "subtitle": "É daqui que saem suas metas de caloria e o desenho do treino.",
            "fields": [
                {"key": "goal", "label": "O que você quer alcançar", "type": SINGLE, "required": True,
                 "options": _enum_opts(Goal, GOAL_LABELS)},
                {"key": "goal_pace", "label": "Em que ritmo", "type": SINGLE, "required": False,
                 "options": _enum_opts(GoalPace, PACE_LABELS),
                 "help": "O ritmo escala o déficit ou o superávit. Devagar preserva mais músculo "
                         "e é mais fácil de sustentar."},
                {"key": "target_weight_kg", "label": "Peso-alvo (opcional)", "type": NUMBER, "required": False,
                 "suffix": "kg", "min": 30, "max": 300, "decimal": True},
            ],
        },
        # --- 2 -------------------------------------------------------------
        {
            "key": "dados",
            "title": "Seus dados",
            "subtitle": "O mínimo pra calcular seu gasto energético.",
            "fields": [
                {"key": "biological_sex", "label": "Sexo biológico", "type": SINGLE, "required": True,
                 "options": _enum_opts(BiologicalSex, SEX_LABELS),
                 "help": "Usado só no cálculo do gasto energético."},
                {"key": "age", "label": "Idade", "type": NUMBER, "required": True, "suffix": "anos",
                 "min": 13, "max": 100},
                {"key": "height_cm", "label": "Altura", "type": NUMBER, "required": True, "suffix": "cm",
                 "min": 100, "max": 250},
                {"key": "weight_kg", "label": "Peso atual", "type": NUMBER, "required": True, "suffix": "kg",
                 "min": 30, "max": 300, "decimal": True},
                # Cobre também "seu trabalho exige esforço físico?": é a mesma
                # informação (gasto fora do treino), e perguntar duas vezes só
                # aumentaria a chance de respostas contraditórias.
                {"key": "activity_level", "label": "Como é seu dia fora do treino", "type": SINGLE,
                 "required": True, "options": _enum_opts(ActivityLevel, ACTIVITY_LABELS),
                 "help": "Conta trabalho e rotina. Quem passa o dia em pé ou carregando peso "
                         "gasta bem mais que quem fica sentado."},
                {"key": "calorie_goal_mode", "label": "Sua meta de calorias", "type": SINGLE,
                 "required": True,
                 "options": [
                     {"value": "auto", "label": "Calcule pra mim",
                      "desc": "Saio do seu objetivo, ritmo e dados acima. É o recomendado."},
                     {"value": "manual", "label": "Eu defino",
                      "desc": "Você informa as calorias e a divisão dos macros."},
                 ]},
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
        # --- 3 -------------------------------------------------------------
        {
            "key": "experiencia",
            "title": "Sua experiência",
            "subtitle": "Define seu volume inicial e o quanto eu chego perto do limite.",
            "fields": [
                # Substitui "você se considera iniciante/intermediário/avançado?".
                # Tempo é verificável; auto-avaliação é inflada, e o nível decide
                # 15% do seu volume semanal.
                {"key": "training_time", "label": "Há quanto tempo você treina de forma consistente",
                 "type": SINGLE, "required": True,
                 "options": _opts([(v, label) for v, label, _ in training_brain.TRAINING_TIME]),
                 "help": "Vale o tempo treinando de verdade, sem contar longas paradas."},
                {"key": "rir_accuracy",
                 "label": "Ao terminar uma série, você sabe quantas repetições ainda conseguiria fazer?",
                 "type": SINGLE, "required": False,
                 "options": _opts3(training_brain.RIR_ACCURACY),
                 "help": "Não tem resposta certa. Isso só me diz o tamanho da margem de segurança "
                         "que eu deixo nas suas séries."},
                {"key": "failure_comfort", "label": "Você gosta de treinar perto do limite?",
                 "type": SINGLE, "required": False,
                 "options": _opts3(training_brain.FAILURE_COMFORT)},
                {"key": "load_preference", "label": "Prefere carga alta ou mais repetições?",
                 "type": SINGLE, "required": False,
                 "options": _opts3(training_brain.LOAD_PREFERENCE)},
            ],
        },
        # --- 4 -------------------------------------------------------------
        {
            "key": "onde",
            "title": "Onde você treina",
            "subtitle": "O que existe no seu lugar de treino define o que eu posso montar.",
            "fields": [
                {"key": "training_location", "label": "Onde", "type": SINGLE, "required": True,
                 "options": _enum_opts(TrainingLocation, LOCAL_LABELS)},
                {"key": "home_equipment", "label": "O que você tem em casa", "type": MULTI,
                 "required": False, "options": _opts(training_brain.HOME_EQUIPMENT),
                 "shows_if": {"field": "training_location", "equals": "casa_com_equipamento"},
                 "help": "Eu monto o plano só com o que você marcar aqui."},
                # "A academia costuma estar cheia?" SAIU.
                #
                # O efeito que ela teria é o do manual: não prescrever superset,
                # que exige segurar duas estações ao mesmo tempo. Só que o motor
                # NUNCA prescreve superset — `training_brain.suggest_technique`
                # escolhe entre rest-pause, myo-reps, back-off e muscle round, e
                # o superset existe no catálogo sem nenhum caminho que o
                # selecione. A pergunta não teria como mudar nada.
                #
                # Ela volta junto com o superset pareado (o modelo que liga dois
                # exercícios, que também não existe).
            ],
        },
        # --- 5 -------------------------------------------------------------
        {
            "key": "disponibilidade",
            "title": "Quando você treina",
            "subtitle": "É isto que define quantos treinos eu monto e de que tamanho.",
            "fields": [
                # "QUAIS dias você treina" saiu. O motor lê o NÚMERO de dias
                # (acima) pra escolher a divisão; os dias específicos nunca
                # decidiram qual treino cai em qual dia — eram lidos só pra
                # CONTAR quantos eram, quando o número não tinha sido respondido.
                # Continuam existindo no perfil (vêm do onboarding), só não são
                # mais perguntados aqui.
                {"key": "training_days_per_week", "label": "Dias por semana",
                 "type": SINGLE, "required": True,
                 "options": [{"value": str(n), "label": f"{n} dias"} for n in training_brain.TRAINING_DAYS_OPTIONS]},
                {"key": "session_length", "label": "Tempo por treino", "type": SINGLE, "required": True,
                 "options": [{"value": v, "label": label, "desc": faixa}
                             for v, label, faixa, _ in training_brain.SESSION_LENGTHS],
                 "help": "É a ordem de grandeza. O tempo real cai conforme você treina mais "
                         "dias na semana, porque o mesmo volume se divide em mais treinos — "
                         "eu te digo a duração exata assim que montar o plano."},
                # "Qual divisão você prefere?" SAIU, e por um motivo que só
                # apareceu ao tentar implementá-la.
                #
                # Pra cada número de dias existe UMA divisão que cumpre a regra 6
                # (mínimo 2×/semana por grupo) com os blueprints que existem:
                # 2 e 3 dias -> full body; 4 -> superior/inferior; 5 -> PPL +
                # superior/inferior; 6 -> PPL ×2. As alternativas ou quebram a
                # frequência mínima (PPL em 3 dias passa a 1×/semana por grupo)
                # ou exigem blueprint que não foi escrito (full body ×4,
                # superior/inferior ×6).
                #
                # Ou seja: escolher a divisão só mudaria alguma coisa piorando o
                # treino. Ela volta quando os blueprints faltantes existirem.
            ],
        },
        # --- 6 -------------------------------------------------------------
        {
            "key": "saude",
            "title": "Saúde e limitações",
            "subtitle": "O que eu preciso evitar. Isso tira exercício do seu plano de verdade.",
            "fields": [
                {"key": "has_injury",
                 "label": "Você tem alguma lesão, cirurgia, placa, pino ou prótese?",
                 "type": BOOL, "required": False},
                {"key": "injury_regions", "label": "Em qual região", "type": MULTI, "required": False,
                 "options": _opts(training_brain.BODY_REGIONS),
                 "shows_if": {"field": "has_injury", "equals": "true"}},
                {"key": "medical_clearance",
                 "label": "Você tem liberação de um profissional pra treinar com isso?",
                 "type": BOOL, "required": False,
                 "shows_if": {"field": "has_injury", "equals": "true"},
                 "help": "Sem liberação eu trabalho mais conservador nessa região. "
                         "O app não substitui avaliação médica."},
                {"key": "has_pain", "label": "Sente dor em algum exercício ou movimento?",
                 "type": BOOL, "required": False},
                {"key": "pain_regions", "label": "Onde dói", "type": MULTI, "required": False,
                 "options": _opts(training_brain.BODY_REGIONS),
                 "shows_if": {"field": "has_pain", "equals": "true"}},
                {"key": "pain_intensity", "label": "Quanto dói", "type": SINGLE, "required": False,
                 "options": _opts3(training_brain.PAIN_INTENSITY),
                 "shows_if": {"field": "has_pain", "equals": "true"}},
                {"key": "limitations", "label": "Alguma dessas te limita hoje?", "type": MULTI,
                 "required": False, "options": _opts3(training_brain.LIMITATIONS)},
                # Substitui os dois campos de texto "exercícios que você gosta" e
                # "exercícios que não quer". Cada opção abaixo o montador obedece
                # (workout_builder.filtrar_por_preferencia); texto ele ignorava.
                {"key": "exercise_prefs", "label": "Suas preferências de exercício", "type": MULTI,
                 "required": False, "options": _opts3(training_brain.EXERCISE_PREFS),
                 "help": "Isto muda os exercícios que eu escolho, não só o texto do plano."},
            ],
        },
        # --- 7 -------------------------------------------------------------
        {
            "key": "prioridades",
            "title": "O que você quer desenvolver",
            "subtitle": "Em ordem. O 1º recebe mais volume que o 2º, e o 2º mais que o 3º.",
            "fields": [
                _priority_field(0),
                _priority_field(1),
                _priority_field(2),
                {"key": "strong_points", "label": "Já está bom, quero só manter (opcional)",
                 "type": MULTI, "required": False, "max_selected": training_brain.WEAK_POINTS_MAX,
                 "options": _opts(training_brain.WEAK_POINTS),
                 "help": "Fica perto do volume mínimo — manter custa bem menos que crescer, e "
                         "sobra recuperação pras suas prioridades."},
                {"key": "allow_advanced_techniques",
                 "label": "Posso usar técnicas avançadas nos seus treinos?",
                 "type": BOOL, "required": False,
                 "help": "Myo-reps, rest-pause, muscle round, back-off e superset. Rendem mais "
                         "estímulo no mesmo tempo, mas trabalham perto da falha."},
                {"key": "known_techniques", "label": "Quais você já usou", "type": MULTI,
                 "required": False, "options": _opts(training_brain.KNOWN_TECHNIQUES),
                 "shows_if": {"field": "allow_advanced_techniques", "equals": "true"},
                 "help": "Eu começo pelas que você já conhece. As outras entram depois, "
                         "uma de cada vez."},
                {"key": "periodization", "label": "Como o treino evolui ao longo dos meses",
                 "type": SINGLE, "required": False,
                 "options": _opts3(training_brain.PERIODIZATIONS)},
            ],
        },
        # --- 8 -------------------------------------------------------------
        {
            "key": "recuperacao",
            "title": "Recuperação e alimentação",
            "subtitle": "Quanto você recupera decide quanto volume aguenta.",
            "fields": [
                # "Quantas horas você dorme" saiu. O número era coletado e
                # DESCARTADO (não existe coluna pra ele, e nada o lia), e o app
                # já tem a aba de Sono, onde a pessoa registra o que dormiu de
                # verdade — perguntar a média aqui competiria com o dado real.
                # O que ficou é a QUALIDADE, que o registro de sono não captura
                # e que entra no fator de recuperação.
                {"key": "sleep_quality", "label": "Como você tem dormido", "type": SINGLE,
                 "required": False, "options": _opts(training_brain.SLEEP_QUALITY)},
                {"key": "stress_level", "label": "Como é sua semana", "type": SINGLE,
                 "required": False, "options": _opts(training_brain.STRESS_LEVEL)},
                # Uma pergunta no lugar de duas ("costuma estar recuperado?" e
                # "sente dor prolongada ou queda de desempenho?"): é a mesma
                # informação perguntada de dois jeitos.
                {"key": "recovery_between", "label": "Como você chega no treino seguinte",
                 "type": SINGLE, "required": False,
                 "options": _opts3(training_brain.RECOVERY_BETWEEN)},
                {"key": "other_sport", "label": "Pratica outro esporte ou atividade?",
                 "type": SINGLE, "required": False,
                 "options": _opts3(training_brain.OTHER_SPORT),
                 "help": "Não é pra te desencorajar — é pra o treino caber junto, "
                         "sem te deixar sem recuperação."},
                {"key": "wants_cardio", "label": "Quer cardio no plano?", "type": BOOL, "required": False},
                {"key": "dietary_restrictions", "label": "Restrições alimentares", "type": MULTI,
                 "required": False, "options": _opts(RESTRICOES)},
                {"key": "meals_per_day", "label": "Refeições por dia", "type": SINGLE, "required": False,
                 "options": [{"value": str(n), "label": f"{n} refeições"} for n in (3, 4, 5, 6)]},
                {"key": "food_dislikes_list", "label": "Alimentos que você não come", "type": MULTI,
                 "required": False, "options": _opts(FOOD_DISLIKES),
                 "help": "Eu não coloco nenhum destes na sua dieta. O que não estiver na lista "
                         "você troca no plano com 1 toque."},
            ],
        },
    ]


def required_keys() -> list[str]:
    return [f["key"] for s in steps() for f in s["fields"] if f.get("required")]


def _cond_str(v: Any) -> str:
    """Um valor de resposta como o `shows_if` o compara.

    Existe por causa do booleano: o app compara com `String(true)` -> "true",
    e o Python faria `str(True)` -> "True". Sem normalizar, todo campo que
    aparece só quando a pessoa responde "sim" (região da lesão, onde dói,
    técnicas que já usou) ficaria invisível pro backend enquanto está visível na
    tela — os dois lados precisam enxergar a mesma coisa.
    """
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _visivel(field: dict, answers: dict[str, Any]) -> bool:
    """Campo condicional (ex.: os de meta manual só valem quando a pessoa
    escolheu "manual"). Sem `shows_if`, o campo sempre vale."""
    cond = field.get("shows_if")
    if not cond:
        return True
    return _cond_str(answers.get(cond["field"])) == _cond_str(cond["equals"])


def ordered_priorities(answers: dict[str, Any]) -> list[str]:
    """Os três campos de prioridade viram a lista ORDENADA de pontos fracos que
    o motor consome (`weak_points`).

    Vagas em branco são puladas e repetição é descartada — quem escolher "peito"
    em 1º e 2º acaba com uma prioridade só, que é exatamente o que ele pediu. A
    ordem da lista é a prioridade: é ela que define o topo da faixa de volume de
    cada músculo (volume_landmarks._WEAK_TOP_BY_RANK).
    """
    return training_brain.valid_weak_points(
        [answers.get(k) for k in PRIORITY_KEYS]
    )


def priorities_to_answers(weak_points: list[str] | None) -> dict[str, Any]:
    """O caminho inverso: a lista do perfil de volta pros três campos da tela,
    pra quem já respondeu ver a própria escolha ao reabrir o questionário."""
    lista = training_brain.valid_weak_points(weak_points)
    return {k: (lista[i] if i < len(lista) else None) for i, k in enumerate(PRIORITY_KEYS)}


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
