"""Loop de orquestração do chat de nutrição: ferramentas de leitura são
executadas e realimentadas ao modelo; a primeira ferramenta de escrita
encontrada interrompe o loop e vira uma proposta para o app confirmar."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import get_client
from app.ai.system_prompt import NUTRITION_SYSTEM_PROMPT
from app.ai.tools import TOOL_DEFINITIONS, WRITE_TOOL_NAMES, execute_read_tool
from app.core.config import settings
from app.models.chat_message import ChatMessage, ChatRole

MAX_TOOL_ITERATIONS = 6
HISTORY_MESSAGE_LIMIT = 20


def _load_history_as_messages(db: Session, user_id: int) -> list[dict]:
    rows = list(
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(HISTORY_MESSAGE_LIMIT)
        ).scalars()
    )
    rows.reverse()
    return [{"role": row.role.value, "content": row.content} for row in rows]


def run_chat_turn(db: Session, user_id: int, user_message: str) -> dict:
    messages = _load_history_as_messages(db, user_id)
    messages.append({"role": "user", "content": user_message})

    client = get_client()
    proposed_action: dict | None = None
    reply_text = ""

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            system=NUTRITION_SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        text_blocks = [b.text for b in response.content if b.type == "text"]
        reply_text = "\n".join(text_blocks) if text_blocks else reply_text
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if response.stop_reason != "tool_use" or not tool_use_blocks:
            break

        write_block = next((b for b in tool_use_blocks if b.name in WRITE_TOOL_NAMES), None)
        if write_block is not None:
            proposed_action = {"tool": write_block.name, "input": write_block.input}
            if not reply_text:
                reply_text = "Preparei isso para você — confirma antes de eu salvar?"
            break

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in tool_use_blocks:
            try:
                result = execute_read_tool(db, user_id, block.name, block.input)
            except Exception as exc:
                result = {"erro": str(exc)}
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        messages.append({"role": "user", "content": tool_results})
    else:
        if not reply_text:
            reply_text = "Não consegui concluir o raciocínio agora — tenta reformular a pergunta?"

    db.add(ChatMessage(user_id=user_id, role=ChatRole.USER, content=user_message))
    db.add(
        ChatMessage(
            user_id=user_id,
            role=ChatRole.ASSISTANT,
            content=reply_text,
            proposed_action=proposed_action,
        )
    )
    db.commit()

    return {"reply": reply_text, "proposed_action": proposed_action}
