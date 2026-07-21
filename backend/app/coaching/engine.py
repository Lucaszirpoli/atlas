"""Camadas 2–4 — DETECÇÃO -> DIAGNÓSTICO -> POLÍTICA.

Lê as métricas e produz achados (findings) com um ajuste graduado e reversível
cada. Tudo por REGRA explícita: os limiares estão aqui em cima, à vista, e o
mesmo input sempre gera o mesmo output. A IA do Coaching (Pro) só traduz isto em
conversa — não muda a decisão.

Tom: nunca culpa/vergonha (regra 7). Nenhum diagnóstico médico (regra 8) — sono
e afins viram sugestão de hábito, não laudo.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.coaching.metrics import Metrics

# --- Limiares (a régua do coach, explícita e auditável) -------------------
MIN_WEIGHT_POINTS = 3          # regressão de peso exige pelo menos isto
MIN_WEIGHT_SPAN_DAYS = 10      # ... e um intervalo mínimo, senão é ruído
MIN_LOGGING_RATIO = 0.4        # < 40% dos dias registrados => confiança baixa

# Faixas de variação de peso ideais por objetivo (% do peso corporal por semana;
# negativo = perdendo). Fora da faixa vira ajuste.
CUT_PLATEAU_ABS = 0.15         # |%/sem| abaixo disto num corte = platô
CUT_FAST_LOSS = -1.0           # perder mais rápido que 1%/sem = rápido demais
BULK_STALL_ABS = 0.05          # ganho ~zero na hipertrofia = não progride
BULK_DROP = -0.15              # perdendo peso de verdade durante um bulk
BULK_FAST_GAIN = 0.6           # ganhar mais que 0.6%/sem = gordura demais
MAINTAIN_DRIFT = 0.5           # manutenção/recomp: deriva > 0.5%/sem

PROTEIN_G_PER_KG_TARGET = 1.8  # alvo quando não há meta de macro definida
PROTEIN_LOW_RATIO = 0.85       # abaixo de 85% do alvo = baixo
MIN_SESSIONS_PER_WEEK = 2      # frequência mínima efetiva
SLEEP_SHORT_HOURS = 6.5
SLEEP_LOW_QUALITY = 3

SEV_INFO = "info"
SEV_ATTENTION = "attention"
SEV_ACTION = "action"


@dataclass
class Finding:
    key: str
    severity: str
    title: str
    detail: str
    proposal: str | None = None
    # Ajuste APLICÁVEL (só nos achados de caloria): {"kcal_delta": int}. O app
    # mostra "Aplicar" e o backend cria uma nova versão da meta. Achados de
    # hábito (proteína, sono, passos) não têm — são orientação, não um botão.
    adjustment: dict | None = None


@dataclass
class WeeklyAnalysis:
    window_days: int
    goal: str | None
    has_enough_data: bool
    confidence: str          # "alta" | "parcial" | "baixa"
    headline: str
    findings: list[Finding] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _protein_target(m: Metrics) -> float | None:
    if m.nutrition.goal_protein_g:
        return m.nutrition.goal_protein_g
    if m.weight_kg:
        return round(PROTEIN_G_PER_KG_TARGET * m.weight_kg, 1)
    return None


def _weight_findings(m: Metrics) -> list[Finding]:
    w = m.weight
    if w.points < MIN_WEIGHT_POINTS or w.span_days < MIN_WEIGHT_SPAN_DAYS or w.pct_bodyweight_per_week is None:
        return []
    pct = w.pct_bodyweight_per_week
    trend = w.trend_kg_per_week
    sinal = f"{trend:+.2f} kg/sem ({pct:+.2f}%/sem)"
    goal = m.goal
    gk = m.nutrition.goal_kcal

    if goal == "emagrecimento":
        if abs(pct) < CUT_PLATEAU_ABS:
            corte = round(gk * 0.1) if gk else 200
            return [Finding("plateau_cut", SEV_ACTION, "Peso estagnou no corte",
                            f"Nas últimas {w.span_days} dias o peso ficou praticamente parado ({sinal}), "
                            "mas o objetivo é emagrecer.",
                            f"Reduzir ~{corte} kcal/dia (uns 10%) OU somar ~2.000 passos/dia por 2 semanas e "
                            "reavaliar. Ajuste pequeno de propósito.",
                            adjustment={"kcal_delta": -corte})]
        if pct <= CUT_FAST_LOSS:
            return [Finding("fast_loss", SEV_ATTENTION, "Emagrecendo rápido demais",
                            f"A perda está em {sinal} — acima de ~1%/sem, o risco de perder músculo e "
                            "travar o metabolismo sobe.",
                            "Somar ~125 kcal/dia (de preferência carboidrato perto do treino) e manter "
                            "a proteína alta pra segurar o músculo.",
                            adjustment={"kcal_delta": 125})]
        return [Finding("on_track_cut", SEV_INFO, "Corte no ritmo certo",
                        f"Perda saudável e sustentável ({sinal}). Segue firme.")]

    if goal == "hipertrofia":
        if pct <= BULK_DROP:
            return [Finding("bulk_losing", SEV_ACTION, "Você está perdendo peso, não ganhando",
                            f"O objetivo é ganhar massa, mas o peso está caindo ({sinal}) — provável déficit "
                            "de calorias.",
                            "Somar ~200 kcal/dia (comida de verdade, não só treino) e reavaliar em 2 semanas.",
                            adjustment={"kcal_delta": 200})]
        if abs(pct) < BULK_STALL_ABS or (trend is not None and trend <= 0):
            return [Finding("bulk_stall", SEV_ACTION, "Ganho travado",
                            f"O peso não está subindo ({sinal}), mas o objetivo é ganhar massa.",
                            "Somar ~125 kcal/dia e reavaliar em 2 semanas. Sem pressa: ganho magro é lento.",
                            adjustment={"kcal_delta": 125})]
        if pct >= BULK_FAST_GAIN:
            return [Finding("fast_gain", SEV_ATTENTION, "Ganhando rápido demais",
                            f"O ganho está em {sinal} — acima disso, boa parte vira gordura.",
                            "Reduzir ~100 kcal/dia pra segurar o ganho num ritmo mais magro.",
                            adjustment={"kcal_delta": -100})]
        return [Finding("on_track_bulk", SEV_INFO, "Ganho magro no ritmo",
                        f"Ganho controlado ({sinal}), do jeito que preserva definição.")]

    # manutenção / recomposição / performance: só sinaliza deriva grande.
    if goal in {"manutencao", "recomposicao", "performance"} and abs(pct) > MAINTAIN_DRIFT:
        delta = -100 if pct > 0 else 100  # empurra no sentido oposto da deriva
        return [Finding("weight_drift", SEV_ATTENTION, "Peso derivando",
                        f"O objetivo é manter, mas o peso está mudando a {sinal}.",
                        f"Ajustar {'−' if delta < 0 else '+'}100 kcal/dia no sentido oposto pra estabilizar.",
                        adjustment={"kcal_delta": delta})]
    return []


def _nutrition_findings(m: Metrics) -> list[Finding]:
    out: list[Finding] = []
    n = m.nutrition
    alvo = _protein_target(m)
    if alvo and n.avg_protein_logged is not None and n.days_logged >= 5:
        if n.avg_protein_logged < alvo * PROTEIN_LOW_RATIO:
            out.append(Finding("low_protein", SEV_ACTION, "Proteína abaixo do ideal",
                               f"Média de {n.avg_protein_logged:.0f} g/dia, alvo ~{alvo:.0f} g "
                               f"({PROTEIN_G_PER_KG_TARGET:g} g/kg). Proteína é o que segura o músculo em "
                               "qualquer objetivo.",
                               "Somar uma fonte de proteína por refeição (ovo, frango, whey, iogurte, "
                               "carne magra) até chegar perto do alvo."))
    return out


def _training_findings(m: Metrics) -> list[Finding]:
    out: list[Finding] = []
    t = m.training
    # Só cobra frequência se a janela é longa o bastante pra ser justo.
    if t.window_days >= 14 and t.sessions_per_week < MIN_SESSIONS_PER_WEEK:
        out.append(Finding("low_frequency", SEV_ATTENTION, "Frequência de treino baixa",
                           f"Média de {t.sessions_per_week:.1f} treinos/semana. Abaixo de 2x por grupo muscular "
                           "o estímulo pra crescer/manter cai bastante.",
                           "Mirar pelo menos 2–3 treinos por semana, mesmo que mais curtos."))

    # Progressão travada num exercício principal — o coach avisa antes de virar
    # frustração. Orientação, não ajuste automático (isso é do lado do treino).
    for lift in t.stalled_lifts:
        nome = lift["name"]
        out.append(Finding(
            f"stalled_lift:{nome}", SEV_ATTENTION, f"{nome} empacou",
            f"Você treinou {nome} em {lift['sessions']} sessões nos últimos {lift['span_days']} dias, mas a "
            "carga/reps não subiu. Estagnar por semanas costuma ser recuperação, técnica ou volume — não força.",
            "Tenta uma progressão pequena: some 1 rep por série até fechar o topo da faixa, aí sobe a carga. "
            "Se não render, confira sono, proteína e um deload leve."))
    return out


def _sleep_findings(m: Metrics) -> list[Finding]:
    out: list[Finding] = []
    s = m.sleep
    if s.nights >= 3:
        if s.avg_hours is not None and s.avg_hours < SLEEP_SHORT_HOURS:
            out.append(Finding("short_sleep", SEV_ATTENTION, "Sono curto",
                               f"Média de {s.avg_hours:.1f} h/noite. Sono é quando o corpo recupera e regula "
                               "o apetite — dormir pouco atrapalha treino e dieta.",
                               "Tentar antecipar a hora de dormir aos poucos (15 min por vez) rumo a 7–8 h."))
        elif s.avg_quality is not None and s.avg_quality < SLEEP_LOW_QUALITY:
            out.append(Finding("low_sleep_quality", SEV_INFO, "Qualidade do sono baixa",
                               f"Qualidade média {s.avg_quality:.1f}/5. Vale cuidar do ritual antes de dormir "
                               "(tela, luz, cafeína à tarde).", None))
    return out


def _data_gaps(m: Metrics) -> list[str]:
    gaps: list[str] = []
    w = m.weight
    if w.points < MIN_WEIGHT_POINTS or w.span_days < MIN_WEIGHT_SPAN_DAYS:
        gaps.append("Registre o peso 2–3× por semana pra eu ler sua tendência (mesmo horário, em jejum).")
    ratio = m.nutrition.days_logged / m.nutrition.window_days if m.nutrition.window_days else 0
    if ratio < MIN_LOGGING_RATIO:
        gaps.append("Registre as refeições na maioria dos dias — sem isso a análise de dieta fica no escuro.")
    if m.sleep.nights == 0:
        gaps.append("Registrar o sono ajuda a explicar oscilações de treino e fome.")
    return gaps


def analyze(m: Metrics) -> WeeklyAnalysis:
    findings: list[Finding] = []
    findings += _weight_findings(m)
    findings += _nutrition_findings(m)
    findings += _training_findings(m)
    findings += _sleep_findings(m)
    gaps = _data_gaps(m)

    # Ordena por severidade (ação > atenção > info) pra o topo mostrar o que importa.
    ordem = {SEV_ACTION: 0, SEV_ATTENTION: 1, SEV_INFO: 2}
    findings.sort(key=lambda f: ordem.get(f.severity, 3))

    tem_peso = m.weight.points >= MIN_WEIGHT_POINTS and m.weight.span_days >= MIN_WEIGHT_SPAN_DAYS
    tem_dieta = (m.nutrition.days_logged / m.nutrition.window_days if m.nutrition.window_days else 0) >= MIN_LOGGING_RATIO
    has_enough = tem_peso or tem_dieta

    if not has_enough:
        confidence = "baixa"
    elif tem_peso and tem_dieta:
        confidence = "alta"
    else:
        confidence = "parcial"

    headline = _headline(m, findings, has_enough)
    return WeeklyAnalysis(
        window_days=m.window_days,
        goal=m.goal,
        has_enough_data=has_enough,
        confidence=confidence,
        headline=headline,
        findings=findings,
        data_gaps=gaps,
        metrics=_metrics_public(m),
    )


def _headline(m: Metrics, findings: list[Finding], has_enough: bool) -> str:
    if not has_enough:
        return "Ainda faltam dados pra uma análise firme — registre mais alguns dias e eu te mostro o quadro."
    acoes = [f for f in findings if f.severity == SEV_ACTION]
    if acoes:
        return acoes[0].title + " — tenho um ajuste pra sugerir."
    atencao = [f for f in findings if f.severity == SEV_ATTENTION]
    if atencao:
        return atencao[0].title + " — vale um pequeno ajuste."
    return "Você está no caminho. Sem mudanças por agora — mantém a consistência."


def _metrics_public(m: Metrics) -> dict:
    """Números que a tela mostra (resumo legível, não o dump inteiro)."""
    return {
        "window_days": m.window_days,
        "goal": m.goal,
        "weight_kg": m.weight_kg,
        "weight_trend_kg_per_week": m.weight.trend_kg_per_week,
        "weight_pct_per_week": m.weight.pct_bodyweight_per_week,
        "weight_points": m.weight.points,
        "avg_kcal": m.nutrition.avg_kcal_logged,
        "goal_kcal": m.nutrition.goal_kcal,
        "avg_protein_g": m.nutrition.avg_protein_logged,
        "protein_target_g": _protein_target(m),
        "days_logged": m.nutrition.days_logged,
        "sessions_per_week": m.training.sessions_per_week,
        "avg_sleep_hours": m.sleep.avg_hours,
    }
