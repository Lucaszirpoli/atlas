"""REGRA DE COERÊNCIA GLOBAL — as 8 perguntas, viradas em checagem automática.

A regra mestra fecha com uma exigência explícita: antes de entregar qualquer
programa, validar oito coisas, e "se qualquer resposta for negativa, o treino
deve ser reestruturado antes de ser entregue".

Cada função aqui é uma daquelas perguntas. `review()` roda todas e devolve os
problemas em texto — vazio significa treino aprovado.

As perguntas 1 e 7 (volume planejado e compatibilidade com a recuperação) são
respondidas por quem monta o volume, não aqui: `volume_landmarks.weekly_plan`
decide as séries semanais por músculo e `workout_builder` fecha o que falta com
exercício novo. O que este módulo cobra é a ESTRUTURA: cobertura, equilíbrio,
redundância, ordem e fidelidade da função de cada vaga.

Achado aqui NÃO é warning decorativo: `workout_builder` tenta reparar o que é
reparável (lacuna de cobertura vira exercício novo) e só entrega depois.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from app.ai.exercise_taxonomy import (
    DELT_POSTERIOR,
    ORDER_MINOR,
    REQUIRED_REGIONS,
    Pattern,
    order_class_for_pattern,
)
from app.models.exercise import MuscleGroup

# Quanto os dois lados de um par podem desequilibrar antes de virar problema.
# 1 vaga de diferença é normal (número ímpar de exercícios); 2 já é um treino
# torto de propósito.
TOLERANCIA_EQUILIBRIO = 2
_TOLERANCIA_EQUILIBRIO = TOLERANCIA_EQUILIBRIO

def _padrao(slot) -> Pattern | None:
    if not slot.pattern:
        return None
    try:
        return Pattern(slot.pattern)
    except ValueError:
        return None


def _musculos_do_plano(plan) -> set[MuscleGroup]:
    out: set[MuscleGroup] = set()
    for s in plan.sessions:
        for sl in s.slots:
            try:
                out.add(MuscleGroup(sl.muscle_group))
            except ValueError:
                pass
    return out


# --- 6) Cobertura regional (Princípio 6) -----------------------------------
def regioes_descobertas(plan) -> list[tuple[MuscleGroup, str]]:
    """Regiões que a SEMANA deveria cobrir e não cobriu.

    "Não basta trabalhar um músculo": peito precisa de clavicular e esternal,
    costas de dorsais e upper back, ombro de lateral e posterior (o anterior vem
    dos supinos), posterior de coxa das duas funções — extensão de quadril e
    flexão de joelho. Só cobra de músculo que o treino REALMENTE treina: quem
    não faz peito na semana não é reprovado por não ter peito clavicular.
    """
    por_musculo: dict[MuscleGroup, set[str]] = defaultdict(set)
    for s in plan.sessions:
        for sl in s.slots:
            try:
                m = MuscleGroup(sl.muscle_group)
            except ValueError:
                continue
            if sl.region:
                por_musculo[m].add(sl.region)

    faltando: list[tuple[MuscleGroup, str]] = []
    treinados = _musculos_do_plano(plan)
    for musculo, exigidas in REQUIRED_REGIONS.items():
        if musculo not in treinados:
            continue
        for regiao in exigidas:
            if regiao not in por_musculo[musculo]:
                faltando.append((musculo, regiao))
    return faltando


# --- 2) Equilíbrio empurrar x puxar ----------------------------------------
def _direcao(slot) -> str | None:
    """'empurrar', 'puxar' ou None (não entra na conta).

    Contar só o PADRÃO não serve: num dia de pull, o pullover é puxada de
    verdade, mas é articulação única (padrão isolamento), então o dia parecia ter
    2 puxadas contra 3 empurradas do dia de push — desequilíbrio que não existe.
    Aqui vale a direção do movimento, não a contagem de articulações.

    Fora da conta de propósito: deltoide lateral (abdução, não é nem um nem
    outro) e os braços. Bíceps e tríceps recebem tanto volume indireto dos
    compostos que contá-los faria a soma responder por eles, e não pelo tronco —
    que é o que a pergunta quer saber.
    """
    try:
        musculo = MuscleGroup(slot.muscle_group)
    except ValueError:
        return None
    if musculo is MuscleGroup.CHEST:
        return "empurrar"
    if musculo is MuscleGroup.BACK:
        return "puxar"
    if musculo is MuscleGroup.SHOULDERS:
        if _padrao(slot) is Pattern.PUSH_V:
            return "empurrar"
        if slot.region == DELT_POSTERIOR:
            return "puxar"
    return None


def direcao_do_slot(slot) -> str | None:
    """'empurrar', 'puxar' ou None — pública porque quem MEXE no plano (o
    preenchimento de volume do workout_builder) precisa saber o efeito de tirar
    uma vaga antes de tirar, e não depois que o validador já reprovou."""
    return _direcao(slot)


def desequilibrio_empurrar_puxar(plan) -> int:
    """Diferença (empurrar - puxar) na semana. 0 é o ideal; o sinal diz pra que
    lado está torto."""
    contagem = Counter(
        d for s in plan.sessions for sl in s.slots if (d := _direcao(sl)) is not None
    )
    return contagem["empurrar"] - contagem["puxar"]


# --- 3) Equilíbrio joelho x quadril ----------------------------------------
def desequilibrio_joelho_quadril(plan) -> int:
    """Diferença (dominante de joelho - dominante de quadril) na semana.

    Conta só os dois padrões que a pergunta nomeia: agachar/empurrar perna
    (KNEE) contra dobradiça de quadril (HIP). A FLEXÃO DE JOELHO fica fora —
    mesa flexora é trabalho de posterior, mas não é "dominância de quadril", e
    contá-la do lado do quadril inflava a soma (todo dia de perna tem uma) e
    reprovava treino correto, inclusive o LOWER A de referência do usuário.

    O risco de deixá-la fora — um treino cheio de agachamento e flexora, sem
    nenhuma extensão de quadril — já é pego pela cobertura regional, que exige
    'posterior (extensão de quadril)' na semana.
    """
    contagem = Counter(_padrao(sl) for s in plan.sessions for sl in s.slots)
    return contagem[Pattern.KNEE] - contagem[Pattern.HIP]


# --- 4) Redundância de padrões (Princípio 4) -------------------------------
def redundancias(plan) -> list[tuple[str, str, int]]:
    """(foco, função, quantas vezes) pra toda função repetida além do aceitável.

    O teto é 2 pra qualquer função, e 3 é que vira problema. Não é frouxidão: o
    exemplo ruim da própria spec são TRÊS exercícios de mesma função (supino reto
    barra -> supino reto Smith -> chest press), e o "segundo estímulo para o
    grupo prioritário" que ela manda incluir produz legitimamente o segundo
    ("Leg Press após Hack Squat" — os dois são dominante de joelho de
    quadríceps, sem distinção de região possível). Nos isoladores de músculo
    pequeno o segundo também é volume legítimo (duas roscas num dia de pull).
    """
    achados: list[tuple[str, str, int]] = []
    for s in plan.sessions:
        contagem: Counter[tuple[str, str | None]] = Counter()
        for sl in s.slots:
            contagem[(sl.pattern or "?", sl.region)] += 1
        for (padrao, regiao), n in contagem.items():
            if n > 2:
                achados.append((s.focus, f"{padrao} / {regiao}", n))
    return achados


# --- 5) Ordem preserva desempenho -----------------------------------------
def problemas_de_ordem(plan) -> list[str]:
    """A sessão abre com movimento pesado e fecha com músculo menor.

    Duas invariantes, e só duas — as que os treinos de referência do usuário
    respeitam. A regra "nenhum composto depois de um isolado" NÃO vale: o LOWER A
    de referência tem hip thrust (composto) na 5ª posição, depois da mesa flexora
    (isolador), e está certo — o hip thrust não disputa fadiga com o que veio
    antes.

    A abertura com isolador tem UMA exceção, e ela é declarada na vaga
    (`priority_opener`): quando o músculo prioritário da pessoa não tem composto
    próprio — braço — abrir com o isolador dele é o que priorizar significa. Sem
    essa exceção, marcar bíceps como ponto fraco não mudava nada na ordem do
    treino, porque a única promoção possível era entre compostos.
    """
    problemas: list[str] = []
    for s in plan.sessions:
        if not s.slots:
            continue
        if not s.slots[0].is_compound and not getattr(s.slots[0], "priority_opener", False):
            problemas.append(
                f"Sessão '{s.focus}' abre com '{s.slots[0].exercise_name}', que não é composto — "
                "o movimento prioritário perde desempenho se não vier primeiro."
            )
        vi_menor: str | None = None
        for sl in s.slots:
            ordem = order_class_for_pattern(_padrao(sl))
            if ordem >= ORDER_MINOR:
                vi_menor = sl.exercise_name
            elif vi_menor is not None:
                problemas.append(
                    f"Sessão '{s.focus}': '{sl.exercise_name}' veio depois de '{vi_menor}' "
                    "(músculo menor tem que fechar o treino)."
                )
                break
    return problemas


# --- 8) A vaga recebeu um exercício da função que ela pedia ----------------
def vagas_sem_funcao(plan) -> list[str]:
    """Vaga sem exercício ou sem padrão registrado.

    Por construção o motor só coloca na vaga um exercício do padrão que ela
    pede, então isto aqui pega o caso em que a base não tinha NADA que servisse
    (a vaga é descartada) ou em que alguém montou a vaga fora do motor.
    """
    problemas: list[str] = []
    for s in plan.sessions:
        for sl in s.slots:
            if sl.exercise_id is None:
                problemas.append(f"Sessão '{s.focus}': vaga '{sl.role or sl.muscle_group}' sem exercício.")
            elif not sl.pattern:
                problemas.append(
                    f"Sessão '{s.focus}': '{sl.exercise_name}' entrou sem padrão de movimento definido."
                )
    return problemas


def sessoes_vazias(plan) -> list[str]:
    return [f"Sessão '{s.focus}' ficou sem exercício nenhum." for s in plan.sessions if not s.slots]


# --- 6b) Nenhum músculo da divisão SUMIU da semana -------------------------
def musculos_perdidos(plan) -> list[MuscleGroup]:
    """Músculos que a divisão escolhida ia treinar e a semana entregue não treina.

    Este é o buraco por onde o bug passou. `regioes_descobertas` só cobra região
    "de músculo que o treino REALMENTE treina" — o que é certo pra não reprovar
    quem não faz peito por não ter peito clavicular, e é exatamente o que torna um
    músculo ZERADO invisível: sem vaga nenhuma, ele não é treinado, então nada é
    cobrado dele. Um treino de 4 dias sem uma única panturrilha na semana passava
    como coerente.

    Aqui a referência não é o treino entregue, é o BLUEPRINT do dia — o desenho
    que a divisão prometia. Sumir daí é sempre uma perda: ou o corte por tempo
    exagerou, ou a base não tinha exercício que servisse, ou uma restrição
    esvaziou o músculo inteiro. Nos três casos é coisa pra sair declarada em vez
    de silenciosa (no último, `restriction_notes` explica o porquê ao lado).
    """
    from app.ai import session_blueprints as bp

    previstos = {vaga.muscle for s in plan.sessions for vaga in bp.blueprint_for(s.focus)}
    return sorted(previstos - _musculos_do_plano(plan), key=lambda m: m.value)


def review(plan, *, method=None) -> list[str]:
    """As 8 perguntas, de uma vez. Lista vazia = treino aprovado."""
    problemas: list[str] = []

    problemas += sessoes_vazias(plan)
    problemas += vagas_sem_funcao(plan)

    for musculo in musculos_perdidos(plan):
        problemas.append(
            f"{musculo.value}: a divisão treina esse músculo, mas a semana entregue "
            "ficou sem nenhum exercício dele."
        )

    for musculo, regiao in regioes_descobertas(plan):
        problemas.append(
            f"{musculo.value}: a semana não cobre '{regiao}' — falta um exercício dessa região."
        )

    d = desequilibrio_empurrar_puxar(plan)
    if abs(d) >= _TOLERANCIA_EQUILIBRIO:
        lado = "empurrar" if d > 0 else "puxar"
        problemas.append(
            f"Desequilíbrio empurrar x puxar na semana: {abs(d)} vagas a mais de {lado}."
        )

    d = desequilibrio_joelho_quadril(plan)
    if abs(d) >= _TOLERANCIA_EQUILIBRIO:
        lado = "dominante de joelho" if d > 0 else "dominante de quadril / posterior"
        problemas.append(
            f"Desequilíbrio joelho x quadril na semana: {abs(d)} vagas a mais de {lado}."
        )

    for foco, funcao, n in redundancias(plan):
        problemas.append(
            f"Sessão '{foco}': {n} exercícios cumprindo a mesma função ({funcao}) — volume desperdiçado."
        )

    problemas += problemas_de_ordem(plan)

    if method is not None and method.days_per_week and plan.days_per_week not in method.days_per_week:
        problemas.append(
            f"{plan.days_per_week} dias não é uma frequência suportada "
            f"({', '.join(map(str, sorted(method.days_per_week)))})."
        )

    return problemas
