"""Loop de orquestração do chat de nutrição: ferramentas de leitura são
executadas e realimentadas ao modelo; a primeira ferramenta de escrita
encontrada interrompe o loop e vira uma proposta para o app confirmar."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.client import get_client
from app.ai.system_prompt import ASSISTANT_SYSTEM_PROMPT
from app.ai.tools import TOOL_DEFINITIONS, WRITE_TOOL_NAMES, execute_read_tool
from app.core.config import settings
from app.models.chat_message import ChatMessage, ChatRole
from app.models.user_profile import UserProfile
from app.models.weight_log import WeightLog

# Montar um treino/dieta personalizado completo pode exigir várias buscas de
# exercício/alimento antes da proposta final — 6 era curto demais pra isso e
# cortava o plano no meio (o usuário via "vou montar..." sem a proposta vir).
MAX_TOOL_ITERATIONS = 14
HISTORY_MESSAGE_LIMIT = 20

# Cache de prompt da Anthropic. As ferramentas + o system prompt fixo são
# ~6.9k tokens IDÊNTICOS em toda chamada, e o loop abaixo repete a chamada até
# MAX_TOOL_ITERATIONS vezes por mensagem do usuário — sem cache, um pedido que
# faz 5 buscas paga ~34k tokens só de texto repetido. Marcado o breakpoint, a
# releitura custa ~10% do preço de entrada.
#
# É casamento de PREFIXO: qualquer byte diferente antes do breakpoint invalida
# tudo dali pra frente. A ordem de renderização é tools -> system -> messages,
# então o breakpoint no bloco fixo do system cobre também as ferramentas, e o
# bloco fixo é igual pra TODOS os usuários (o cache é compartilhado entre eles).
CACHE_BREAKPOINT = {"type": "ephemeral"}


def _load_history_as_messages(db: Session, user_id: int) -> list[dict]:
    rows = list(
        db.execute(
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id)
            .order_by(ChatMessage.id.desc())  # ordem de inserção (created_at empata no mesmo turno)
            .limit(HISTORY_MESSAGE_LIMIT)
        ).scalars()
    )
    rows.reverse()
    return [{"role": row.role.value, "content": row.content} for row in rows]


def _profile_context(db: Session, user_id: int) -> str:
    """Resumo do perfil já cadastrado — injetado no prompt pra IA não precisar
    reperguntar o que o onboarding/perfil já coletou (regra: fácil, sem
    fricção)."""
    profile = db.execute(select(UserProfile).where(UserProfile.user_id == user_id)).scalar_one_or_none()
    if profile is None:
        return ""
    weight = db.execute(
        select(WeightLog).where(WeightLog.user_id == user_id).order_by(WeightLog.recorded_at.desc()).limit(1)
    ).scalar_one_or_none()
    lines = [
        f"- Objetivo: {profile.goal.value}",
        f"- Sexo biológico: {profile.biological_sex.value} · idade: {profile.age}",
        f"- Altura: {profile.height_cm}cm"
        + (f" · peso mais recente: {weight.weight_kg}kg" if weight else " · peso ainda não registrado"),
        f"- Nível de experiência: {profile.experience_level.value}",
        f"- Local de treino: {profile.training_location.value} · nível de atividade: {profile.activity_level.value}",
        f"- Dias disponíveis: {', '.join(profile.available_days) if profile.available_days else 'não informado'}",
        f"- Restrições alimentares: {', '.join(profile.dietary_restrictions) if profile.dietary_restrictions else 'nenhuma informada'}",
        f"- Lesões/limitações: {profile.injuries_limitations or 'nenhuma informada'}",
    ]
    return "\n".join(lines)


# Campo que deveria ser array em cada tool de escrita "em lote".
_ARRAY_FIELD = {
    "criar_treino_personalizado": "rotinas",
    "criar_dieta_personalizada": "refeicoes",
}


def _normalize_tool_input(tool_name: str, tool_input: dict) -> dict:
    """Corrige uma malformação ocasional do modelo em respostas grandes: o
    array principal (rotinas/refeicoes) vem como STRING contendo o JSON, às
    vezes com um campo irmão (ex: substituir_existentes) colado depois do
    array dentro dessa mesma string, em vez de estruturado no schema pedido.
    Sem isso o app recebe uma proposta que não bate com o formato esperado."""
    field = _ARRAY_FIELD.get(tool_name)
    if not field or not isinstance(tool_input.get(field), str):
        return tool_input

    fixed = dict(tool_input)
    raw = fixed[field].strip()
    depth = 0
    end = None
    for i, ch in enumerate(raw):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    try:
        parsed = json.loads(raw[:end] if end else raw)
    except json.JSONDecodeError:
        return tool_input  # não deu pra recuperar — segue como veio

    fixed[field] = parsed
    if end:
        tail = raw[end:].strip().lstrip(",").strip()
        if tail:
            try:
                for k, v in json.loads("{" + tail + "}").items():
                    fixed.setdefault(k, v)
            except json.JSONDecodeError:
                pass
    return fixed


def run_chat_turn(
    db: Session,
    user_id: int,
    user_message: str,
    context_module: str | None = None,
    model: str | None = None,
) -> dict:
    messages = _load_history_as_messages(db, user_id)
    messages.append({"role": "user", "content": user_message})

    # O system vai em DOIS blocos por causa do cache (ver CACHE_BREAKPOINT):
    # o texto fixo primeiro, o que varia por pessoa/tela depois. Se o perfil
    # fosse concatenado no fim do prompt como antes, cada peso novo registrado
    # mudaria os bytes do bloco inteiro e o cache nunca pegaria.
    system_blocks: list[dict] = [
        {"type": "text", "text": ASSISTANT_SYSTEM_PROMPT, "cache_control": CACHE_BREAKPOINT}
    ]
    volatil: list[str] = []
    profile_ctx = _profile_context(db, user_id)
    if profile_ctx:
        volatil.append(f"## Perfil já cadastrado da pessoa\n{profile_ctx}")
    if context_module:
        volatil.append(f"## Contexto atual\nA pessoa abriu o chat a partir da tela de {context_module}.")
    if volatil:
        system_blocks.append({"type": "text", "text": "\n\n".join(volatil)})

    client = get_client()
    proposed_action: dict | None = None
    reply_text = ""
    cached_block: dict | None = None  # breakpoint móvel no fim das mensagens

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=model or settings.anthropic_model,
            # Propor um dia inteiro de dieta ou um treino de vários dias num só
            # tool_use pode gerar um JSON grande — 1024 truncava a chamada no
            # meio (stop_reason="max_tokens"), fazendo a proposta sumir.
            max_tokens=4096,
            system=system_blocks,
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
            proposed_action = {
                "tool": write_block.name,
                "input": _normalize_tool_input(write_block.name, write_block.input),
            }
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
        # Segundo breakpoint, andando junto com o fim da conversa: cada volta do
        # loop reenvia todo o histórico + os resultados de busca já trazidos (que
        # ficam grandes — buscar_exercicios por grupo muscular traz vários de uma
        # vez). Assim a volta seguinte relê isso do cache em vez de reprocessar.
        # Só o mais recente fica marcado (o limite é 4 por chamada); a entrada já
        # escrita continua válida pra ser lida mesmo sem a marca.
        if cached_block is not None:
            cached_block.pop("cache_control", None)
        tool_results[-1]["cache_control"] = CACHE_BREAKPOINT
        cached_block = tool_results[-1]
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
