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

from app.coaching import training_brain
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

VOLUME_DROP_DELOAD = -8  # queda de carga (%) a partir da qual o coach oferece deload


def _deload_worthy(m: Metrics) -> bool:
    """True quando a carga caiu o bastante pra o coach sugerir uma semana leve.
    Enquanto isso vale, ele NÃO manda subir carga — seria um paradoxo."""
    v = m.training.volume_trend_pct
    return v is not None and v <= VOLUME_DROP_DELOAD


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
class Insight:
    """Barra horizontal por dimensão (peso/calorias/macros/sono/carga/treino),
    SEMPRE presente, explicando o status EM RELAÇÃO AO OBJETIVO. `chart` diz qual
    gráfico abrir ao tocar no ícone; `finding_key`+`adjustment` só quando há um
    ajuste aplicável (ex.: caloria)."""

    key: str            # peso | calorias | macros | sono | carga | treino
    severity: str
    title: str
    detail: str
    chart: str | None = None
    finding_key: str | None = None
    adjustment: dict | None = None


@dataclass
class WeeklyAnalysis:
    window_days: int
    goal: str | None
    has_enough_data: bool
    confidence: str          # "alta" | "parcial" | "baixa"
    headline: str
    findings: list[Finding] = field(default_factory=list)
    insights: list[Insight] = field(default_factory=list)
    data_gaps: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# Ritmo de peso ideal por objetivo (% do peso corporal por semana; sinal importa).
_GOAL_WEIGHT_TARGET = {
    "emagrecimento": -0.5,
    "hipertrofia": 0.25,
    "manutencao": 0.0,
    "recomposicao": 0.0,
    "performance": 0.0,
}


def _pct_off(actual: float, target: float) -> str:
    """'~X% do esperado' quando indo na direção certa."""
    if target == 0:
        return ""
    return f" — cerca de {abs(round(actual / target * 100))}% do esperado"


def _peso_insight(m: Metrics) -> Insight:
    w = m.weight
    # Ajuste aplicável (vem do finding de peso, se houver) — o botão fica aqui.
    wf = _weight_findings(m)
    adj_key = next((f.key for f in wf if f.adjustment), None)
    adj = next((f.adjustment for f in wf if f.adjustment), None)

    if w.points < MIN_WEIGHT_POINTS or w.span_days < MIN_WEIGHT_SPAN_DAYS or w.pct_bodyweight_per_week is None:
        return Insight("peso", SEV_INFO, "Peso", "Registre o peso 2–3× por semana (mesmo horário, em jejum) "
                       "pra eu ler sua tendência.", chart="peso")
    pct = w.pct_bodyweight_per_week
    tgt = _GOAL_WEIGHT_TARGET.get(m.goal or "", 0.0)
    trend_txt = f"{w.trend_kg_per_week:+.2f} kg/sem ({pct:+.2f}%/sem)"

    if tgt == 0:  # manutenção/recomp/performance
        if abs(pct) <= MAINTAIN_DRIFT:
            return Insight("peso", SEV_INFO, "Peso estável", f"Seu peso está firme ({trend_txt}), como o "
                           "objetivo de manter pede. Segue assim.", chart="peso")
        return Insight("peso", SEV_ATTENTION, "Peso derivando", f"O objetivo é manter, mas o peso está a "
                       f"{trend_txt}. Vale segurar pra estabilizar.", chart="peso",
                       finding_key=adj_key, adjustment=adj)

    deveria = "perder" if tgt < 0 else "ganhar"
    direcao_certa = (tgt < 0) == (pct < 0) and abs(pct) > 0.05
    if direcao_certa and abs(pct) >= abs(tgt) * 0.7:
        return Insight("peso", SEV_INFO, "Peso no ritmo", f"Pra {m.goal} o ideal é {deveria} ~{abs(tgt):.2f}%/sem; "
                       f"você está a {abs(pct):.2f}%/sem. No ritmo certo.", chart="peso")
    if not direcao_certa:
        return Insight("peso", SEV_ACTION, "Peso fora do rumo", f"Pra {m.goal} você deveria {deveria} "
                       f"~{abs(tgt):.2f}%/sem, mas está a {trend_txt} — o oposto do esperado.", chart="peso",
                       finding_key=adj_key, adjustment=adj)
    return Insight("peso", SEV_ATTENTION, "Peso abaixo do esperado", f"Pra {m.goal} o ideal é {deveria} "
                   f"~{abs(tgt):.2f}%/sem; você está a {abs(pct):.2f}%/sem{_pct_off(pct, tgt)}.", chart="peso",
                   finding_key=adj_key, adjustment=adj)


def _calorias_insight(m: Metrics) -> Insight:
    n = m.nutrition
    if n.avg_kcal_logged is None or n.goal_kcal is None:
        return Insight("calorias", SEV_INFO, "Calorias", "Registre as refeições na maioria dos dias pra eu "
                       "comparar com a sua meta.", chart="calorias")
    diff = round(n.avg_kcal_logged - n.goal_kcal)
    if abs(diff) <= n.goal_kcal * 0.05:
        return Insight("calorias", SEV_INFO, "Calorias na meta", f"Média de {n.avg_kcal_logged} kcal/dia, "
                       f"batendo a meta de {round(n.goal_kcal)} pro seu objetivo.", chart="calorias")
    sentido = "acima" if diff > 0 else "abaixo"
    return Insight("calorias", SEV_ATTENTION, f"Calorias {sentido} da meta", f"Média de {n.avg_kcal_logged} "
                   f"kcal/dia — {abs(diff)} {sentido} da meta de {round(n.goal_kcal)} pro seu objetivo.",
                   chart="calorias")


def _macros_insight(m: Metrics) -> Insight:
    n = m.nutrition
    trios = [
        ("proteína", n.avg_protein_logged, n.goal_protein_g, "g"),
        ("carboidrato", n.avg_carbs_logged, n.goal_carbs_g, "g"),
        ("gordura", n.avg_fat_logged, n.goal_fat_g, "g"),
    ]
    if any(avg is None or goal is None for _, avg, goal, _ in trios):
        return Insight("macros", SEV_INFO, "Macros", "Registre as refeições pra eu acompanhar proteína, "
                       "carbo e gordura.", chart="macros")
    # O macro MAIS fora da meta (maior desvio relativo) manda no título.
    pior = max(trios, key=lambda t: abs(t[1] - t[2]) / (t[2] or 1))
    nome, avg, goal, u = pior
    desvio = round(avg - goal)
    resumo = ", ".join(f"{n_}: {a:.0f}/{g:.0f}{u}" for n_, a, g, u in trios)
    if abs(desvio) <= max(goal * 0.12, 8):
        return Insight("macros", SEV_INFO, "Macros no alvo", f"Média diária dentro do esperado ({resumo}).",
                       chart="macros")
    sentido = "acima" if desvio > 0 else "abaixo"
    # Proteína ACIMA do alvo não é problema — é bom (protege músculo). Só vira
    # alerta quando a proteína está BAIXA; excesso de carbo/gordura sinaliza sobra.
    if nome == "proteína" and desvio > 0:
        return Insight("macros", SEV_INFO, "Proteína acima do alvo", f"Você está com boa proteína "
                       f"({avg:.0f}{u} vs alvo {goal:.0f}{u}) — ótimo pra preservar músculo. Média dos três: "
                       f"{resumo}.", chart="macros")
    sev = SEV_ACTION if nome == "proteína" else SEV_ATTENTION
    return Insight("macros", sev, f"{nome.capitalize()} {sentido} do alvo",
                   f"Pra seu objetivo a média diária deveria ser ~{goal:.0f}{u} de {nome}, mas ficou "
                   f"{avg:.0f}{u}. Média dos três: {resumo}.", chart="macros")


def _sono_insight(m: Metrics) -> Insight:
    s = m.sleep
    if s.nights < 3 or s.avg_hours is None:
        return Insight("sono", SEV_INFO, "Sono", "Registre o sono por alguns dias — ele explica muita "
                       "oscilação de treino e fome.", chart="sono")
    alvo = 7.5
    if s.avg_hours >= SLEEP_SHORT_HOURS:
        return Insight("sono", SEV_INFO, "Sono na média", f"Média de {s.avg_hours:.1f} h/noite — dentro do que "
                       "o corpo precisa pra recuperar e sustentar seu objetivo. Continue assim.", chart="sono")
    falta = round((alvo - s.avg_hours) / alvo * 100)
    return Insight("sono", SEV_ATTENTION, "Sono curto", f"Média de {s.avg_hours:.1f} h/noite — cerca de {falta}% "
                   "abaixo do ideal (~7,5 h). Dormir pouco atrapalha treino, fome e recuperação.", chart="sono")


def _carga_insight(
    m: Metrics,
    active_deload: bool = False,
    periodization: str = "auto",
    offer_deload: bool = False,
    planned_deload: bool = False,
) -> Insight:
    # Em semana de deload, a carga CAINDO é o esperado — não re-oferecer deload
    # nem tratar como problema (senão o coach se contradiz).
    if active_deload:
        return Insight("carga", SEV_INFO, "Carga em deload", "Você está numa semana leve de propósito. Cair a "
                       "carga agora é o certo — a sobrecarga volta a subir quando o deload terminar.", chart="carga")
    v = m.training.volume_trend_pct
    if v is None:
        return Insight("carga", SEV_INFO, "Carga", "Conclua alguns treinos pra eu acompanhar sua carga total "
                       "(peso × reps).", chart="carga")
    # A periodização é quem decide se o coach OFERECE deload aqui — é o que evita
    # o paradoxo (deload + subir carga juntos).
    if offer_deload:
        if planned_deload:  # ondulatória: fim do mesociclo, deload PLANEJADO
            return Insight("carga", SEV_ATTENTION, "Fim de ciclo — hora do deload",
                           "Você vem acumulando volume e intensidade já faz um mesociclo (modelo ondulatório). "
                           "Puxar uma semana de deload agora dessensibiliza a fadiga e destrava o próximo salto — "
                           "é parte do plano, não perda de progresso.", chart="carga",
                           finding_key="deload", adjustment={"kind": "deload"})
        return Insight("carga", SEV_ATTENTION, "Carga caindo", f"Seu volume total caiu ~{abs(v):.0f}% no período. "
                       "Se não é deload proposital, pode ser fadiga acumulada — dá pra puxar uma semana leve pra "
                       "recuperar e voltar mais forte.", chart="carga",
                       finding_key="deload", adjustment={"kind": "deload"})
    if v >= 3:
        return Insight("carga", SEV_INFO, "Carga subindo", f"Seu volume total subiu ~{v:.0f}% no período — "
                       "sobrecarga progressiva acontecendo, é o que puxa o resultado.", chart="carga")
    if v <= VOLUME_DROP_DELOAD:
        # Carga caindo, mas o modo não desloada (linear): a correção é recuperar,
        # não aliviar o plano.
        if periodization == "linear":
            return Insight("carga", SEV_ATTENTION, "Carga caindo", f"Seu volume total caiu ~{abs(v):.0f}% no período. "
                           "No plano linear a gente não desloada — antes de forçar, cuida da recuperação: capriche "
                           "no sono e na proteína e segure a carga até estabilizar.", chart="carga")
        return Insight("carga", SEV_ATTENTION, "Carga caindo", f"Seu volume total caiu ~{abs(v):.0f}% no período. "
                       "Pode ser fadiga acumulada — cuida do sono e da recuperação e retoma a carga aos poucos.",
                       chart="carga")
    return Insight("carga", SEV_ATTENTION, "Carga estável", "Seu volume total está praticamente parado. Pra "
                   "evoluir, mire somar uma série ou uma repetição aos poucos.", chart="carga")


# A técnica de intensidade pra furar platô agora vem do training_brain
# (escolhida por tipo de exercício + PERÍODO do ciclo). A barra e o endpoint que
# aplica rederivam de lá — determinístico, como todo o resto do coach.


# Grupos onde uma progressão de carga costuma ser maior (grandes cadeias). Fora
# daqui (peito/costas/ombro/braço/panturrilha), o passo é o menor incremento.
_BIG_LOWER = {"quads", "hamstrings", "glutes"}


def progression_step(muscle: str, equipment: str, top_weight: float) -> tuple[float | None, float | None, str]:
    """Passo de progressão pra um exercício pronto pra subir.

    Devolve (incremento_kg, novo_peso, como-fazer). No peso corporal não há carga
    pra somar: incremento/novo_peso = None e a dica é somar reps/peso extra.
    """
    if equipment == "bodyweight":
        return None, None, (
            "Você já bate o topo das reps com folga. Suba o estímulo: some 1–2 reps por "
            "série, ou adicione carga (cinto de lastro, mochila, colete)."
        )
    inc = 5.0 if muscle in _BIG_LOWER else 2.5
    novo = round(top_weight + inc, 1)
    return inc, novo, (
        f"Você fechou o topo da faixa com folga em {top_weight:g} kg. Sobe pra {novo:g} kg na "
        f"próxima (+{inc:g} kg) e volta a trabalhar na base da faixa de reps. É assim que a "
        "sobrecarga progressiva vira resultado."
    )


def _treino_insight(
    m: Metrics,
    active_deload: bool = False,
    offer_deload: bool = False,
    period: str = "intensificacao",
    session_length: str | None = None,
    weak_points: tuple[str, ...] = (),
    applied_technique_ex_ids: frozenset[int] = frozenset(),
) -> Insight:
    t = m.training
    # Em deload, o coach NÃO manda forçar (nem progressão, nem técnica de
    # intensidade) — seria se contradizer. Foco é recuperar.
    if active_deload:
        return Insight("treino", SEV_INFO, "Semana de deload", "Você está numa semana leve pra recuperar. "
                       "Sem forçar progressão nem técnica de intensidade agora — semana que vem o coach volta a "
                       "puxar. Deload é o que permite continuar progredindo.", chart="carga")
    if t.window_days >= 14 and t.sessions_per_week < MIN_SESSIONS_PER_WEEK:
        return Insight("treino", SEV_ATTENTION, "Frequência de treino baixa", f"Média de {t.sessions_per_week:.1f} "
                       "treinos/semana. Abaixo de 2× por grupo o estímulo cai — mire 2–3×.", chart="carga")
    if t.stalled_lifts:
        # Só oferece técnica pros que AINDA não têm uma dica aplicada. Sem isto, a
        # barra reoferecia pra sempre a mesma técnica mesmo depois de aplicada (a
        # técnica não "destrava" o lift na hora — vira dica na prévia do treino),
        # e a pessoa via o botão voltar toda vez. Aqui ele some quando já aplicou.
        pendentes = [s for s in t.stalled_lifts if s["exercise_id"] not in applied_technique_ex_ids]
        if pendentes:
            lift = pendentes[0]  # o principal ainda sem técnica (compostos primeiro)
            # Técnica avançada escolhida por ponto fraco > tempo por sessão > fase
            # do ciclo (ver docstring de suggest_technique).
            is_weak_point = lift.get("muscle") in weak_points
            tech_key, tech_label, _ = training_brain.suggest_technique(
                lift["is_compound"], period, session_length=session_length, is_weak_point=is_weak_point
            )
            nomes = ", ".join(s["name"] for s in pendentes)
            return Insight(
                "treino", SEV_ATTENTION, "Progressão travada",
                f"{nomes} não subiu de carga/reps nas últimas semanas. Dá pra atacar com "
                f"{tech_label.lower()} — aplico como dica no exercício, aparece quando você for treinar.",
                chart="carga",
                finding_key=f"stalled_lift:{lift['exercise_id']}",
                adjustment={
                    "kind": "technique",
                    "technique": tech_key,
                    "technique_label": tech_label,
                    "exercise_id": lift["exercise_id"],
                    "exercise_name": lift["name"],
                },
            )
        # Todas as travas já têm técnica aplicada — vira informativo (sem botão),
        # dizendo ONDE a dica está, em vez de reoferecer o que já foi feito.
        nomes = ", ".join(s["name"] for s in t.stalled_lifts)
        return Insight(
            "treino", SEV_INFO, "Técnica aplicada na progressão travada",
            f"Já apliquei uma técnica de intensidade em {nomes}. Ela aparece na prévia do treino, "
            "no próprio exercício (é lá que você remove, se quiser). Se depois de 2–3 semanas não "
            "destravar, eu reviso a estratégia.",
            chart="carga",
        )
    # Só manda subir carga se o coach NÃO está oferecendo deload agora (senão
    # pediria deload e progressão ao mesmo tempo — paradoxo). Recuperar vem antes.
    if t.progression_lifts and not offer_deload:
        p = t.progression_lifts[0]
        inc, novo, _ = progression_step(p["muscle"], p["equipment"], p["top_weight"])
        if novo is not None:
            come = f"subir de {p['top_weight']:g} pra {novo:g} kg"
        else:
            come = "subir o estímulo (mais reps ou carga extra)"
        return Insight(
            "treino", SEV_ACTION, "Pronto pra subir a carga",
            f"Você fez {p['top_reps']} reps no {p['name']} com folga — tá na hora de {come}. "
            "Aplico como lembrete no seu treino.",
            chart="carga",
            finding_key=f"progression:{p['exercise_id']}",
            adjustment={
                "kind": "progression",
                "exercise_id": p["exercise_id"],
                "exercise_name": p["name"],
                "new_weight": novo,
            },
        )
    if t.sessions == 0:
        return Insight("treino", SEV_INFO, "Treino", "Conclua treinos pra eu acompanhar frequência e progressão.",
                       chart="carga")
    return Insight("treino", SEV_INFO, "Treino em dia", f"{t.sessions_per_week:.1f} treinos/semana e progressão "
                   "saudável. Mantém a consistência.", chart="carga")


def _insights(
    m: Metrics,
    active_deload: bool = False,
    periodization: str = "auto",
    planned_deload: bool = False,
    period: str = "intensificacao",
    session_length: str | None = None,
    weak_points: tuple[str, ...] = (),
    applied_technique_ex_ids: frozenset[int] = frozenset(),
) -> list[Insight]:
    # Decisão ÚNICA de oferecer deload (mata o paradoxo): a periodização manda.
    offer = training_brain.offer_deload(
        periodization=periodization,
        volume_worthy=_deload_worthy(m),
        planned=planned_deload,
        active_deload=active_deload,
    )
    return [
        _peso_insight(m),
        _calorias_insight(m),
        _macros_insight(m),
        _sono_insight(m),
        _carga_insight(m, active_deload, periodization, offer, planned_deload),
        _treino_insight(m, active_deload, offer, period, session_length, weak_points, applied_technique_ex_ids),
    ]


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


def analyze(
    m: Metrics,
    *,
    active_deload: bool = False,
    periodization: str = "auto",
    planned_deload: bool = False,
    period: str = "intensificacao",
    session_length: str | None = None,
    weak_points: tuple[str, ...] = (),
    applied_technique_ex_ids: frozenset[int] = frozenset(),
) -> WeeklyAnalysis:
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
        insights=_insights(m, active_deload, periodization, planned_deload, period, session_length, weak_points,
                           applied_technique_ex_ids),
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


def weekly_checkin(m: Metrics) -> dict:
    """Resumo semanal proativo — a 'mensagem de segunda' do coach. Lê a semana e
    devolve o que foi bem (wins) e o que merece foco, em linguagem curta e sem
    culpa (regra 7). Determinístico. O router chama com janela de 7 dias."""
    lines: list[dict] = []       # {key, status: good|warn|info, text}
    wins = 0

    # Treino (frequência) — o hábito que mais move o ponteiro.
    t = m.training
    if t.sessions > 0:
        if t.sessions_per_week >= MIN_SESSIONS_PER_WEEK:
            lines.append({"key": "treino", "status": "good",
                          "text": f"Treinou {t.sessions}× essa semana. Consistência em dia."})
            wins += 1
        else:
            lines.append({"key": "treino", "status": "warn",
                          "text": f"Treinou {t.sessions}× — mire 2–3× pra manter o estímulo."})
    else:
        lines.append({"key": "treino", "status": "info",
                      "text": "Nenhum treino registrado essa semana. Bora marcar o primeiro?"})

    # Peso — na direção do objetivo?
    w = m.weight
    if w.points >= 2 and w.pct_bodyweight_per_week is not None:
        tgt = _GOAL_WEIGHT_TARGET.get(m.goal or "", 0.0)
        pct = w.pct_bodyweight_per_week
        na_direcao = (tgt == 0 and abs(pct) <= MAINTAIN_DRIFT) or (tgt != 0 and (tgt < 0) == (pct < 0) and abs(pct) > 0.05)
        if na_direcao:
            lines.append({"key": "peso", "status": "good",
                          "text": f"Peso a {w.trend_kg_per_week:+.2f} kg/sem — na direção do seu objetivo."})
            wins += 1
        else:
            lines.append({"key": "peso", "status": "warn",
                          "text": f"Peso a {w.trend_kg_per_week:+.2f} kg/sem — fora do rumo do objetivo."})

    # Proteína — o macro que protege músculo.
    n = m.nutrition
    alvo = _protein_target(m)
    if alvo and n.avg_protein_logged is not None and n.days_logged >= 3:
        if n.avg_protein_logged >= alvo * PROTEIN_LOW_RATIO:
            lines.append({"key": "proteina", "status": "good",
                          "text": f"Proteína média {n.avg_protein_logged:.0f} g/dia — no alvo."})
            wins += 1
        else:
            lines.append({"key": "proteina", "status": "warn",
                          "text": f"Proteína média {n.avg_protein_logged:.0f} g/dia, abaixo do alvo (~{alvo:.0f} g)."})

    # Sono.
    s = m.sleep
    if s.nights >= 2 and s.avg_hours is not None:
        if s.avg_hours >= SLEEP_SHORT_HOURS:
            lines.append({"key": "sono", "status": "good",
                          "text": f"Sono {s.avg_hours:.1f} h/noite — recuperação em dia."})
            wins += 1
        else:
            lines.append({"key": "sono", "status": "warn",
                          "text": f"Sono {s.avg_hours:.1f} h/noite — curto; atrapalha treino e fome."})

    has_data = len(lines) > 0 and not (len(lines) == 1 and lines[0]["key"] == "treino" and t.sessions == 0)
    warns = [l for l in lines if l["status"] == "warn"]

    def _plural(n: int, sing: str, plur: str) -> str:
        return f"{n} {sing if n == 1 else plur}"

    if not has_data:
        headline = "Ainda não tenho dados dessa semana. Registra treino, peso e refeições que eu te dou o balanço."
    elif not warns:
        headline = "Semana redonda 👏 Você fez o combinado — segue nesse ritmo."
    elif wins and warns:
        headline = (f"Boa semana no geral — {_plural(wins, 'coisa no lugar', 'coisas no lugar')}. "
                    f"Fica de olho em {_plural(len(warns), 'ponto', 'pontos')}.")
    else:
        headline = "Tem alguns pontos pra ajustar essa semana — nada grave, dá pra corrigir."

    return {
        "window_days": m.window_days,
        "goal": m.goal,
        "has_data": has_data,
        "headline": headline,
        "wins_count": wins,
        "lines": lines,
    }


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
        "avg_carbs_g": m.nutrition.avg_carbs_logged,
        "goal_carbs_g": m.nutrition.goal_carbs_g,
        "avg_fat_g": m.nutrition.avg_fat_logged,
        "goal_fat_g": m.nutrition.goal_fat_g,
        "days_logged": m.nutrition.days_logged,
        "sessions_per_week": m.training.sessions_per_week,
        "volume_trend_pct": m.training.volume_trend_pct,
        "avg_sleep_hours": m.sleep.avg_hours,
        "baseline_at": m.baseline_at.isoformat() if m.baseline_at else None,
    }
