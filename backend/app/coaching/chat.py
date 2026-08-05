"""Camada conversacional do Coaching (Pro) — a IA que EXPLICA, tira dúvidas e,
agora, AGE: monta/troca treino, troca exercício e gera dieta personalizada.

O motor determinístico (metrics/engine) segue sendo a VERDADE que ancora a
conversa (o modelo não inventa número nem contradiz a análise). O que mudou é
que o coach tem FERRAMENTAS (app/coaching/chat_tools) pra realmente mexer no
treino e na dieta — cada uma chama código determinístico e seguro (arquivar em
vez de deletar, overlay reversível, dieta que só grava se a pessoa aplicar).
Sem chave da Anthropic, cai num resumo determinístico (sem ações).
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from app.ai.client import get_client
from app.coaching import chat_tools
from app.coaching.engine import WeeklyAnalysis
from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

_MODEL = settings.anthropic_model
_MAX_HISTORY = 8
_MAX_TOOL_ROUNDS = 5

# Teto de tokens de SAÍDA por rodada.
#
# Era 900, e 900 era a causa de uma falha grave e invisível: o modelo raciocina
# antes de responder, e esse raciocínio sai do MESMO orçamento. Medido com a
# mensagem real que quebrou ("tudo que comi hoje" + 7 alimentos em 4 blocos sem
# dizer qual refeição é qual): 5 tentativas de 5 gastaram as 900 inteiras só
# pensando — de 593 a 900 tokens de raciocínio — e a resposta terminava com
# `stop_reason="max_tokens"`, ZERO ferramenta executada e ZERO texto.
#
# O tamanho não é chute: uma mensagem ambígua como aquela pede ~900 de
# raciocínio, e registrar 4 refeições custa mais ~500 de chamadas de ferramenta.
# 4096 cobre isso com folga, e como o cobrado é o que se usa (não o teto), um
# teto largo não custa nada nas respostas curtas — que são a maioria.
_MAX_TOKENS = 4096
# Segunda tentativa quando ainda assim estourou. Um raciocínio que passa de 4096
# é raro o bastante pra valer uma tentativa a mais em vez de uma desculpa.
_MAX_TOKENS_RETRY = 8192


# Os alimentos rejeitados moram no questionário (é lista de apresentação, não
# regra de motor). Importado aqui só pra traduzir o valor gravado no rótulo.
def _food_dislikes_labels():
    from app.coaching.questionnaire import FOOD_DISLIKES

    return FOOD_DISLIKES


FOOD_DISLIKES_LABELS = _food_dislikes_labels()


def _perfil_lines(profile) -> list[str]:
    """TUDO que a pessoa respondeu no questionário. Antes o coach só recebia a
    análise numérica: quem respondeu "prefiro máquinas", "dor no ombro direito"
    ou "não como peixe" conversava com um coach que não sabia de nada disso —
    e por isso parecia não levar o questionário em conta.

    Os campos de TEXTO LIVRE saíram do questionário (ver `questionnaire`), então
    as linhas abaixo vêm das respostas estruturadas. Os textos antigos continuam
    sendo lidos quando existem: perfil que respondeu o questionário anterior não
    pode perder contexto que já tinha dado.
    """
    if profile is None:
        return []
    from app.coaching import training_brain

    def _rot(pares, valores) -> str | None:
        """Valores gravados -> rótulos que a pessoa viu na tela."""
        mapa = {p[0]: p[1] for p in pares}
        return ", ".join(mapa.get(v, v) for v in (valores or [])) or None

    def _um(pares, valor) -> str | None:
        return {p[0]: p[1] for p in pares}.get(valor) if valor else None

    prioridades = training_brain.resolve_weak_points(profile)
    itens: list[tuple[str, object]] = [
        ("Nível", getattr(getattr(profile, "experience_level", None), "value", None)),
        ("Tempo de treino", _um(training_brain.TRAINING_TIME, getattr(profile, "training_time", None))),
        ("Local de treino", getattr(getattr(profile, "training_location", None), "value", None)),
        ("Equipamento em casa", _rot(training_brain.HOME_EQUIPMENT, getattr(profile, "home_equipment", None))),
        ("Academia no horário dela",
         _um(training_brain.GYM_CROWDING, getattr(profile, "gym_crowding", None))),
        ("Dias por semana", getattr(profile, "training_days_per_week", None)),
        ("Tempo por sessão", getattr(profile, "session_length", None)),
        ("Esse tempo inclui cardio (musculação de verdade é 1 degrau menor)",
         "SIM" if getattr(profile, "session_includes_cardio", None) else None),
        ("Divisão preferida",
         _um(training_brain.SPLIT_PREFERENCES, getattr(profile, "split_preference", None))),
        ("Pode misturar superior e inferior no mesmo treino",
         "NÃO — nunca coloque os dois juntos numa sessão (bloqueia corpo inteiro e Torso/Limbs)"
         if getattr(profile, "avoid_mixing_upper_lower", None) else None),
        # A ORDEM importa: é ela que define quem recebe mais volume.
        ("Prioridades, em ordem",
         " > ".join(training_brain.WEAK_POINT_LABEL.get(m, m) for m in prioridades) or None),
        ("Pontos já desenvolvidos",
         _rot(training_brain.WEAK_POINTS, getattr(profile, "strong_points", None))),
        ("Lesão",
         _rot(training_brain.BODY_REGIONS, getattr(profile, "injury_regions", None))),
        ("Tem liberação profissional pra treinar a lesão",
         getattr(profile, "medical_clearance", None) if getattr(profile, "has_injury", None) else None),
        ("Dor", _rot(training_brain.BODY_REGIONS, getattr(profile, "pain_regions", None))),
        ("Intensidade da dor",
         _um(training_brain.PAIN_INTENSITY, getattr(profile, "pain_intensity", None))),
        ("Limitações", _rot(training_brain.LIMITATIONS, getattr(profile, "limitations", None))),
        ("Preferências de exercício",
         _rot(training_brain.EXERCISE_PREFS, getattr(profile, "exercise_prefs", None))),
        ("Prefere carga ou repetição",
         _um(training_brain.LOAD_PREFERENCE, getattr(profile, "load_preference", None))),
        ("Conforto perto da falha",
         _um(training_brain.FAILURE_COMFORT, getattr(profile, "failure_comfort", None))),
        ("Sabe estimar RIR",
         _um(training_brain.RIR_ACCURACY, getattr(profile, "rir_accuracy", None))),
        ("Técnica avançada",
         "pode usar" if training_brain.advanced_allowed(profile) else "SÓ SÉRIES NORMAIS — não sugira técnica"),
        ("Sono", _um(training_brain.SLEEP_QUALITY, getattr(profile, "sleep_quality", None))),
        ("Estresse", _um(training_brain.STRESS_LEVEL, getattr(profile, "stress_level", None))),
        ("Chega no treino seguinte",
         _um(training_brain.RECOVERY_BETWEEN, getattr(profile, "recovery_between", None))),
        ("Outro esporte", _um(training_brain.OTHER_SPORT, getattr(profile, "other_sport", None))),
        ("Restrições alimentares", ", ".join(getattr(profile, "dietary_restrictions", None) or []) or None),
        ("Não come", _rot(FOOD_DISLIKES_LABELS, getattr(profile, "food_dislikes_list", None))),
        # Respostas do questionário ANTIGO. Ficam por último e só aparecem em
        # quem as tinha preenchido — quem responder o novo nunca as verá.
        ("Lesões/limitações (texto antigo)", getattr(profile, "injuries_limitations", None)),
        ("Outras preferências (texto antigo)", getattr(profile, "exercise_preferences_text", None)),
        ("Histórico de treino (texto antigo)", getattr(profile, "training_history", None)),
        ("Não come (texto antigo)", getattr(profile, "food_dislikes", None)),
        ("Medicamentos/hormônios", getattr(profile, "medications", None)),
        ("Observações dela", getattr(profile, "extra_notes", None)),
    ]
    preenchidos = [f"- {rot}: {val}" for rot, val in itens if val not in (None, "", [])]
    if not preenchidos:
        return []
    return [
        "",
        "O QUE ELA TE CONTOU NO QUESTIONÁRIO (respeite CADA item; é o contrato com ela):",
        *preenchidos,
    ]


def _descobertas_lines(achados) -> list[str]:
    """As relações que o coach achou cruzando os módulos da pessoa.

    Entram como FATO OBSERVADO, não como teoria: cada uma já passou por
    tamanho de efeito, amostra nos dois grupos e estabilidade nas duas metades
    da janela (ver coaching/descobertas). O modelo pode citá-las, mas a regra
    de não inventar número continua valendo — o que está aqui é tudo que ele
    sabe sobre isso.
    """
    if not achados:
        return []
    linhas = [
        "",
        "O QUE EU JÁ CRUZEI DOS DADOS DELA (padrões do histórico DELA, não regra geral —",
        "fale deles como observação, nunca como causa provada):",
    ]
    for d in achados:
        extra = f" Sugestão ligada a isso: {d.acao}" if d.acao else ""
        linhas.append(f"- [{d.confianca}, n={d.n}] {d.frase}{extra}")
    return linhas


def _system_prompt(analysis: WeeklyAnalysis, profile=None, retrato=None, medido=None, achados=None) -> str:
    m = analysis.metrics
    linhas = [
        "Você é o coach pessoal do usuário dentro do app ATLAS (fitness/nutrição). "
        "Fala português do Brasil, tom de professor experiente: direto, acolhedor, motivador, "
        "SEM culpa ou vergonha, SEM jargão desnecessário.",
        "",
        "VOCÊ TEM AUTORIDADE sobre o treino e a dieta desta pessoa e pode AGIR pelas ferramentas:",
        "- montar_treino: monta/refaz o treino inteiro pelas preferências dela (arquiva o anterior).",
        "- ajustar_plano: muda uma PREFERÊNCIA (divisão do treino, dias por semana, tempo por treino, "
        "prioridade de músculo, periodização, cardio, técnicas avançadas, refeições por dia, restrição "
        "alimentar, alimento rejeitado) e refaz o que depende dela. É o equivalente a ela editar o "
        "questionário. Qualquer pedido do tipo 'não gosto de X', 'quero treinar N dias', 'quero priorizar "
        "Y' passa por AQUI.",
        "- trocar_exercicio: troca UM exercício citado por outro, de verdade, na rotina (edição definitiva). "
        "OBRIGATÓRIO: na primeira chamada a ferramenta devolve uma pergunta — repasse-a à pessoa "
        "('quer manter os registros anteriores de séries, repetições e cargas?') com as três opções "
        "(manter / começar novos / cancelar) e só troque depois da resposta dela. Nada é apagado em "
        "nenhum dos casos.",
        "- registrar_refeicao: registra no diário os alimentos que ela contar que comeu — chame sempre que "
        "ela mencionar o que comeu, mesmo sem pedir explicitamente pra registrar (ex.: 'comi arroz e frango "
        "no almoço' já é um pedido implícito de registro).",
        "- gerar_dieta: monta um cardápio que bate a meta de macros (a pessoa salva/aplica depois). As "
        "restrições e os alimentos que ela não come JÁ SÃO APLICADOS pelo motor — não precisa repassá-los.",
        "",
        "REGRA DE OURO DAS FERRAMENTAS — não negociável:",
        "- NUNCA diga que alterou/atualizou/refez alguma coisa sem ter CHAMADO a ferramenta e recebido "
        "\"ok\": true. Dizer 'pronto, atualizei sua rotina' sem ter chamado nada é a pior falha possível "
        "aqui — a pessoa vai treinar confiando numa mudança que não existe.",
        "- Se a ferramenta devolver \"erro\" ou \"nao_pude_aplicar\", conte isso à pessoa COM O MOTIVO e "
        "ofereça o caminho que existe (ex.: a divisão que ela quer precisa de mais dias por semana). "
        "Nunca disfarce uma recusa como sucesso.",
        "- Se a ferramenta devolver \"sem_efeito\" (nada mudou porque já estava assim), NÃO responda só "
        "'nada mudou' — reconecte com o que você mesmo já tinha explicado antes na conversa, pra não "
        "soar como uma contradição (ex.: 'É por isso que o upper/lower resolve: cada dia já é só "
        "superior OU só inferior, nunca os dois — e seu treino já roda assim, então não precisei mudar "
        "nada'). Se o que ela sente na prática (ex.: 'ainda sinto que mistura') não bate com o que a "
        "ferramenta diz, diga isso com honestidade em vez de insistir que está tudo certo.",
        "- Se ela pedir algo pra que você não tem ferramenta, diga onde ela faz isso no app.",
        "Use uma ferramenta SÓ quando a pessoa claramente pedir/contar aquilo. Depois de agir, confirme "
        "em 1-2 frases o que você fez.",
        "",
        "REGRAS INEGOCIÁVEIS:",
        "- A ANÁLISE abaixo foi calculada por um motor determinístico e é a VERDADE. "
        "Baseie a conversa nela. NUNCA invente números nem a contradiga.",
        "- Se não há dado suficiente pra afirmar algo, diga isso com honestidade.",
        "- NÃO dê diagnóstico médico. Sono/saúde viram sugestão de hábito, nunca laudo.",
        "- Ajuste de CALORIAS da meta você NÃO muda na conversa — direciona pro card 'Aplicar ajuste'. "
        "(Gerar um cardápio novo é diferente e pode.)",
        "- Respostas curtas (2 a 5 frases). Nada de listas gigantes.",
        "",
        f"ANÁLISE ATUAL (janela de {analysis.window_days} dias, objetivo: {analysis.goal or 'não definido'}):",
        f"- Resumo: {analysis.headline}",
        f"- Confiança: {analysis.confidence}",
        f"- Peso: {m.get('weight_kg')} kg, tendência {m.get('weight_trend_kg_per_week')} kg/sem "
        f"({m.get('weight_pct_per_week')}%/sem), {m.get('weight_points')} registros.",
        f"- Calorias: média {m.get('avg_kcal')} kcal/dia vs meta {m.get('goal_kcal')}; "
        f"proteína média {m.get('avg_protein_g')} g vs alvo {m.get('protein_target_g')} g; "
        f"{m.get('days_logged')} dias registrados.",
        f"- Treino: {m.get('sessions_per_week')} sessões/semana. Sono: {m.get('avg_sleep_hours')} h/noite.",
    ]
    if analysis.findings:
        linhas.append("- Achados e ajustes sugeridos:")
        for f in analysis.findings:
            prop = f" Sugestão: {f.proposal}" if f.proposal else ""
            linhas.append(f"  • [{f.severity}] {f.title}: {f.detail}{prop}")
    if analysis.data_gaps:
        linhas.append("- Faltam dados: " + " ".join(analysis.data_gaps))
    # Quem ela DISSE que é (questionário) e quem ela TEM SIDO (retrato do
    # histórico). O primeiro é contrato, o segundo é observação — e o segundo
    # fica mais forte a cada semana de uso.
    linhas += _perfil_lines(profile)
    if retrato is not None:
        linhas.append("")
        linhas += retrato.prompt_lines()
    # E o que foi MEDIDO nela — gasto energético real, tolerância a volume,
    # ritmo por série. Diferente do retrato (comportamento), estes números já
    # estão dentro das contas do plano, então o coach pode falar deles como
    # fato, não como impressão.
    if medido is not None:
        linhas += medido.prompt_lines()
    # E o que ele CRUZOU: relações entre módulos diferentes que só aparecem com
    # meses de registro (sono×treino, água×rendimento, comida×carga do dia
    # seguinte). É o que permite o coach responder "por que meu treino rendeu
    # mal hoje?" com o padrão real dela, em vez de com teoria genérica.
    linhas += _descobertas_lines(achados)
    return "\n".join(linhas)


def _fallback(analysis: WeeklyAnalysis, question: str) -> str:
    """SEM IA CONFIGURADA: devolve o essencial da análise, com honestidade.

    Este texto só cabe num caso — o app rodando sem chave da Anthropic. Ele
    ANUNCIA que a IA não está ativa, então usá-lo em qualquer outra situação
    mente pra uma pessoa que É Pro (o endpoint do chat exige Pro pra chegar
    aqui). Falha técnica tem resposta própria, ver `_erro_tecnico`.
    """
    partes = [analysis.headline]
    top = next((f for f in analysis.findings if f.severity in {"action", "attention"}), None)
    if top:
        partes.append(f"{top.title}: {top.detail}")
        if top.proposal:
            partes.append(f"Sugestão: {top.proposal}")
    partes.append(
        "Pra conversar mais a fundo sobre isso, a IA do Coaching precisa estar ativa no seu plano."
    )
    return " ".join(partes)


def _erro_tecnico(actions: list[dict]) -> str:
    """A resposta quando o coach FALHOU — que é diferente de o coach não existir.

    Os dois casos devolviam a mesma coisa: o resumo da análise da semana mais
    "a IA do Coaching precisa estar ativa no seu plano". Numa falha técnica isso
    são duas mentiras ao mesmo tempo — a IA está ativa, e a pessoa recebe a
    resposta de uma pergunta que ela não fez. Foi exatamente o que aconteceu com
    quem mandou o que tinha comido no dia e levou de volta uma análise de
    frequência de treino.

    Admitir a falha é pior de ler e melhor de confiar. E o que as ferramentas já
    executaram ANTES da falha vem junto: aquilo aconteceu de verdade no banco, e
    esconder isso faria a pessoa registrar tudo de novo, em duplicata.
    """
    if actions:
        return (
            " ".join(a["summary"] for a in actions)
            + " Depois disso deu um problema técnico aqui e eu perdi o fio da conversa — o que "
            "está acima já foi feito, não precisa repetir. Me chama de novo pro resto."
        )
    return (
        "Deu um problema técnico aqui e eu não consegui responder — nada foi alterado no seu "
        "plano nem no seu diário. Tenta de novo, por favor."
    )


def _rodada(client, system: str, msgs: list) -> object:
    """Uma rodada com o modelo, com o orçamento de saída ESCALANDO quando a
    resposta é cortada no meio.

    `stop_reason == "max_tokens"` significa resposta truncada, e o que vem junto
    é inútil das duas formas possíveis: ou é só raciocínio (nenhum texto, nenhuma
    ferramenta), ou é uma chamada de ferramenta pela metade — que NÃO pode ser
    executada, senão registra meia refeição.

    Antes esse caso não era tratado: o corte não casava com o `if` de ferramenta,
    o texto vinha vazio e a função caía no resumo determinístico como se o modelo
    tivesse escolhido não responder. Medido na mensagem real que quebrou, isso
    acontecia em 5 de 5 tentativas — o raciocínio sozinho consumia as 900 do teto
    antigo. Aqui o corte vira o que ele é: falta de espaço, então tenta de novo
    com mais espaço.
    """
    resp = None
    for teto in (_MAX_TOKENS, _MAX_TOKENS_RETRY):
        resp = client.messages.create(
            model=_MODEL, max_tokens=teto, system=system, tools=chat_tools.TOOLS, messages=msgs,
        )
        if resp.stop_reason != "max_tokens":
            return resp
        logger.warning("coach chat: resposta cortada com max_tokens=%s; tentando de novo", teto)
    return resp


def _result(answer: str, used_ai: bool, actions: list[dict], diet_plan: dict | None) -> dict:
    return {"answer": answer, "used_ai": used_ai, "actions": actions, "diet_plan": diet_plan}


def answer(
    db: Session, user: User, analysis: WeeklyAnalysis, question: str, history: list[dict] | None = None
) -> dict:
    """Responde ancorado na análise e, quando a pessoa pede, AGE (monta/troca
    treino, gera dieta) via ferramentas. Retorna {answer, used_ai, actions,
    diet_plan}. Sem chave, cai no resumo determinístico (sem ações)."""
    if not settings.anthropic_api_key.strip():
        return _result(_fallback(analysis, question), False, [], None)

    msgs: list = []
    for h in (history or [])[-_MAX_HISTORY:]:
        role = h.get("role")
        content = (h.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            msgs.append({"role": role, "content": content})
    msgs.append({"role": "user", "content": question.strip()})

    actions: list[dict] = []
    diet_plan: dict | None = None
    client = get_client()
    # Perfil + retrato comportamental + parâmetros medidos: o coach fala com
    # quem CONHECE a pessoa, e com números que ele mesmo mediu nela.
    from app.coaching import adaptive, user_model

    from app.services import goal_service

    profile = getattr(user, "profile", None)
    medido = adaptive.modelo(
        db, user.id, profile=profile, peso_kg=goal_service.get_latest_weight_kg(db, user.id)
    )
    from app.coaching import descobertas as _descobertas
    from app.core.usertime import profile_tz

    system = _system_prompt(
        analysis,
        profile=profile,
        retrato=user_model.aprender(db, user.id),
        medido=medido,
        achados=_descobertas.descobrir(db, user.id, profile_tz(profile)),
    )

    try:
        for _ in range(_MAX_TOOL_ROUNDS):
            resp = _rodada(client, system, msgs)
            tool_uses = [b for b in resp.content if getattr(b, "type", None) == "tool_use"]
            if resp.stop_reason == "tool_use" and tool_uses:
                msgs.append({"role": "assistant", "content": resp.content})
                results = []
                for tu in tool_uses:
                    # UMA ferramenta que explode não pode derrubar o turno
                    # inteiro. Sem este isolamento, um erro em "registrar
                    # refeição" fazia a conversa toda cair no `except` de baixo —
                    # inclusive as ferramentas que já tinham dado certo antes
                    # dela na mesma rodada, que ficavam sem ser contadas.
                    # Devolvendo o erro ao modelo, ele conta à pessoa o que não
                    # deu, que é a regra de ouro das ferramentas no prompt.
                    try:
                        out = chat_tools.run_tool(db, user, tu.name, dict(tu.input or {}))
                    except Exception:
                        logger.exception(
                            "coach chat: ferramenta %s falhou (user_id=%s)", tu.name, user.id
                        )
                        # A sessão pode ter ficado suja (ex.: falha no meio de um
                        # flush). Sem o rollback, a próxima ferramenta da mesma
                        # rodada falharia por arrasto.
                        db.rollback()
                        out = {"for_model": {"erro": (
                            "Falha técnica ao executar isso. NADA foi alterado. "
                            "Conte isso à pessoa em vez de dizer que deu certo."
                        )}}
                    if out.get("action"):
                        actions.append(out["action"])
                    if out.get("diet_plan") is not None:
                        diet_plan = out["diet_plan"]
                    results.append({
                        "type": "tool_result", "tool_use_id": tu.id,
                        "content": json.dumps(out.get("for_model", {}), ensure_ascii=False),
                    })
                msgs.append({"role": "user", "content": results})
                continue

            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
            if text:
                return _result(text, True, actions, diet_plan)
            # Sem texto: ou as ferramentas já disseram tudo, ou a resposta veio
            # truncada mesmo com o teto maior (`_rodada` já tentou duas vezes).
            # Nos dois casos o resumo determinístico da semana seria uma resposta
            # a uma pergunta que ninguém fez.
            if not actions:
                logger.warning(
                    "coach chat: rodada sem texto e sem ação (stop_reason=%s, user_id=%s)",
                    getattr(resp, "stop_reason", None), user.id,
                )
            return _result(_erro_tecnico(actions), bool(actions), actions, diet_plan)
        # Esgotou as rodadas de ferramenta sem o modelo fechar a conversa.
        logger.warning("coach chat: %s rodadas sem resposta final (user_id=%s)",
                       _MAX_TOOL_ROUNDS, user.id)
        return _result(_erro_tecnico(actions), bool(actions), actions, diet_plan)
    except Exception:
        # Erro de rede/modelo: a tela nunca quebra. Mas o erro PRECISA aparecer
        # no log — este bloco era um `except` mudo, e foi por isso que uma falha
        # em produção só virou diagnóstico quando um usuário mandou print da
        # conversa. Mantém o que já foi executado.
        logger.exception("coach chat: turno falhou (user_id=%s)", user.id)
        return _result(_erro_tecnico(actions), False, actions, diet_plan)
