"""Reconhecimento de refeição por foto. Sempre retorna uma estimativa a
confirmar pelo usuário — nunca grava nada sozinho (a margem de erro real de
reconhecimento por IA em pratos compostos é de ~20-27%, espec. 1.3)."""

import json
import re

from sqlalchemy.orm import Session

from app.ai.client import get_client
from app.core.config import settings
from app.services import food_service


def _extract_json(text: str) -> dict:
    """Extrai o JSON da resposta do modelo de forma robusta.

    ISTO é o que fazia a foto "nunca reconhecer nada": o modelo costuma
    embrulhar o JSON em cerca de markdown (```json ... ```) mesmo pedindo "APENAS
    JSON", e o json.loads cru falhava -> lista vazia SEMPRE. Aqui a gente tira a
    cerca e, se ainda falhar, pega o primeiro objeto {...} do texto."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"itens": []}

VISION_PROMPT = """\
Analise a foto de uma refeição brasileira. Identifique cada alimento visível \
e estime a quantidade em gramas de forma realista (porções caseiras comuns). \
Responda APENAS com um JSON válido, sem texto antes ou depois, no formato:
{"itens": [{"nome": "arroz branco", "quantidade_g": 150, "confianca": "alta"}]}
confianca deve ser "alta", "media" ou "baixa". Se não conseguir identificar \
nada com confiança, retorne uma lista vazia."""


def analyze_meal_photo(db: Session, image_base64: str, media_type: str) -> dict:
    client = get_client()
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_base64},
                    },
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
    )

    text = "".join(b.text for b in response.content if b.type == "text")
    parsed = _extract_json(text)

    itens = []
    for item in parsed.get("itens", []):
        matches = food_service.search_local(db, item["nome"], limit=1)
        itens.append(
            {
                "nome_identificado": item["nome"],
                "food_id": matches[0].id if matches else None,
                "quantidade_estimada_g": item.get("quantidade_g", 100),
                "confianca": item.get("confianca", "media"),
            }
        )

    return {
        "itens": itens,
        "aviso": (
            "Estimativa por IA — a margem de erro em pratos compostos pode ser "
            "significativa. Confira e ajuste as quantidades antes de salvar."
        ),
    }
