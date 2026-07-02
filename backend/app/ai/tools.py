"""Definições das ferramentas (function calling) do assistente, no formato
esperado pela Anthropic API, restritas ao modo NUTRIÇÃO (Fase 3).

Ferramentas de leitura são executadas dentro do loop do orquestrador.
Ferramentas de escrita (WRITE_TOOL_NAMES) NUNCA são executadas pelo backend
automaticamente — o orquestrador intercepta a chamada e devolve uma proposta
para o app confirmar explicitamente (espec. 3.6)."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.meal import MealLog, MealLogItem
from app.models.water_log import WaterLog
from app.models.weight_log import WeightLog
from app.services import food_service

WRITE_TOOL_NAMES = {"registrar_refeicao", "atualizar_peso", "ajustar_meta_calorica"}

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
        "description": "Consulta o histórico recente do usuário em nutrição, água ou peso.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": ["refeicoes", "agua", "peso"]},
                "dias": {"type": "integer", "description": "Quantos dias olhar para trás", "default": 7},
            },
            "required": ["tipo"],
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


def execute_read_tool(db: Session, user_id: int, tool_name: str, tool_input: dict) -> dict:
    if tool_name == "buscar_alimento":
        foods = food_service.search_with_open_food_facts_fallback(db, tool_input["nome"], limit=10)
        return {"resultados": [_serialize_food(f) for f in foods]}

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
