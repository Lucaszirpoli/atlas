"""Definições das ferramentas (function calling) do assistente, no formato
esperado pela Anthropic API, restritas ao modo NUTRIÇÃO (Fase 3).

Ferramentas de leitura são executadas dentro do loop do orquestrador.
Ferramentas de escrita (WRITE_TOOL_NAMES) NUNCA são executadas pelo backend
automaticamente — o orquestrador intercepta a chamada e devolve uma proposta
para o app confirmar explicitamente (espec. 3.6)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.exercise import EXTENDED_STRENGTH_CATEGORIES, Exercise, MuscleGroup
from app.models.meal import MealLog, MealLogItem
from app.models.routine import Routine
from app.models.sleep_log import SleepLog
from app.models.water_log import WaterLog
from app.models.weight_log import WeightLog
from app.models.workout_session import WorkoutSession
from app.services import food_service, workout_insights_service

WRITE_TOOL_NAMES = {
    "registrar_refeicao",
    "atualizar_peso",
    "ajustar_meta_calorica",
    "criar_rotina_treino",
    "criar_dieta_personalizada",
    "criar_treino_personalizado",
}

TOOL_DEFINITIONS = [
    {
        "name": "buscar_alimento",
        "description": (
            "Busca alimentos na base do app (TACO + Open Food Facts + cadastros "
            "próprios) pelo nome. Use para achar o food_id certo antes de propor "
            "um registrar_refeicao."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"nome": {"type": "string", "description": "Nome do alimento buscado"}},
            "required": ["nome"],
        },
    },
    {
        "name": "consultar_historico",
        "description": "Consulta o histórico recente do usuário em nutrição, água, peso ou treino.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["refeicoes", "agua", "peso", "treinos", "sono"]},
                "dias": {"type": "integer", "description": "Quantos dias olhar para trás", "default": 7},
            },
            "required": ["tipo"],
        },
    },
    {
        "name": "buscar_exercicios",
        "description": (
            "Busca exercícios na biblioteca do app por nome e/ou grupo muscular. Use "
            "para achar os exercise_id certos antes de propor criar_rotina_treino."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Nome ou parte do nome do exercício"},
                "grupo_muscular": {
                    "type": "string",
                    "enum": [
                        "chest", "back", "shoulders", "biceps", "triceps", "quads",
                        "hamstrings", "glutes", "calves", "abs", "forearms", "traps",
                        "full_body", "cardio",
                    ],
                },
            },
        },
    },
    {
        "name": "registrar_refeicao",
        "description": (
            "Propõe o registro de uma refeição com um ou mais alimentos. NUNCA salva "
            "direto — o usuário precisa confirmar na interface antes de qualquer coisa "
            "ser gravada. Sempre busque os food_id certos com buscar_alimento antes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "categoria": {"type": "string", "description": "Ex: Café da manhã, Almoço"},
                "itens": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "food_id": {"type": "integer"},
                            "nome": {"type": "string"},
                            "quantidade_g": {"type": "number"},
                        },
                        "required": ["food_id", "nome", "quantidade_g"],
                    },
                },
            },
            "required": ["categoria", "itens"],
        },
    },
    {
        "name": "atualizar_peso",
        "description": "Propõe um novo registro de peso corporal. Nunca salva direto.",
        "input_schema": {
            "type": "object",
            "properties": {"peso_kg": {"type": "number"}},
            "required": ["peso_kg"],
        },
    },
    {
        "name": "ajustar_meta_calorica",
        "description": (
            "Propõe uma nova meta calórica/macro. Nunca salva direto — sempre mostre o "
            "raciocínio pro usuário antes de propor."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kcal": {"type": "number"},
                "protein_g": {"type": "number"},
                "carbs_g": {"type": "number"},
                "fat_g": {"type": "number"},
            },
            "required": ["kcal", "protein_g", "carbs_g", "fat_g"],
        },
    },
    {
        "name": "verificar_platos_e_deload",
        "description": (
            "Verifica se algum exercício do usuário está em platô (sem progressão de "
            "carga nas últimas sessões) e se já é hora de sugerir uma semana de deload "
            "(treino intenso contínuo por 4+ semanas). Use antes de reavaliar o treino "
            "de alguém."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "criar_rotina_treino",
        "description": (
            "Propõe a criação de UMA ÚNICA rotina de treino (um dia). Pra treino "
            "personalizado com MAIS DE UM dia (o caso comum — ex: Upper/Lower, PPL), "
            "use criar_treino_personalizado, que propõe todos os dias de uma vez. "
            "Sempre busque os exercise_id certos com buscar_exercicios antes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome": {"type": "string", "description": "Ex: Treino A - Upper"},
                "exercicios": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "exercise_id": {"type": "integer"},
                            "nome": {"type": "string"},
                            "target_sets": {"type": "integer"},
                            "target_reps_min": {"type": "integer"},
                            "target_reps_max": {"type": "integer"},
                            "rest_seconds": {"type": "integer", "default": 90},
                        },
                        "required": ["exercise_id", "nome", "target_sets", "target_reps_min"],
                    },
                },
            },
            "required": ["nome", "exercicios"],
        },
    },
    {
        "name": "listar_rotinas_ativas",
        "description": (
            "Lista as rotinas de treino ATIVAS (não arquivadas) do usuário. Use ANTES "
            "de propor criar_treino_personalizado: se já existir rotina ativa, "
            "PERGUNTE em texto (sem chamar ferramenta nesse turno) se a pessoa quer "
            "substituir as rotinas atuais pelas novas ou manter as duas coisas — só "
            "chame criar_treino_personalizado depois que ela responder."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "criar_dieta_personalizada",
        "description": (
            "Propõe um plano de dieta personalizado — um dia inteiro com uma ou mais "
            "refeições, cada uma com seus alimentos. Usa UMA confirmação só para o dia "
            "inteiro (não chame registrar_refeicao várias vezes). Sempre busque os "
            "food_id certos com buscar_alimento antes de cada alimento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "nome_do_plano": {"type": "string", "description": "Ex: Dieta personalizada - hipertrofia"},
                "refeicoes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "categoria": {"type": "string", "description": "Ex: Café da manhã, Almoço"},
                            "itens": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "food_id": {"type": "integer"},
                                        "nome": {"type": "string"},
                                        "quantidade_g": {"type": "number"},
                                    },
                                    "required": ["food_id", "nome", "quantidade_g"],
                                },
                            },
                        },
                        "required": ["categoria", "itens"],
                    },
                },
            },
            "required": ["refeicoes"],
        },
    },
    {
        "name": "criar_treino_personalizado",
        "description": (
            "Propõe um treino personalizado com UMA OU MAIS rotinas (um dia cada, ex: "
            "'Treino A - Upper', 'Treino B - Lower') em UMA confirmação só. Sempre "
            "busque os exercise_id certos com buscar_exercicios antes. Se "
            "listar_rotinas_ativas mostrou rotinas existentes, pergunte primeiro (em "
            "texto) se substitui ou mantém, e reflita a resposta em substituir_existentes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "substituir_existentes": {
                    "type": "boolean",
                    "description": "True para arquivar as rotinas ativas atuais antes de criar as novas.",
                    "default": False,
                },
                "rotinas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "nome": {"type": "string", "description": "Ex: Treino A - Upper"},
                            "exercicios": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "exercise_id": {"type": "integer"},
                                        "nome": {"type": "string"},
                                        "target_sets": {"type": "integer"},
                                        "target_reps_min": {"type": "integer"},
                                        "target_reps_max": {"type": "integer"},
                                        "rest_seconds": {"type": "integer", "default": 90},
                                    },
                                    "required": ["exercise_id", "nome", "target_sets", "target_reps_min"],
                                },
                            },
                        },
                        "required": ["nome", "exercicios"],
                    },
                },
            },
            "required": ["rotinas"],
        },
    },
]


def _serialize_food(food) -> dict:
    return {
        "food_id": food.id,
        "nome": food.name,
        "marca": food.brand,
        "kcal_por_100g": food.kcal_per_100g,
        "proteina_por_100g": food.protein_g_per_100g,
        "carboidrato_por_100g": food.carbs_g_per_100g,
        "gordura_por_100g": food.fat_g_per_100g,
    }


def _serialize_exercise(exercise: Exercise) -> dict:
    return {
        "exercise_id": exercise.id,
        "nome": exercise.name,
        "grupo_muscular_primario": exercise.primary_muscle_group.value,
        "equipamento": exercise.equipment.value,
        "dificuldade": exercise.difficulty.value,
    }


def execute_read_tool(db: Session, user_id: int, tool_name: str, tool_input: dict) -> dict:
    if tool_name == "buscar_alimento":
        # Base local (TACO + já cacheado) primeiro; sem match, tenta marcas ao
        # vivo no Open Food Facts — mesmo padrão usado no resto do app
        # (food_service.search_with_open_food_facts_fallback nunca existiu,
        # isso ficava dando erro toda vez que a IA tentava buscar comida).
        foods = food_service.search_local(db, tool_input["nome"], limit=10)
        if not foods:
            try:
                foods = food_service.search_brands_live(db, tool_input["nome"], limit=10)
            except Exception:
                foods = []
        return {"resultados": [_serialize_food(f) for f in foods]}

    if tool_name == "verificar_platos_e_deload":
        return {
            "platos": workout_insights_service.detect_plateaus(db, user_id),
            "deload": workout_insights_service.detect_deload_suggestion(db, user_id),
        }

    if tool_name == "listar_rotinas_ativas":
        rotinas = list(
            db.execute(
                select(Routine).where(Routine.user_id == user_id, Routine.is_archived.is_(False))
            ).scalars()
        )
        return {"rotinas": [{"id": r.id, "nome": r.name} for r in rotinas]}

    if tool_name == "buscar_exercicios":
        # Três filtros/ordens que faltavam e produziam treino ruim:
        # 1. category: sem isso a IA recebia alongamento e cardio como opção de
        #    exercício de rotina (um terço da base importada não é musculação).
        # 2. is_custom: exercício criado por OUTRO usuário não pode vazar aqui.
        # 3. order_by: não havia ORDER BY nenhum — com .limit(15) o banco
        #    devolvia os primeiros por ordem física (ids baixos = curados), que
        #    são justo os que não têm foto. Era por isso que o treino montado
        #    pelo chat vinha inteiro sem imagem. Agora quem tem foto vem antes.
        stmt = select(Exercise).where(
            Exercise.is_custom.is_(False),
            Exercise.category.in_(EXTENDED_STRENGTH_CATEGORIES),
        )
        if tool_input.get("nome"):
            stmt = stmt.where(Exercise.name.ilike(f"%{tool_input['nome']}%"))
        if tool_input.get("grupo_muscular"):
            stmt = stmt.where(
                Exercise.primary_muscle_group == MuscleGroup(tool_input["grupo_muscular"])
            )
        stmt = stmt.order_by(Exercise.video_url.is_(None), Exercise.id)
        exercises = list(db.execute(stmt.limit(25)).scalars())
        return {"resultados": [_serialize_exercise(e) for e in exercises]}

    if tool_name == "consultar_historico":
        dias = tool_input.get("dias", 7)
        since = datetime.now(timezone.utc) - timedelta(days=dias)

        if tool_input["tipo"] == "refeicoes":
            meals = list(
                db.execute(
                    select(MealLog)
                    .where(MealLog.user_id == user_id, MealLog.logged_at >= since)
                    .order_by(MealLog.logged_at)
                ).scalars()
            )
            resumo = []
            for meal in meals:
                items = list(
                    db.execute(
                        select(MealLogItem).where(MealLogItem.meal_log_id == meal.id)
                    ).scalars()
                )
                resumo.append(
                    {
                        "data_hora": meal.logged_at.isoformat(),
                        "kcal_total": sum(i.kcal for i in items),
                        "proteina_total": sum(i.protein_g for i in items),
                    }
                )
            return {"refeicoes": resumo}

        if tool_input["tipo"] == "agua":
            logs = list(
                db.execute(
                    select(WaterLog)
                    .where(WaterLog.user_id == user_id, WaterLog.logged_at >= since)
                    .order_by(WaterLog.logged_at)
                ).scalars()
            )
            return {"total_ml": sum(l.amount_ml for l in logs), "registros": len(logs)}

        if tool_input["tipo"] == "treinos":
            sessions = list(
                db.execute(
                    select(WorkoutSession)
                    .where(
                        WorkoutSession.user_id == user_id,
                        WorkoutSession.started_at >= since,
                        WorkoutSession.completed_at.is_not(None),
                    )
                    .order_by(WorkoutSession.started_at)
                ).scalars()
            )
            return {
                "sessoes": [
                    {
                        "data": s.started_at.isoformat(),
                        "rotina_id": s.routine_id,
                        "volume_total_kg": sum(set_.weight_kg * set_.reps for set_ in s.sets),
                    }
                    for s in sessions
                ]
            }

        if tool_input["tipo"] == "sono":
            logs = list(
                db.execute(
                    select(SleepLog)
                    .where(SleepLog.user_id == user_id, SleepLog.sleep_at >= since)
                    .order_by(SleepLog.sleep_at)
                ).scalars()
            )
            return {
                "registros": [
                    {
                        "data": l.sleep_at.isoformat(),
                        "duracao_minutos": int((l.wake_at - l.sleep_at).total_seconds() // 60),
                        "qualidade": l.quality,
                        "como_acordou": l.wake_feeling.value,
                    }
                    for l in logs
                ]
            }

        if tool_input["tipo"] == "peso":
            logs = list(
                db.execute(
                    select(WeightLog)
                    .where(WeightLog.user_id == user_id, WeightLog.recorded_at >= since)
                    .order_by(WeightLog.recorded_at)
                ).scalars()
            )
            return {
                "registros": [
                    {"data": l.recorded_at.isoformat(), "peso_kg": l.weight_kg} for l in logs
                ]
            }

    raise ValueError(f"Ferramenta de leitura desconhecida: {tool_name}")
