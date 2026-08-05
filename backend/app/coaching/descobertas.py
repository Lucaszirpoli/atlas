"""DESCOBERTAS — o coach cruzando TODOS os dados da pessoa pra achar o que
afeta o quê, nela especificamente.

A diferença pro `adaptive.py`: aquele mede PARÂMETROS dela (gasto, tolerância a
volume, ritmo) que entram nas contas. Este acha RELAÇÕES entre dimensões
diferentes ("nos dias em que você bebeu pouca água, seu volume de treino caiu
14%") — coisas que nenhum questionário pergunta e que nem a própria pessoa
percebe, porque exigem cruzar meses de registro de quatro módulos ao mesmo
tempo.

O que existia antes: TRÊS correlações escritas na mão, no frontend, só como
texto na tela de Evolução — não alimentavam decisão nenhuma do coach. Este
módulo generaliza aquilo pro backend, com todas as dimensões e com rigor
estatístico.

═══════════════════════════════════════════════════════════════════════════
POR QUE NÃO TESTAR "TUDO CONTRA TUDO"
═══════════════════════════════════════════════════════════════════════════

É a pergunta óbvia: por que não cruzar as 12 dimensões todas contra todas, nos
dois sentidos, com defasagem? Porque isso são ~250 testes, e com 30 dias de
dado o acaso SOZINHO produz dezenas de "achados" fortes. É exatamente o
sobreajuste que mata robô de trade que foi otimizado no histórico: encontra
padrão lindo no passado e não vale nada no futuro.

Três defesas, todas obrigatórias pra um achado aparecer:

1. **Catálogo fechado de hipóteses plausíveis.** Só testamos relações que
   fazem sentido fisiológico (sono→treino, hidratação→treino, comida→treino,
   sono→apetite...). Não testamos "peso de terça prevê água de quinta".
2. **Tamanho de efeito mínimo + amostra mínima nos DOIS grupos.** Diferença de
   3% com 2 dias de cada lado é ruído com cara de descoberta.
3. **Estabilidade.** O efeito precisa aparecer na PRIMEIRA e na SEGUNDA metade
   da janela, na mesma direção. Um feriado atípico não vira lei.

E, mesmo passando nas três, a frase é sempre DESCRITIVA ("nos dias em que...,
foi X%"), nunca causal ("dormir pouco FAZ você comer mais"). O coach relata o
que observou no histórico dela; não afirma mecanismo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.usertime import local_date, window_start_utc
from app.models.meal import MealLog, MealLogItem
from app.models.sleep_log import SleepLog
from app.models.water_log import WaterLog
from app.models.weight_log import WeightLog
from app.models.workout_session import SetType, WorkoutSession, WorkoutSetLog

# Janela de observação. 120 dias dá base pra estabilidade sem deixar hábito de
# meio ano atrás mandar no retrato de hoje.
JANELA_DIAS = 120

# Guardas anti-ruído (ver docstring).
MIN_POR_GRUPO = 4        # dias mínimos em CADA lado da comparação
MIN_EFEITO_PCT = 8.0     # abaixo disso não é achado, é oscilação
MIN_DIAS_ESTABILIDADE = 12  # abaixo disso nem tenta checar as duas metades


@dataclass(frozen=True)
class Descoberta:
    """Uma relação observada entre duas dimensões da vida da pessoa."""

    chave: str
    titulo: str
    frase: str
    efeito_pct: float
    n: int
    confianca: str  # baixa | media | alta
    acao: str | None = None  # o que fazer a respeito, quando há algo seguro a fazer

    def to_dict(self) -> dict:
        return {
            "chave": self.chave,
            "titulo": self.titulo,
            "frase": self.frase,
            "efeito_pct": round(self.efeito_pct, 1),
            "n": self.n,
            "confianca": self.confianca,
            "acao": self.acao,
        }


# ---------------------------------------------------------------------------
# 1. A TABELA DIÁRIA — todas as dimensões, um valor por dia, no fuso da pessoa
# ---------------------------------------------------------------------------
def tabela_diaria(db: Session, user_id: int, tz: ZoneInfo, dias: int = JANELA_DIAS) -> dict[str, dict[date, float]]:
    """Um dicionário por dimensão: {dia local -> valor}.

    Tudo é bucketizado no FUSO DA PESSOA (não UTC): um treino das 21h no Brasil
    é do dia que ela treinou, não do dia seguinte.
    """
    desde = window_start_utc(dias, tz)
    t: dict[str, dict[date, float]] = {}

    # --- SONO (atribuído ao dia em que ACORDOU) ---------------------------
    horas: dict[date, float] = {}
    qualidade: dict[date, float] = {}
    for lg in db.execute(
        select(SleepLog).where(SleepLog.user_id == user_id, SleepLog.wake_at >= desde)
    ).scalars():
        d = local_date(lg.wake_at, tz)
        horas[d] = (lg.wake_at - lg.sleep_at).total_seconds() / 3600.0
        if lg.quality is not None:
            qualidade[d] = float(lg.quality)
    t["sono_horas"] = horas
    t["sono_qualidade"] = qualidade

    # --- DIETA ------------------------------------------------------------
    kcal: dict[date, float] = {}
    prot: dict[date, float] = {}
    carb: dict[date, float] = {}
    gord: dict[date, float] = {}
    linhas = db.execute(
        select(
            MealLog.logged_at,
            func.sum(MealLogItem.kcal),
            func.sum(MealLogItem.protein_g),
            func.sum(MealLogItem.carbs_g),
            func.sum(MealLogItem.fat_g),
        )
        .join(MealLogItem, MealLogItem.meal_log_id == MealLog.id)
        .where(MealLog.user_id == user_id, MealLog.logged_at >= desde)
        .group_by(MealLog.id, MealLog.logged_at)
    ).all()
    for quando, k, p, c, g in linhas:
        d = local_date(quando, tz)
        kcal[d] = kcal.get(d, 0.0) + float(k or 0)
        prot[d] = prot.get(d, 0.0) + float(p or 0)
        carb[d] = carb.get(d, 0.0) + float(c or 0)
        gord[d] = gord.get(d, 0.0) + float(g or 0)
    t["kcal"] = kcal
    t["proteina"] = prot
    t["carbo"] = carb
    t["gordura"] = gord

    # --- ÁGUA -------------------------------------------------------------
    agua: dict[date, float] = {}
    for quando, ml in db.execute(
        select(WaterLog.logged_at, WaterLog.amount_ml)
        .where(WaterLog.user_id == user_id, WaterLog.logged_at >= desde)
    ).all():
        d = local_date(quando, tz)
        agua[d] = agua.get(d, 0.0) + float(ml or 0)
    t["agua"] = agua

    # --- TREINO (volume, carga média, séries, duração) --------------------
    volume: dict[date, float] = {}
    carga: dict[date, float] = {}
    series: dict[date, float] = {}
    duracao: dict[date, float] = {}
    sessoes = db.execute(
        select(
            WorkoutSession.started_at,
            WorkoutSession.completed_at,
            func.sum(WorkoutSetLog.weight_kg * WorkoutSetLog.reps),
            func.avg(WorkoutSetLog.weight_kg),
            func.count(WorkoutSetLog.id),
        )
        .join(WorkoutSetLog, WorkoutSetLog.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= desde,
            WorkoutSetLog.set_type.not_in([SetType.WARMUP, SetType.FEEDER]),
        )
        .group_by(WorkoutSession.id, WorkoutSession.started_at, WorkoutSession.completed_at)
    ).all()
    for inicio, fim, vol, cg, n in sessoes:
        d = local_date(inicio, tz)
        if vol:
            volume[d] = volume.get(d, 0.0) + float(vol)
        if cg:
            carga[d] = float(cg)
        if n:
            series[d] = series.get(d, 0.0) + float(n)
        if fim is not None:
            mins = (fim - inicio).total_seconds() / 60.0
            if 10 <= mins <= 180:  # sessão esquecida aberta não é duração
                duracao[d] = mins
    t["treino_volume"] = volume
    t["treino_carga"] = carga
    t["treino_series"] = series
    t["treino_duracao"] = duracao

    # --- PESO -------------------------------------------------------------
    peso: dict[date, float] = {}
    for lg in db.execute(
        select(WeightLog).where(WeightLog.user_id == user_id, WeightLog.recorded_at >= desde)
    ).scalars():
        peso[local_date(lg.recorded_at, tz)] = float(lg.weight_kg)
    t["peso"] = peso

    return t


# ---------------------------------------------------------------------------
# 2. O CATÁLOGO DE HIPÓTESES — só relações que fazem sentido fisiológico
# ---------------------------------------------------------------------------
#
# (causa, efeito, defasagem_em_dias, título, molde da frase)
#
# `{sinal}` vira "a mais"/"a menos"; `{pct}` o tamanho do efeito; `{alto}` e
# `{baixo}` as médias dos dois grupos, já formatadas.
_HIPOTESES: list[tuple[str, str, int, str, str]] = [
    # --- SONO afetando o resto ---------------------------------------------
    ("sono_horas", "kcal", 0, "Sono e fome",
     "Nos dias em que você dormiu menos, comeu {pct}% {sinal} ({baixo} vs {alto})."),
    ("sono_horas", "kcal", 1, "Sono e fome do dia seguinte",
     "No dia seguinte a uma noite curta, você comeu {pct}% {sinal} ({baixo} vs {alto})."),
    ("sono_horas", "treino_volume", 0, "Sono e rendimento",
     "Nos dias em que você dormiu menos, seu treino rendeu {pct}% {sinal} de volume ({baixo} vs {alto})."),
    ("sono_horas", "treino_carga", 0, "Sono e carga",
     "Nos dias em que você dormiu menos, a carga média que você pegou foi {pct}% {sinal} ({baixo} vs {alto})."),
    ("sono_qualidade", "treino_volume", 0, "Qualidade do sono e treino",
     "Nas noites que você avaliou como piores, o treino rendeu {pct}% {sinal} de volume ({baixo} vs {alto})."),
    ("sono_horas", "agua", 0, "Sono e hidratação",
     "Nos dias em que você dormiu menos, bebeu {pct}% {sinal} de água ({baixo} vs {alto})."),

    # --- COMIDA afetando o treino ------------------------------------------
    ("kcal", "treino_volume", 1, "Comida e treino do dia seguinte",
     "Depois dos dias em que você comeu mais, o treino seguinte rendeu {pct}% {sinal} de volume ({baixo} vs {alto})."),
    ("carbo", "treino_volume", 1, "Carboidrato e rendimento",
     "Depois dos dias com mais carboidrato, o treino seguinte rendeu {pct}% {sinal} de volume ({baixo} vs {alto})."),
    ("carbo", "treino_carga", 1, "Carboidrato e carga",
     "Depois dos dias com mais carboidrato, a carga média foi {pct}% {sinal} ({baixo} vs {alto})."),
    ("kcal", "treino_duracao", 1, "Comida e duração do treino",
     "Depois dos dias em que você comeu mais, você treinou {pct}% {sinal} tempo ({baixo} vs {alto})."),

    # --- HIDRATAÇÃO --------------------------------------------------------
    ("agua", "treino_volume", 0, "Hidratação e rendimento",
     "Nos dias em que você bebeu mais água, o treino rendeu {pct}% {sinal} de volume ({baixo} vs {alto})."),
    ("agua", "treino_series", 0, "Hidratação e séries",
     "Nos dias em que você bebeu mais água, você fez {pct}% {sinal} séries ({baixo} vs {alto})."),

    # --- TREINO afetando sono e apetite ------------------------------------
    ("treino_volume", "sono_horas", 0, "Treino e sono da noite",
     "Nas noites depois dos treinos mais pesados, você dormiu {pct}% {sinal} ({baixo} vs {alto})."),
    ("treino_volume", "kcal", 0, "Treino e apetite",
     "Nos dias de treino mais pesado, você comeu {pct}% {sinal} ({baixo} vs {alto})."),
    ("treino_volume", "proteina", 0, "Treino e proteína",
     "Nos dias de treino mais pesado, você comeu {pct}% {sinal} de proteína ({baixo} vs {alto})."),

    # --- PROTEÍNA ----------------------------------------------------------
    ("proteina", "treino_volume", 1, "Proteína e rendimento",
     "Depois dos dias com mais proteína, o treino seguinte rendeu {pct}% {sinal} de volume ({baixo} vs {alto})."),
]

# Como formatar o valor de cada dimensão dentro da frase.
_FORMATO: dict[str, callable] = {
    "sono_horas": lambda v: f"{v:.1f}h".replace(".", ","),
    "sono_qualidade": lambda v: f"{v:.1f}".replace(".", ","),
    "kcal": lambda v: f"{round(v)} kcal",
    "proteina": lambda v: f"{round(v)}g",
    "carbo": lambda v: f"{round(v)}g",
    "gordura": lambda v: f"{round(v)}g",
    "agua": lambda v: f"{v / 1000:.1f}L".replace(".", ","),
    "treino_volume": lambda v: f"{v / 1000:.1f}t".replace(".", ",") if v >= 1000 else f"{round(v)}kg",
    "treino_carga": lambda v: f"{round(v)}kg",
    "treino_series": lambda v: f"{round(v)} séries",
    "treino_duracao": lambda v: f"{round(v)}min",
    "peso": lambda v: f"{v:.1f}kg".replace(".", ","),
}

# Palavra que descreve a direção, por dimensão do EFEITO.
_SINAL_MAIS = {
    "sono_horas": ("a mais", "a menos"),
    "treino_duracao": ("a mais", "a menos"),
}


def _media(ns: list[float]) -> float:
    return sum(ns) / len(ns)


def _pares(
    tabela: dict[str, dict[date, float]], causa: str, efeito: str, lag: int
) -> list[tuple[date, float, float]]:
    """Dias em que existe valor da causa E do efeito (com a defasagem)."""
    origem = tabela.get(causa) or {}
    destino = tabela.get(efeito) or {}
    out: list[tuple[date, float, float]] = []
    for d, v in origem.items():
        alvo = destino.get(d + timedelta(days=lag))
        if alvo is not None:
            out.append((d, v, alvo))
    return out


def _efeito(pares: list[tuple[date, float, float]]) -> tuple[float, float, float] | None:
    """Separa os dias pela MEDIANA da causa e compara a média do efeito nos
    dois grupos. Devolve (diferença %, média do grupo alto, média do baixo).

    Mediana e não média: um único dia extremo desloca a média e joga quase
    todo mundo pro mesmo lado, esvaziando a comparação.
    """
    if len(pares) < MIN_POR_GRUPO * 2:
        return None
    corte = median([c for _, c, _ in pares])
    altos = [e for _, c, e in pares if c > corte]
    baixos = [e for _, c, e in pares if c <= corte]
    if len(altos) < MIN_POR_GRUPO or len(baixos) < MIN_POR_GRUPO:
        return None
    ma, mb = _media(altos), _media(baixos)
    if mb == 0:
        return None
    return (ma / mb - 1) * 100, ma, mb


def _estavel(pares: list[tuple[date, float, float]], direcao: float) -> bool:
    """O efeito aparece nas DUAS metades da janela, na mesma direção?

    É esta checagem que separa 'padrão dela' de 'uma semana atípica'. Com
    poucos dias não dá pra exigir (não haveria metade com amostra), então
    abaixo do piso o achado passa — mas entra como confiança baixa.
    """
    if len(pares) < MIN_DIAS_ESTABILIDADE:
        return True
    ordenados = sorted(pares, key=lambda p: p[0])
    meio = len(ordenados) // 2
    for metade in (ordenados[:meio], ordenados[meio:]):
        r = _efeito(metade)
        if r is None:
            return False
        if (r[0] > 0) != (direcao > 0):
            return False
    return True


# ---------------------------------------------------------------------------
# 3. DE ACHADO PRA AÇÃO
# ---------------------------------------------------------------------------
#
# Nem toda descoberta vira ação, e isso é de propósito. Correlação não é causa:
# saber que você come mais depois de dormir mal não autoriza o app a mexer na
# sua meta. Só entram aqui as relações em que existe uma coisa CONCRETA e
# SEGURA a fazer — e mesmo essas exigem barra mais alta que a de exibição.

ACAO_EFEITO_MIN = 12.0          # efeito mínimo pra sugerir algo (exibir basta 8%)
ACAO_CONFIANCA = {"media", "alta"}  # com confiança baixa o coach mostra, mas não age

# chave da hipótese -> o que fazer. Texto na voz do coach, sem culpa.
_ACOES: dict[str, str] = {
    "sono_horas->kcal@1": (
        "Nos dias seguintes a uma noite curta, deixe a proteína e a fruta à mão: "
        "a fome sobe sozinha e a escolha fica mais difícil."
    ),
    "sono_horas->treino_volume@0": (
        "Quando dormir mal, troque a meta do dia: mantenha a carga e tire uma série, "
        "em vez de tentar fechar tudo e falhar no meio."
    ),
    "sono_horas->treino_carga@0": (
        "Depois de noite curta, use o aquecimento pra decidir a carga do dia — "
        "seu corpo já mostrou que ela cai nesses dias."
    ),
    "sono_qualidade->treino_volume@0": (
        "Sono ruim tem pesado no seu rendimento. Vale tratar a noite anterior "
        "como parte do treino."
    ),
    "agua->treino_volume@0": (
        "Beber água antes e durante o treino tem rendido volume pra você. "
        "Leve a garrafa cheia."
    ),
    "agua->treino_series@0": (
        "Sua hidratação aparece no número de séries que você aguenta. "
        "Vale começar o dia bebendo."
    ),
    "carbo->treino_volume@1": (
        "Carboidrato na véspera tem virado rendimento no seu caso. "
        "Reforce no dia anterior aos treinos pesados."
    ),
    "carbo->treino_carga@1": (
        "Sua carga responde ao carboidrato do dia anterior. "
        "Vale planejar isso antes dos dias de treino puxado."
    ),
    "kcal->treino_volume@1": (
        "Comer abaixo do normal tem custado rendimento no treino seguinte. "
        "Os dias de véspera de treino são os piores pra cortar comida."
    ),
    "proteina->treino_volume@1": (
        "Sua proteína do dia anterior tem aparecido no treino seguinte."
    ),
}

# Quanto uma descoberta forte de sono→rendimento pode mexer no fator de
# recuperação que dimensiona o volume da semana. Teto baixo DE PROPÓSITO: é
# correlação, então ela ajusta na margem — nunca manda no plano. E só pra
# BAIXO: o coach não infla volume por causa de correlação, só fica mais
# conservador quando a evidência da própria pessoa pede.
AJUSTE_RECUPERACAO_MAX = 0.08


def ajuste_de_recuperacao(achados: list[Descoberta]) -> tuple[float, str | None]:
    """O único lugar onde uma descoberta vira NÚMERO no plano.

    Se o histórico mostra que o rendimento desta pessoa cai bastante quando ela
    dorme mal, isso é evidência medida sobre a recuperação dela — exatamente o
    que `training_brain.recovery_factor` estima a partir do questionário. Aqui
    a evidência corrige a resposta, seguindo as mesmas regras do `adaptive`:
    piso de evidência, efeito limitado e nunca substituição total.

    Devolve (delta a somar no fator, motivo legível) — delta ≤ 0.
    """
    relevantes = [
        d for d in achados
        if d.chave in ("sono_horas->treino_volume@0", "sono_qualidade->treino_volume@0")
        and d.confianca in ACAO_CONFIANCA
        and d.efeito_pct > 0  # rendimento MAIOR com mais sono = cai com pouco sono
        and abs(d.efeito_pct) >= ACAO_EFEITO_MIN
    ]
    if not relevantes:
        return 0.0, None
    forte = max(relevantes, key=lambda d: abs(d.efeito_pct))
    # 20% de queda -> teto do ajuste. Proporcional, e limitado.
    delta = -min(AJUSTE_RECUPERACAO_MAX, AJUSTE_RECUPERACAO_MAX * abs(forte.efeito_pct) / 20.0)
    motivo = (
        f"Seu rendimento cai {round(abs(forte.efeito_pct))}% quando você dorme mal, "
        "então dimensionei a semana um pouco mais conservadora."
    )
    return round(delta, 3), motivo


def descobrir(db: Session, user_id: int, tz: ZoneInfo, limite: int = 8) -> list[Descoberta]:
    """Roda o catálogo inteiro e devolve os achados que sobreviveram às três
    defesas, do efeito mais forte pro mais fraco."""
    tabela = tabela_diaria(db, user_id, tz)
    achados: list[Descoberta] = []

    for causa, efeito_dim, lag, titulo, molde in _HIPOTESES:
        pares = _pares(tabela, causa, efeito_dim, lag)
        r = _efeito(pares)
        if r is None:
            continue
        diff, media_alta, media_baixa = r
        if abs(diff) < MIN_EFEITO_PCT:
            continue
        if not _estavel(pares, diff):
            continue

        fmt = _FORMATO.get(efeito_dim, lambda v: f"{round(v)}")
        mais, menos = _SINAL_MAIS.get(efeito_dim, ("a mais", "a menos"))
        # A frase compara o grupo BAIXO da causa contra o ALTO, então o sinal
        # é o do grupo baixo — é assim que "dormiu menos → comeu mais" sai certo.
        sinal = menos if diff > 0 else mais
        n = len(pares)
        confianca = "alta" if n >= 40 else "media" if n >= 20 else "baixa"
        chave = f"{causa}->{efeito_dim}@{lag}"
        # A sugestão só acompanha o achado quando ele é forte E confiável o
        # bastante. Abaixo disso o coach mostra o que viu, mas não manda fazer
        # nada — dizer "faça X" com base em ruído é pior que não dizer nada.
        acao = (
            _ACOES.get(chave)
            if confianca in ACAO_CONFIANCA and abs(diff) >= ACAO_EFEITO_MIN
            else None
        )
        achados.append(
            Descoberta(
                chave=chave,
                titulo=titulo,
                frase=molde.format(
                    pct=round(abs(diff)),
                    sinal=sinal,
                    alto=fmt(media_alta),
                    baixo=fmt(media_baixa),
                ),
                efeito_pct=diff,
                n=n,
                confianca=confianca,
                acao=acao,
            )
        )

    achados.sort(key=lambda a: abs(a.efeito_pct), reverse=True)
    return achados[:limite]
