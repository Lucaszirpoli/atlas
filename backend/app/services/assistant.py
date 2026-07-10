"""Assistente DETERMINÍSTICO do app — SEM IA, sem custo de token. Responde
"quase tudo" sobre o que está DENTRO do app combinando duas coisas:

1. Perguntas sobre os SEUS dados (calorias/macros de hoje, meta, peso, água,
   sono, treinos da semana, constância) — calculadas na hora do banco.
2. Uma base de conhecimento fitness/nutrição (o que é RIR, RPE, deload,
   déficit calórico, etc.) e "como faço X no app".

Roteia por intenção via palavras-chave (sem acento/maiúscula). Se nada casar,
dá um fallback amigável dizendo o que ele sabe responder — e sugere a IA
avançada (Pro) pra perguntas abertas. Nunca inventa: só devolve número que
calculou ou texto curado da base.
"""

from __future__ import annotations

import unicodedata
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.calorie_goal import CalorieGoal
from app.models.meal import MealCategory, MealLog, MealLogItem
from app.models.sleep_log import SleepLog
from app.models.water_log import WaterLog
from app.models.weight_log import WeightLog
from app.models.workout_session import WorkoutSession
from app.schemas.meal import MealLogCreate, MealLogItemCreate
from app.services import meal_parser, meal_service, water_service


def _norm(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _has(text: str, *words: str) -> bool:
    return any(w in text for w in words)


# ---------------------------------------------------------------------------
# Consultas aos dados do usuário (calculadas na hora).
# ---------------------------------------------------------------------------

def _today_bounds() -> tuple[datetime, datetime]:
    today = datetime.now(timezone.utc).date()
    return (
        datetime.combine(today, time.min, tzinfo=timezone.utc),
        datetime.combine(today, time.max, tzinfo=timezone.utc),
    )


def _today_nutrition(db: Session, user_id: int) -> dict:
    start, end = _today_bounds()
    meals = db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items))
        .where(MealLog.user_id == user_id, MealLog.logged_at >= start, MealLog.logged_at <= end)
    ).scalars()
    kcal = protein = carbs = fat = 0.0
    for m in meals:
        for it in m.items:
            kcal += it.kcal
            protein += it.protein_g
            carbs += it.carbs_g
            fat += it.fat_g
    return {"kcal": round(kcal), "protein": round(protein), "carbs": round(carbs), "fat": round(fat)}


def _calorie_goal(db: Session, user_id: int) -> CalorieGoal | None:
    return db.execute(
        select(CalorieGoal).where(CalorieGoal.user_id == user_id).order_by(CalorieGoal.created_at.desc()).limit(1)
    ).scalar_one_or_none()


def _latest_weight(db: Session, user_id: int) -> WeightLog | None:
    return db.execute(
        select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.recorded_at.desc()).limit(1)
    ).scalar_one_or_none()


def _water_today(db: Session, user_id: int) -> tuple[int, int]:
    start, end = _today_bounds()
    total = db.execute(
        select(func.coalesce(func.sum(WaterLog.amount_ml), 0)).where(
            WaterLog.user_id == user_id, WaterLog.logged_at >= start, WaterLog.logged_at <= end
        )
    ).scalar_one()
    goal = water_service.compute_goal_ml(db, user_id)
    return int(total), int(goal)


def _sleep_last_and_week(db: Session, user_id: int) -> tuple[float | None, float | None, int]:
    # naive porque no SQLite os datetimes voltam sem timezone (no Postgres com
    # tz, .replace(tzinfo=None) de ambos os lados também compara certo).
    since = (datetime.now(timezone.utc) - timedelta(days=7)).replace(tzinfo=None)
    logs = list(
        db.execute(
            select(SleepLog).where(SleepLog.user_id == user_id).order_by(SleepLog.wake_at.desc())
        ).scalars()
    )
    if not logs:
        return None, None, 0
    last_h = (logs[0].wake_at - logs[0].sleep_at).total_seconds() / 3600
    week = [l for l in logs if l.wake_at.replace(tzinfo=None) >= since]
    avg_h = (
        sum((l.wake_at - l.sleep_at).total_seconds() / 3600 for l in week) / len(week) if week else None
    )
    return round(last_h, 1), (round(avg_h, 1) if avg_h else None), len(week)


def _workouts_this_week(db: Session, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return db.execute(
        select(func.count()).select_from(WorkoutSession).where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.completed_at.is_not(None),
            WorkoutSession.completed_at >= monday,
        )
    ).scalar_one()


# ---------------------------------------------------------------------------
# Registrar comida em linguagem natural direto no chat ("comi 3 pães e 2 ovos").
# ---------------------------------------------------------------------------

# Verbos que indicam "eu comi/bebi" — dispara o registro (fora de perguntas).
_EAT_VERBS = ("comi", "tomei", "ingeri", "lanchei", "jantei", "almocei", "comendo", "devorei", "mandei ver")

# Palavras da refeição -> nome da categoria pra casar com as do usuário.
_MEAL_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("cafe da manha", "cafe-da-manha", "no cafe"), "café da manhã"),
    (("almoco", "almocei"), "almoço"),
    (("jantar", "jantei", "janta"), "jantar"),
    (("lanche da tarde",), "lanche da tarde"),
    (("lanche da manha",), "lanche da manhã"),
    (("lanche", "lanchei"), "lanche"),
    (("ceia",), "ceia"),
]

# Fillers que sobram no começo depois de tirar o verbo/refeição.
_LEAD_FILLERS = {"no", "na", "de", "da", "do", "hoje", "ontem", "agora", "tipo", "uns", "umas", "que", "um pouco"}


def _pick_category(db: Session, user_id: int, text: str) -> tuple[MealCategory, str]:
    """Descobre em qual refeição registrar (pelo texto ou pela hora) e devolve
    a categoria + o texto sem a menção da refeição."""
    cats = meal_service.ensure_default_categories(db, user_id)
    db.flush()
    by_norm = {_norm(c.name): c for c in cats}

    cleaned = text
    for words, cat_name in _MEAL_HINTS:
        if _has(text, *words):
            # remove a menção da refeição do texto
            for w in words:
                cleaned = cleaned.replace(w, " ")
            cat = by_norm.get(_norm(cat_name))
            if cat is None:  # casa por prefixo (ex: "almoço" vs categorias do user)
                cat = next((c for c in cats if _norm(cat_name) in _norm(c.name)), None)
            if cat is not None:
                return cat, cleaned

    # Sem menção: escolhe pela hora do dia.
    hour = datetime.now(timezone.utc).hour  # UTC; aproximação boa o bastante
    target = (
        "café da manhã" if 8 <= hour < 14 else "almoço" if 14 <= hour < 18 else "jantar" if 18 <= hour < 24 else "ceia"
    )
    cat = by_norm.get(_norm(target)) or next((c for c in cats if _norm(target) in _norm(c.name)), None) or cats[0]
    return cat, cleaned


def _strip_lead_fillers(text: str) -> str:
    toks = text.split()
    while toks and toks[0] in _LEAD_FILLERS:
        toks.pop(0)
    return " ".join(toks)


def _try_log_food(db: Session, user_id: int, text: str) -> dict | None:
    """Se o texto for um registro de comida, interpreta e REGISTRA de verdade,
    devolvendo a confirmação. Senão devolve None (segue o roteamento normal)."""
    category, cleaned = _pick_category(db, user_id, text)
    # tira os verbos de "comer" do começo
    for v in _EAT_VERBS:
        cleaned = cleaned.replace(v, " ")
    cleaned = _strip_lead_fillers(" ".join(cleaned.split()))

    parsed = meal_parser.parse_meal_text(db, cleaned)
    valid = [p for p in parsed if p["food"] is not None and p["quantity_g"] and p["quantity_g"] > 0]
    if not valid:
        return _reply(
            "Entendi que você comeu algo, mas não consegui identificar os alimentos. "
            "Tente algo como \"comi 3 pães e 2 ovos\" ou \"150g de arroz e 100g de frango\"."
        )

    meal = meal_service.log_meal(
        db,
        user_id,
        MealLogCreate(
            meal_category_id=category.id,
            logged_at=datetime.now(timezone.utc),
            items=[MealLogItemCreate(food_id=p["food"].id, quantity_g=p["quantity_g"]) for p in valid],
        ),
    )
    db.commit()

    total_kcal = round(sum(i.kcal for i in meal.items))
    linhas = "; ".join(f"{p['food'].name} ({round(p['quantity_g'])}g)" for p in valid)
    return _reply(
        f"Registrei no {category.name}: {linhas} — {total_kcal} kcal. ✓\n"
        "Se algum alimento ficou diferente, dá pra ajustar ou remover na aba Dieta."
    )


# ---------------------------------------------------------------------------
# Base de conhecimento (respostas curadas). Cada item: (palavras, resposta).
# ---------------------------------------------------------------------------

KNOWLEDGE: list[tuple[tuple[str, ...], str]] = [
    (("rir",), "RIR (Reps In Reserve) é quantas repetições você ainda conseguiria fazer no fim de uma série. RIR 2 = pararia 2 antes da falha. Quanto menor o RIR, mais perto da falha e mais intenso."),
    (("rpe",), "RPE é o nível de esforço percebido de 0 a 10 (10 = esforço máximo, não conseguiria mais nenhuma repetição). É outra forma de medir a intensidade, parecida com o RIR (RPE 8 ≈ RIR 2)."),
    (("deload",), "Deload é uma semana mais leve (menos volume/carga) pra recuperar do acúmulo de fadiga e voltar mais forte. Costuma vir a cada 4-8 semanas ou quando o desempenho cai."),
    (("drop set", "dropset", "drop-set"), "Drop-set é fazer a série até perto da falha, reduzir o peso na hora e continuar sem descanso, esgotando o músculo. Técnica avançada de intensidade."),
    (("rest pause", "rest-pause", "restpause"), "Rest-pause é ir até a falha, descansar poucos segundos (10-15) e continuar a mesma série, arrancando mais repetições com a mesma carga."),
    (("myo", "myo-reps", "myo reps"), "Myo-reps: uma série de ativação até quase a falha, depois mini-séries curtas com pausas de poucos segundos — muito estímulo em pouco tempo."),
    (("hipertrofia",), "Hipertrofia é o crescimento muscular. Os principais gatilhos são tensão mecânica (carga desafiadora), volume adequado (séries por semana) e proximidade da falha, com boa recuperação e proteína suficiente."),
    (("volume",), "Volume de treino = quanto trabalho você fez, geralmente séries por grupo muscular na semana (ou peso × reps somado). Mais volume tende a gerar mais hipertrofia até um teto, respeitando a recuperação."),
    (("falha", "ate a falha", "até a falha"), "Treinar até a falha é fazer repetições até não conseguir mais uma com boa técnica. Útil em doses, mas gera muita fadiga — não precisa ser em toda série."),
    (("deficit", "déficit", "cutting", "emagrecer", "perder peso", "perder gordura"), "Pra perder gordura você precisa de déficit calórico: comer menos calorias do que gasta. Um déficit moderado (~300-500 kcal/dia) preserva músculo. Proteína alta e treino de força ajudam muito."),
    (("superavit", "superávit", "bulking", "ganhar massa", "ganhar peso", "ganhar musculo", "ganhar músculo"), "Pra ganhar massa você precisa de leve superávit calórico (comer um pouco mais do que gasta) + treino de força progressivo + proteína suficiente. Superávit pequeno (~200-300 kcal) minimiza ganho de gordura."),
    (("proteina", "proteína"), "Uma faixa prática pra quem treina é ~1,6 a 2,2 g de proteína por kg de peso por dia, distribuída ao longo das refeições. É o macronutriente mais importante pra manter/ganhar músculo."),
    (("agua", "água", "hidrata"), "Uma referência simples é ~35 ml de água por kg de peso por dia (mais em dias quentes ou de treino pesado). O app calcula sua meta com base no seu peso."),
    (("manter", "manutencao", "manutenção"), "Pra manter o peso, você come aproximadamente o que gasta (calorias de manutenção). O app estima sua meta a partir do seu perfil; ajuste conforme a balança ao longo das semanas."),
    (("cardio", "aerobico", "aeróbico"), "Cardio ajuda no gasto calórico e na saúde cardiovascular. Ele não atrapalha o ganho de músculo se a alimentação e a recuperação estiverem ok — dá pra combinar com a musculação."),
    (("descanso", "intervalo entre serie", "intervalo"), "Pra força/hipertrofia em compostos, 1,5-3 min de descanso entre séries costuma render melhor. Em isoladores, 1-1,5 min já basta. O importante é recuperar o suficiente pra manter a qualidade das reps."),
    (("bro split", "bro-split"), "Bro-split é treinar um músculo por dia (frequência 1x/semana). Funciona, mas pra maioria treinar cada grupo 2x/semana rende mais — por isso o app não usa bro-split como padrão."),
    (("cadencia", "cadência", "tempo"), "Cadência é o ritmo da repetição, em segundos por fase (ex: 3-1-1-1 = 3s descendo, 1s embaixo, 1s subindo, 1s no topo). Controlar a fase excêntrica (descida) aumenta o estímulo."),
    (("composto",), "Exercício composto envolve várias articulações e grupos musculares (agachamento, supino, remada). São a base do treino por moverem muita carga e estímulo."),
    (("isolado", "isolamento"), "Exercício isolado trabalha um músculo por uma articulação (rosca, extensora, elevação lateral). Ótimos pra complementar volume e detalhar grupos específicos."),
]

# "Como faço X no app" — respostas de navegação/ajuda.
HOWTO: list[tuple[tuple[str, ...], str]] = [
    (("registrar comida", "registrar refeicao", "registrar refeição", "anotar comida", "adicionar alimento", "lancar comida"),
     "Na aba Dieta, em cada refeição você tem 'Adicionar' (buscar alimento) e 'Falar/escrever' — nesse você digita ou fala pelo microfone do teclado algo como '30g de requeijão e 2 ovos' e o app registra."),
    (("criar treino", "montar treino", "nova rotina", "criar rotina"),
     "Na aba Treino: 'Nova rotina' pra montar do zero, ou 'Montar treino por metodologia' pra gerar um treino fiel a um método consagrado (Mentzer, FST-7, 5/3/1...)."),
    (("registrar peso", "anotar peso", "colocar peso"),
     "Toque em 'Veja sua evolução' (ou na aba de evolução) e use 'Registrar peso'. O histórico vira o gráfico de peso."),
    (("registrar sono", "anotar sono"),
     "Na tela de Sono você informa a hora que dormiu e acordou; o app calcula a duração e monta seu histórico."),
    (("registrar agua", "registrar água", "beber agua", "anotar agua"),
     "No card de Água (Início ou Dieta) toque nos botões +200/+300/+500 ml pra registrar rápido."),
]


def _knowledge_answer(text: str) -> str | None:
    for words, answer in KNOWLEDGE + HOWTO:
        if _has(text, *words):
            return answer
    return None


# ---------------------------------------------------------------------------
# Roteador principal.
# ---------------------------------------------------------------------------

def answer(db: Session, user_id: int, raw_text: str) -> dict:
    text = _norm(raw_text)
    if not text:
        return _fallback()

    is_question = _has(text, "quanto", "quantos", "quantas", "qual", "como", "o que", "oque", "sera", "?", "falta", "meta")
    # "devo/preciso/recomenda/por dia/por kg/ideal" = quer a RECOMENDAÇÃO
    # (conhecimento), não o número consumido hoje.
    wants_reco = _has(text, "devo", "preciso", "recomend", "por dia", "por kg", "ideal", "quanto de")

    # --- Registrar comida de verdade ("comi 3 pães e 2 ovos") ---
    # Só fora de perguntas (senão "quantas calorias comi hoje" viraria registro).
    if not is_question and _has(text, *_EAT_VERBS):
        logged = _try_log_food(db, user_id, text)
        if logged is not None:
            return logged

    # --- Como registrar comida (a dúvida "como faço") ---
    if _has(text, "registr", "anot", "adicion", "lanc", "coloc") and _has(text, "comida", "aliment", "refei"):
        return _reply(HOWTO[0][1])

    # --- Recomendações (conhecimento) antes dos dados quando "devo/por dia" ---
    if wants_reco and _has(text, "proteina", "proteína"):
        return _reply(_knowledge_answer("proteina") or "")
    if wants_reco and _has(text, "agua", "água", "hidrat"):
        return _reply(_knowledge_answer("agua") or "")

    # --- Dados: calorias / macros de hoje ---
    if _has(text, "caloria", "kcal") and is_question:
        n = _today_nutrition(db, user_id)
        goal = _calorie_goal(db, user_id)
        if goal:
            remaining = round(goal.kcal - n["kcal"])
            return _reply(
                f"Hoje você consumiu {n['kcal']} kcal de uma meta de {round(goal.kcal)} kcal — "
                f"{'faltam ' + str(remaining) if remaining > 0 else 'passou ' + str(-remaining)} kcal."
            )
        return _reply(f"Hoje você consumiu {n['kcal']} kcal. Você ainda não definiu uma meta calórica.")

    if _has(text, "proteina", "proteína") and is_question:
        n = _today_nutrition(db, user_id)
        goal = _calorie_goal(db, user_id)
        extra = f" (meta {round(goal.protein_g)} g)" if goal and goal.protein_g else ""
        return _reply(f"Hoje você consumiu {n['protein']} g de proteína{extra}.")

    if _has(text, "carboidrato", "carbo") and is_question:
        n = _today_nutrition(db, user_id)
        return _reply(f"Hoje você consumiu {n['carbs']} g de carboidrato.")

    if _has(text, "gordura") and is_question:
        n = _today_nutrition(db, user_id)
        return _reply(f"Hoje você consumiu {n['fat']} g de gordura.")

    if _has(text, "meta") and _has(text, "caloria", "kcal", "comer") and is_question:
        goal = _calorie_goal(db, user_id)
        if goal:
            return _reply(f"Sua meta é {round(goal.kcal)} kcal por dia ({round(goal.protein_g)} g de proteína).")
        return _reply("Você ainda não definiu uma meta calórica. Dá pra definir na aba Dieta > Meta.")

    # --- Peso ---
    if _has(text, "peso", "pesando", "balanca", "balança") and is_question:
        w = _latest_weight(db, user_id)
        if w:
            return _reply(f"Seu último peso registrado é {w.weight_kg} kg.")
        return _reply("Você ainda não registrou nenhum peso. Dá pra registrar na aba de evolução.")

    # --- Água ---
    if _has(text, "agua", "água", "hidrat") and is_question:
        total, goal = _water_today(db, user_id)
        pct = round(total / goal * 100) if goal else 0
        return _reply(f"Hoje você bebeu {total/1000:.1f} L de uma meta de {goal/1000:.1f} L ({pct}%).")

    # --- Sono ---
    if _has(text, "sono", "dormi", "dormir") and is_question:
        last_h, avg_h, nights = _sleep_last_and_week(db, user_id)
        if last_h is None:
            return _reply("Você ainda não registrou nenhuma noite de sono.")
        avg_txt = f" Média da semana: {avg_h}h em {nights} noites." if avg_h else ""
        return _reply(f"Sua última noite foi de {last_h}h de sono.{avg_txt}")

    # --- Treinos da semana / progresso ---
    if _has(text, "treino", "treinei", "treinar") and is_question:
        n = _workouts_this_week(db, user_id)
        return _reply(f"Você concluiu {n} {'treino' if n == 1 else 'treinos'} esta semana.")

    if _has(text, "progred", "evolu", "melhor") and is_question:
        n = _workouts_this_week(db, user_id)
        w = _latest_weight(db, user_id)
        parts = [f"{n} treinos esta semana"]
        if w:
            parts.append(f"peso atual {w.weight_kg} kg")
        return _reply(
            "Dá pra ver sua evolução completa (peso, volume, sono e a análise do período) na aba de evolução. Resumo: "
            + ", ".join(parts)
            + "."
        )

    # --- Base de conhecimento / como faço X ---
    kb = _knowledge_answer(text)
    if kb:
        return _reply(kb)

    return _fallback()


def _reply(text: str) -> dict:
    return {"reply": text, "answered": True}


def _fallback() -> dict:
    return {
        "reply": (
            "Ainda não sei responder isso por aqui, mas posso te ajudar com várias coisas! Experimente perguntar: "
            "\"quantas calorias comi hoje?\", \"quanta proteína?\", \"quanto tô pesando?\", \"quanta água bebi?\", "
            "\"como foi meu sono?\", \"quantos treinos fiz essa semana?\", ou termos como \"o que é RIR\", \"o que é "
            "déficit calórico\", \"como registro comida\". Pra perguntas mais abertas, o assistente de IA avançado "
            "(Pro) consegue ir além."
        ),
        "answered": False,
    }
