"""Médias ROBUSTAS — a régua estatística do coach (spec §10.4).

Por que não usar média simples: um único dia atípico (churrasco de 5.000 kcal,
um dia que a pessoa esqueceu de registrar o jantar) puxa a média e faz o coach
recomendar um ajuste que não tem nada a ver com a rotina real dela. Um outlier
não é mentira — é um dia — mas ele não pode mandar na leitura.

A regra é escolher o método pela QUANTIDADE de dias válidos:

    < 5 dias    -> não dá pra concluir nada (confiança "insuficiente")
    5 a 6       -> mediana, confiança baixa
    7 a 13      -> mediana ou média winsorizada
    14 ou mais  -> média robusta com detecção de outliers

Nada é apagado: o outlier continua no histórico e nos gráficos, só tem o peso
LIMITADO na média (winsorização = puxa pro percentil, não descarta).
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median as _median


@dataclass
class RobustAverage:
    """Resultado de uma média robusta, com o rastro de como foi calculada —
    a UI e o motor de decisão precisam saber o quanto podem confiar nela."""

    value: float | None
    method: str  # "insuficiente" | "mediana" | "winsorizada"
    confidence: str  # "insuficiente" | "baixa" | "media" | "alta"
    n: int
    outliers: int  # quantos valores tiveram o peso limitado

    @property
    def is_usable(self) -> bool:
        """True quando dá pra tomar decisão em cima. Abaixo de 5 dias o coach
        não gera conclusão forte — mostra o número, mas não age nele."""
        return self.value is not None and self.confidence != "insuficiente"


# Fronteiras da spec §10.4.
MIN_FOR_CONCLUSION = 5
MIN_FOR_WINSOR = 7
MIN_FOR_HIGH_CONFIDENCE = 14

# Quanto se apara de cada ponta na winsorização. 10% é conservador: com 14 dias
# limita 1 valor de cada lado; com 20, dois.
WINSOR_FRACTION = 0.10


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Percentil por interpolação linear. `q` em [0, 1]."""
    if not sorted_vals:
        raise ValueError("lista vazia")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def winsorized_mean(values: list[float], fraction: float = WINSOR_FRACTION) -> tuple[float, int]:
    """Média winsorizada: valores abaixo do percentil `fraction` viram esse
    percentil, e o mesmo no topo. Devolve (média, quantos foram limitados).

    Winsorizar em vez de aparar é de propósito: o dia extremo continua contando
    como um dia (a pessoa comeu), só que com peso de "dia alto", não de
    "outlier que domina a média".
    """
    if not values:
        return 0.0, 0
    ordenados = sorted(values)
    lo = _percentile(ordenados, fraction)
    hi = _percentile(ordenados, 1 - fraction)
    limitados = 0
    ajustados: list[float] = []
    for v in values:
        if v < lo:
            ajustados.append(lo)
            limitados += 1
        elif v > hi:
            ajustados.append(hi)
            limitados += 1
        else:
            ajustados.append(v)
    return sum(ajustados) / len(ajustados), limitados


def robust_average(values: list[float]) -> RobustAverage:
    """A média que o coach usa pra decidir. Só devem entrar aqui dias
    ENCERRADOS e VÁLIDOS (ver day_quality) — esta função não sabe filtrar dia
    em andamento nem registro pela metade, ela só faz a estatística."""
    n = len(values)
    if n == 0:
        return RobustAverage(value=None, method="insuficiente", confidence="insuficiente", n=0, outliers=0)

    if n < MIN_FOR_CONCLUSION:
        # Mostra a mediana (é o resumo mais honesto com poucos pontos), mas
        # marca como insuficiente: o motor não gera recomendação em cima disto.
        return RobustAverage(
            value=round(float(_median(values)), 2),
            method="mediana",
            confidence="insuficiente",
            n=n,
            outliers=0,
        )

    if n < MIN_FOR_WINSOR:
        return RobustAverage(
            value=round(float(_median(values)), 2), method="mediana", confidence="baixa", n=n, outliers=0
        )

    media, limitados = winsorized_mean(values)
    return RobustAverage(
        value=round(media, 2),
        method="winsorizada",
        confidence="alta" if n >= MIN_FOR_HIGH_CONFIDENCE else "media",
        n=n,
        outliers=limitados,
    )


def moving_average(values: list[float], window: int = 7) -> list[float]:
    """Média móvel — a leitura certa pro PESO corporal, que oscila vários
    quilos por retenção de água sem nada ter mudado de verdade. Sempre devolve
    a mesma quantidade de pontos da entrada (janela cresce até `window`)."""
    out: list[float] = []
    for i in range(len(values)):
        janela = values[max(0, i - window + 1) : i + 1]
        out.append(sum(janela) / len(janela))
    return out
