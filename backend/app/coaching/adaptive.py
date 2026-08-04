"""O que o coach aprende COM OS DADOS e devolve pro motor.

A diferença pro `user_model.py`: aquele monta um RETRATO do comportamento e
entrega pro chat verbalizar. Este produz NÚMEROS que entram nas contas — a meta
calórica, o volume semanal, o passo de carga, a duração estimada da sessão.

Por que isso existia como buraco: todos os parâmetros do motor vinham do
questionário (nível, atividade, recuperação) — respostas dadas UMA vez, sobre si
mesmo, por alguém que ainda não tinha treinado no app. A pessoa treinava seis
meses e o coach continuava operando com as mesmas suposições do primeiro dia.
Ela registrava tudo, e nada daquilo voltava pra ela em forma de decisão.

A regra aqui é: **o questionário é a hipótese inicial; o histórico é a
evidência**. Conforme a evidência chega, ela pesa mais — nunca 100%, porque um
histórico curto ou um mês atípico não podem apagar a base.

Cinco regras que valem pra TODO parâmetro deste arquivo, e que são o que separa
"aprender" de "chutar com número novo toda semana":

1. **Piso de evidência.** Abaixo dele o parâmetro não age. `confianca` vira
   "nenhuma" e quem chama usa o valor da fórmula.
2. **Mistura, não substituição.** O valor usado é `fórmula × (1-p) + observado ×
   p`, com `p` crescendo com a confiança e nunca chegando a 1.
3. **Limites duros.** Cada parâmetro tem faixa própria. Um dado estranho (a
   pessoa esqueceu de registrar uma semana) não pode virar prescrição absurda.
4. **Passo máximo.** O valor não pode saltar de uma leitura pra outra. Coach que
   muda tudo toda semana não é adaptativo, é instável.
5. **Evidência junto.** Todo valor carrega a frase que explica de onde saiu. Um
   número que o coach não sabe justificar não deveria mudar o treino de ninguém.

Determinístico: o mesmo histórico dá sempre o mesmo resultado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.routine import RoutineExercise
from app.models.workout_session import SetType, WorkoutSession, WorkoutSetLog

# ---------------------------------------------------------------------------
# O resultado de um aprendizado
# ---------------------------------------------------------------------------

NENHUMA, BAIXA, MEDIA, ALTA = "nenhuma", "baixa", "media", "alta"

# Quanto o observado pesa contra a fórmula, por confiança. Nunca 1.0: o coach
# não entrega o volante inteiro pra uma janela de algumas semanas.
PESO_POR_CONFIANCA: dict[str, float] = {NENHUMA: 0.0, BAIXA: 0.35, MEDIA: 0.60, ALTA: 0.80}


@dataclass(frozen=True)
class Aprendido:
    """Um parâmetro que o coach deduziu do histórico.

    `valor` é o observado puro. Quem consome chama `aplicar()` pra misturá-lo
    com a fórmula — assim o peso da evidência mora num lugar só.
    """

    chave: str
    valor: float
    confianca: str
    evidencia: str
    n: int

    @property
    def usar(self) -> bool:
        return self.confianca != NENHUMA

    @property
    def peso(self) -> float:
        return PESO_POR_CONFIANCA.get(self.confianca, 0.0)

    def aplicar(self, formula: float) -> float:
        """Mistura o observado com o valor da fórmula, pelo peso da confiança."""
        if not self.usar:
            return formula
        return formula * (1.0 - self.peso) + self.valor * self.peso

    def to_dict(self) -> dict:
        return {
            "chave": self.chave,
            "valor": round(self.valor, 2),
            "confianca": self.confianca,
            "evidencia": self.evidencia,
            "n": self.n,
        }


def _limitar(v: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(v, maximo))


def _passo_maximo(anterior: float | None, novo: float, fracao: float) -> float:
    """Regra 4: o parâmetro não salta. Sem valor anterior, aceita o novo."""
    if anterior is None or anterior <= 0:
        return novo
    teto, piso = anterior * (1 + fracao), anterior * (1 - fracao)
    return _limitar(novo, piso, teto)


# ---------------------------------------------------------------------------
# 1. ENERGIA OBSERVADA — quantas calorias ESTA pessoa realmente gasta
# ---------------------------------------------------------------------------
#
# É o aprendizado de maior valor do app, e o mais fácil de justificar: se ela
# come 2.400 kcal/dia e o peso não se move, a manutenção dela É 2.400 — não
# importa o que Mifflin-St Jeor diz. A balança é o juiz.
#
#     TDEE_observado = kcal_médio_registrado − (Δkg_por_semana × 7700 / 7)
#
# Um efeito colateral que é FEATURE, não bug: quem sub-registra a comida (todo
# mundo sub-registra um pouco) produz um TDEE observado menor que o real. E está
# certo — a meta sai na mesma moeda em que ela registra. O que importa é a
# trajetória do peso, e essa vem da balança, que não mente.

KCAL_POR_KG = 7700.0

# Piso de evidência. Peso precisa de tendência confiável (regressão sobre vários
# pontos, num intervalo grande o bastante); comida precisa de dias fechados.
MIN_DIAS_COMIDA = 10
MIN_PONTOS_PESO = 4
MIN_JANELA_PESO_DIAS = 14

# Limites duros: o observado não pode ficar fora desta faixa em torno da
# fórmula. Fora disso é muito mais provável ser registro furado que metabolismo
# excepcional — e o coach prefere errar pro lado de não fazer besteira.
TDEE_MIN_FATOR = 0.65
TDEE_MAX_FATOR = 1.45

# Passo máximo entre uma leitura e a seguinte.
TDEE_PASSO = 0.12


def energia_observada(
    *,
    kcal_medio: float | None,
    kcal_confianca: str,
    dias_comida: int,
    trend_kg_semana: float | None,
    pontos_peso: int,
    janela_peso_dias: int,
    tdee_formula: float,
    tdee_anterior: float | None = None,
) -> Aprendido:
    """O gasto energético desta pessoa, lido do que ela comeu e do que a balança
    fez. Recebe números já calculados (metrics) em vez de ir ao banco: fica
    testável sem subir banco nenhum e não duplica a estatística robusta."""
    faltando = (
        kcal_medio is None
        or trend_kg_semana is None
        or dias_comida < MIN_DIAS_COMIDA
        or pontos_peso < MIN_PONTOS_PESO
        or janela_peso_dias < MIN_JANELA_PESO_DIAS
        or kcal_confianca in ("insuficiente", NENHUMA)
    )
    if faltando:
        return Aprendido(
            "energia", tdee_formula, NENHUMA,
            "Ainda sem dados suficientes: preciso de ~2 semanas registrando comida e peso.",
            0,
        )

    bruto = kcal_medio - (trend_kg_semana * KCAL_POR_KG / 7.0)
    limitado = _limitar(bruto, tdee_formula * TDEE_MIN_FATOR, tdee_formula * TDEE_MAX_FATOR)
    final = _passo_maximo(tdee_anterior, limitado, TDEE_PASSO)

    # A confiança do conjunto é a do elo mais fraco: uma tendência de peso ótima
    # não salva uma semana de comida mal registrada.
    conf_comida = (
        ALTA if dias_comida >= 21 else MEDIA if dias_comida >= 14 else BAIXA
    )
    conf_peso = (
        ALTA if pontos_peso >= 12 and janela_peso_dias >= 28
        else MEDIA if pontos_peso >= 7
        else BAIXA
    )
    ordem = [BAIXA, MEDIA, ALTA]
    confianca = ordem[min(ordem.index(conf_comida), ordem.index(conf_peso))]

    sentido = "ganhando" if trend_kg_semana > 0 else "perdendo" if trend_kg_semana < 0 else "mantendo"
    nota = ""
    if abs(limitado - bruto) > 1:
        nota = " (limitei o valor: o registro sugere um gasto fora do plausível)"
    return Aprendido(
        "energia", final, confianca,
        f"Você come ~{round(kcal_medio)} kcal/dia e está {sentido} "
        f"{abs(trend_kg_semana):.2f} kg/semana — isso põe seu gasto real perto de "
        f"{round(final)} kcal/dia, contra {round(tdee_formula)} da fórmula{nota}.",
        dias_comida,
    )


# ---------------------------------------------------------------------------
# 2. TOLERÂNCIA A VOLUME — quanta série ESTA pessoa aguenta de verdade
# ---------------------------------------------------------------------------
#
# Hoje o volume sai de `_LEVEL_FACTOR` (iniciante/intermediário/avançado), que a
# pessoa escolhe no questionário sobre si mesma. Duas pessoas que se declaram
# "intermediário" recebem o mesmo volume, mesmo que uma termine todo treino
# subindo carga e a outra abandone metade das sessões.
#
# Três sinais observáveis, cada um respondendo uma pergunta:
#   - CONCLUSÃO: ela termina o que foi prescrito? (volume prescrito é real?)
#   - EXECUÇÃO:  ela faz as séries que estavam no plano? (ou corta no meio?)
#   - PROGRESSO: a carga sobe? (o volume está produzindo resultado?)

MIN_SESSOES_TOLERANCIA = 6
JANELA_TOLERANCIA_DIAS = 42

# Faixa dura: o aprendizado ajusta o volume em no máximo ±25%. Ele afina a
# prescrição; não reescreve a fisiologia dos landmarks MEV/MRV.
TOLERANCIA_MIN = 0.75
TOLERANCIA_MAX = 1.25


def tolerancia_a_volume(
    db: Session, user_id: int, now: datetime | None = None
) -> Aprendido:
    """Fator multiplicador do volume semanal, lido da execução real."""
    now = now or datetime.now(timezone.utc)
    desde = now - timedelta(days=JANELA_TOLERANCIA_DIAS)

    sessoes = list(
        db.execute(
            select(WorkoutSession.id, WorkoutSession.routine_id, WorkoutSession.completed_at)
            .where(WorkoutSession.user_id == user_id, WorkoutSession.started_at >= desde)
        ).all()
    )
    if len(sessoes) < MIN_SESSOES_TOLERANCIA:
        return Aprendido(
            "tolerancia_volume", 1.0, NENHUMA,
            f"Preciso de pelo menos {MIN_SESSOES_TOLERANCIA} treinos registrados pra saber "
            "quanto volume você aguenta.",
            len(sessoes),
        )

    concluidas = sum(1 for _, _, c in sessoes if c is not None)
    taxa_conclusao = concluidas / len(sessoes)

    # Séries EFETIVAS registradas por sessão (aquecimento e feeder não contam
    # como volume — é a mesma definição que os landmarks usam).
    ids = [s for s, _, _ in sessoes]
    feitas = dict(
        db.execute(
            select(WorkoutSetLog.session_id, func.count(WorkoutSetLog.id))
            .where(
                WorkoutSetLog.session_id.in_(ids),
                WorkoutSetLog.set_type.not_in([SetType.WARMUP, SetType.FEEDER]),
            )
            .group_by(WorkoutSetLog.session_id)
        ).all()
    )
    # Séries PRESCRITAS na rotina daquela sessão.
    prescritas = dict(
        db.execute(
            select(RoutineExercise.routine_id, func.sum(RoutineExercise.target_sets))
            .where(RoutineExercise.routine_id.in_([r for _, r, _ in sessoes if r]))
            .group_by(RoutineExercise.routine_id)
        ).all()
    )

    razoes: list[float] = []
    for sid, rid, _ in sessoes:
        alvo = prescritas.get(rid)
        if not alvo:
            continue
        razoes.append(min((feitas.get(sid) or 0) / float(alvo), 1.5))
    taxa_execucao = median(razoes) if razoes else None

    if taxa_execucao is None:
        return Aprendido(
            "tolerancia_volume", 1.0, NENHUMA,
            "Os treinos registrados não vieram de uma rotina com séries planejadas, "
            "então não consigo comparar o feito com o prescrito.",
            len(sessoes),
        )

    # Da execução observada pro fator. Quem entrega tudo (ou mais) e termina as
    # sessões pode receber mais; quem entrega metade está recebendo volume que
    # não cabe na vida dela — e prescrever ainda mais é ignorar o que ela mostrou.
    fator = _limitar(0.55 + 0.5 * taxa_execucao + 0.2 * taxa_conclusao, TOLERANCIA_MIN, TOLERANCIA_MAX)

    confianca = ALTA if len(sessoes) >= 18 else MEDIA if len(sessoes) >= 10 else BAIXA
    if fator >= 1.05:
        leitura = "você fecha o que é prescrito — dá pra subir o volume"
    elif fator <= 0.95:
        leitura = "boa parte das séries planejadas não acontece — melhor prescrever o que cabe de verdade"
    else:
        leitura = "o volume atual está no tamanho certo pra você"
    return Aprendido(
        "tolerancia_volume", fator, confianca,
        f"Em {len(sessoes)} treinos você registrou {round(taxa_execucao * 100)}% das séries "
        f"planejadas e terminou {round(taxa_conclusao * 100)}% das sessões: {leitura}.",
        len(sessoes),
    )


# ---------------------------------------------------------------------------
# 3. PASSO DE CARGA POR EXERCÍCIO — quanto ESTA pessoa sobe neste exercício
# ---------------------------------------------------------------------------
#
# `engine.progression_step` sugere +5 kg em membro inferior e +2,5 kg no resto,
# para todo mundo, em todo exercício. Mas quem levanta 40 kg no supino e quem
# levanta 120 não sobem no mesmo degrau, e a anilha disponível não é a mesma em
# elevação lateral e leg press.
#
# O que se aprende aqui é o degrau que a pessoa REALMENTE usou neste exercício —
# olhando as subidas de carga que aconteceram no histórico dela.

MIN_SUBIDAS = 3
JANELA_PASSO_DIAS = 180
PASSO_MIN_KG = 1.0
PASSO_MAX_KG = 20.0


def passo_de_carga(
    db: Session, user_id: int, exercise_id: int, now: datetime | None = None
) -> Aprendido:
    """O incremento de carga típico desta pessoa neste exercício."""
    now = now or datetime.now(timezone.utc)
    desde = now - timedelta(days=JANELA_PASSO_DIAS)

    linhas = db.execute(
        select(WorkoutSession.started_at, func.max(WorkoutSetLog.weight_kg))
        .join(WorkoutSetLog, WorkoutSetLog.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= desde,
            WorkoutSetLog.exercise_id == exercise_id,
            WorkoutSetLog.set_type.not_in([SetType.WARMUP, SetType.FEEDER]),
        )
        .group_by(WorkoutSession.id, WorkoutSession.started_at)
        .order_by(WorkoutSession.started_at)
    ).all()

    pesos = [float(p) for _, p in linhas if p]
    subidas = [b - a for a, b in zip(pesos, pesos[1:]) if b > a]
    if len(subidas) < MIN_SUBIDAS:
        return Aprendido(
            "passo_carga", 0.0, NENHUMA,
            "Ainda não vi subidas de carga suficientes neste exercício pra saber seu degrau.",
            len(subidas),
        )

    passo = _limitar(median(subidas), PASSO_MIN_KG, PASSO_MAX_KG)
    confianca = ALTA if len(subidas) >= 8 else MEDIA if len(subidas) >= 5 else BAIXA
    return Aprendido(
        "passo_carga", passo, confianca,
        f"Nas suas {len(subidas)} subidas de carga neste exercício, o degrau típico foi "
        f"{passo:g} kg.",
        len(subidas),
    )


# ---------------------------------------------------------------------------
# 4. RITMO DA SESSÃO — quanto tempo ESTA pessoa leva por série
# ---------------------------------------------------------------------------
#
# `prescription.session_minutes` estima a duração com constantes universais
# (3 s por repetição, 60 s de transição). Elas serviram pra corrigir rótulos que
# exageravam o tempo em ~2×, mas continuam sendo a média de uma pessoa genérica.
# Quem conversa entre séries e quem treina de fone levam tempos bem diferentes —
# e o app já mede os dois, do início ao fim de cada sessão.

MIN_SESSOES_RITMO = 5
JANELA_RITMO_DIAS = 60
SEG_POR_SERIE_MIN = 60.0
SEG_POR_SERIE_MAX = 420.0
# Sessões absurdas (esqueceu de finalizar, finalizou no dia seguinte) não podem
# entrar na conta — são erro de registro, não ritmo.
SESSAO_MIN_MIN, SESSAO_MAX_MIN = 10, 180


def ritmo_da_sessao(db: Session, user_id: int, now: datetime | None = None) -> Aprendido:
    """Segundos por série efetiva, medidos das sessões concluídas."""
    now = now or datetime.now(timezone.utc)
    desde = now - timedelta(days=JANELA_RITMO_DIAS)

    linhas = db.execute(
        select(
            WorkoutSession.started_at,
            WorkoutSession.completed_at,
            func.count(WorkoutSetLog.id),
        )
        .join(WorkoutSetLog, WorkoutSetLog.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= desde,
            WorkoutSession.completed_at.is_not(None),
            WorkoutSetLog.set_type.not_in([SetType.WARMUP, SetType.FEEDER]),
        )
        .group_by(WorkoutSession.id, WorkoutSession.started_at, WorkoutSession.completed_at)
    ).all()

    ritmos: list[float] = []
    for inicio, fim, series in linhas:
        if not series or inicio is None or fim is None:
            continue
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        if fim.tzinfo is None:
            fim = fim.replace(tzinfo=timezone.utc)
        minutos = (fim - inicio).total_seconds() / 60.0
        if not (SESSAO_MIN_MIN <= minutos <= SESSAO_MAX_MIN):
            continue
        ritmos.append(minutos * 60.0 / series)

    if len(ritmos) < MIN_SESSOES_RITMO:
        return Aprendido(
            "ritmo_sessao", 0.0, NENHUMA,
            f"Preciso de {MIN_SESSOES_RITMO} treinos concluídos pra medir o seu ritmo.",
            len(ritmos),
        )

    seg = _limitar(median(ritmos), SEG_POR_SERIE_MIN, SEG_POR_SERIE_MAX)
    confianca = ALTA if len(ritmos) >= 15 else MEDIA if len(ritmos) >= 9 else BAIXA
    return Aprendido(
        "ritmo_sessao", seg, confianca,
        f"Nos seus {len(ritmos)} últimos treinos você levou cerca de {round(seg)} s por série "
        "(contando descanso e transição).",
        len(ritmos),
    )


# ---------------------------------------------------------------------------
# O retrato completo — o que alimenta a tela e o prompt do coach
# ---------------------------------------------------------------------------


@dataclass
class ModeloAprendido:
    energia: Aprendido
    tolerancia_volume: Aprendido
    ritmo_sessao: Aprendido

    def to_dict(self) -> dict:
        return {
            "energia": self.energia.to_dict(),
            "tolerancia_volume": self.tolerancia_volume.to_dict(),
            "ritmo_sessao": self.ritmo_sessao.to_dict(),
            "aprendidos": [a.chave for a in self._todos() if a.usar],
        }

    def _todos(self) -> list[Aprendido]:
        return [self.energia, self.tolerancia_volume, self.ritmo_sessao]

    def prompt_lines(self) -> list[str]:
        """Como isto entra no contexto do coach de IA. Só o que já é confiável —
        listar o que ele ainda não sabe só o faria falar de menos com mais
        palavras."""
        ativos = [a for a in self._todos() if a.usar]
        if not ativos:
            return []
        return [
            "",
            "O QUE EU MEDI NELA E JÁ ESTOU USANDO NAS CONTAS (não é estimativa de tabela):",
            *[f"- {a.evidencia}" for a in ativos],
            "Pode citar estes números com segurança: eles saíram do histórico dela, não de fórmula.",
        ]


def energia_do_usuario(db: Session, user_id: int, profile, peso_kg: float | None) -> Aprendido:
    """A energia observada desta pessoa, lida do histórico dela.

    Ponte entre `metrics` (que já sabe calcular média robusta de caloria e
    tendência de peso) e a fórmula. Importa lá dentro de propósito: `metrics` é
    caro e nem todo chamador de `adaptive` precisa dele.
    """
    from app.coaching.metrics import compute_metrics
    from app.services.nutrition_calc import calculate_bmr, calculate_tdee

    if profile is None or peso_kg is None or not profile.biological_sex or not profile.activity_level:
        return Aprendido("energia", 0.0, NENHUMA, "Ainda não tenho seus dados básicos pra estimar gasto.", 0)

    formula = calculate_tdee(
        calculate_bmr(profile.biological_sex, peso_kg, profile.height_cm, profile.age),
        profile.activity_level,
    )
    # Janela de 28 dias: curta o bastante pra acompanhar mudança de rotina,
    # longa o bastante pra a tendência de peso não ser ruído de retenção.
    m = compute_metrics(db, user_id, window_days=28)
    return energia_observada(
        kcal_medio=m.nutrition.avg_kcal_logged,
        kcal_confianca=m.nutrition.avg_confidence,
        dias_comida=m.nutrition.days_logged,
        trend_kg_semana=m.weight.trend_kg_per_week,
        pontos_peso=m.weight.points,
        janela_peso_dias=m.weight.span_days,
        tdee_formula=formula,
    )


def modelo(
    db: Session,
    user_id: int,
    *,
    profile=None,
    peso_kg: float | None = None,
    now: datetime | None = None,
) -> ModeloAprendido:
    """Tudo que o coach aprendeu sobre esta pessoa, numa leitura só.

    `profile` e `peso_kg` são o que a parte de ENERGIA precisa; sem eles, ela
    volta "nenhuma" e as outras duas continuam valendo normalmente."""
    return ModeloAprendido(
        energia=energia_do_usuario(db, user_id, profile, peso_kg),
        tolerancia_volume=tolerancia_a_volume(db, user_id, now),
        ritmo_sessao=ritmo_da_sessao(db, user_id, now),
    )
