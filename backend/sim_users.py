"""Simulação agente-a-agente (Monte Carlo, discrete-event) de 100.000
usuários do appfit por 30 dias. Cada agente evolui por estados
(onboarded -> activated -> returning/churned -> pro) com transições
probabilísticas calibradas nos parâmetros de benchmark fornecidos.

Roda em Python puro (sem deps). Uso: python sim_users.py
"""
import random
import statistics
from collections import Counter, defaultdict

random.seed(42)
N = 100_000
DAYS = 30
PRICE = 20.0

# ---- Personas: (nome, fração, user_type, p_tech_high, willingness_weights(a,m,b),
#                 act_base, ai_value_mult, churn_bias) ----
# user_type define a prob diária base de retorno (habitual/casual/non).
BASE_RETURN = {"habitual": 0.72, "casual": 0.45, "non": 0.38}

PERSONAS = [
    # nome, frac, tipo, tech_high, (wa,wm,wb), act_base, ai_mult
    ("Iniciante sedentário",              0.08, "non",      0.20, (0.15,0.40,0.45), 0.75, 0.85),
    ("Iniciante musculação",              0.17, "casual",   0.35, (0.10,0.45,0.45), 0.58, 1.10),
    ("Intermediário hipertrofia (science)",0.15,"habitual", 0.70, (0.35,0.45,0.20), 0.50, 1.40),
    ("Intermediário old-school (bro)",    0.12, "casual",   0.25, (0.08,0.37,0.55), 0.44, 0.80),
    ("Avançado bodybuilder natural",      0.08, "habitual", 0.75, (0.40,0.42,0.18), 0.44, 1.45),
    ("Avançado science (pesquisador)",    0.06, "habitual", 0.85, (0.45,0.40,0.15), 0.40, 1.55),
    ("Crossfit / funcional",              0.10, "casual",   0.55, (0.20,0.45,0.35), 0.52, 0.95),
    ("Cardio puro (corrida/HIIT)",        0.08, "casual",   0.45, (0.12,0.45,0.43), 0.50, 0.70),
    ("Dieta restrita (vegano/alérgico)",  0.05, "casual",   0.60, (0.30,0.45,0.25), 0.55, 1.20),
    ("Casual fitness (trend/social)",     0.11, "non",      0.30, (0.05,0.35,0.60), 0.82, 0.70),
]

WILLING_CONV = {"alta": 0.40, "media": 0.10, "baixa": 0.015}  # conversão-base por encontro c/ paywall
CHURN_REASONS = [
    "Cansei / parou de motivar",
    "Prefiro outro app",
    "Não vejo progresso",
    "Muito complicado / muitos campos",
    "Falta feature específica",
    "Base de alimentos incompleta",
    "Não tenho amigos aqui",
]

def pick(weights_dict):
    r = random.random(); acc = 0
    for k, w in weights_dict.items():
        acc += w
        if r <= acc:
            return k
    return k

class Agent:
    __slots__ = ("p","tipo","tech","willing","ai_mult","act_base","food_found",
                 "onboarded","activated","pro","alive","churn_day","churn_reason",
                 "momentum","missed","seen_paywall","pro_day","invites","act_day","last_day")

# monta agentes
agents = []
persona_idx = []
cum = []
acc = 0
for i,pp in enumerate(PERSONAS):
    acc += pp[1]; cum.append(acc)

for _ in range(N):
    r = random.random()
    pi = next(i for i,c in enumerate(cum) if r <= c)
    name,frac,tipo,tech_high,ww,act_base,ai_mult = PERSONAS[pi]
    a = Agent()
    a.p = pi; a.tipo = tipo; a.ai_mult = ai_mult; a.act_base = act_base
    # tech
    a.tech = "alto" if random.random() < tech_high else ("medio" if random.random() < 0.6 else "baixo")
    # willingness
    a.willing = pick({"alta":ww[0],"media":ww[1],"baixa":ww[2]})
    # dieta restrita: achou o alimento na base? (TACO+OFF ~ mas com buracos)
    a.food_found = True if pi != 8 else (random.random() < 0.62)
    a.onboarded=False; a.activated=False; a.pro=False; a.alive=True
    a.churn_day=None; a.churn_reason=None; a.momentum=0.0; a.missed=0
    a.seen_paywall=False; a.pro_day=None; a.invites=0; a.act_day=None; a.last_day=0
    agents.append(a)

# ---------------- DIA 1-2: ONBOARDING ----------------
DESIGN_BONUS = 0.08
for a in agents:
    base = 0.70 + DESIGN_BONUS
    base += {"alto":0.10,"medio":0.05,"baixo":-0.05}[a.tech]
    # ajuste por persona (13 passos punem iniciante/casual/non; avançado tolera)
    padj = {0:-0.05,1:-0.05,2:0.03,3:-0.04,4:0.02,5:0.02,6:-0.02,7:-0.04,8:-0.03,9:-0.15}[a.p]
    base += padj
    p_onb = min(max(base, 0.05), 0.95)
    if random.random() < p_onb:
        a.onboarded = True
        a.last_day = 1
    else:
        # não concluiu: efeito install&forget — maioria some
        a.alive = False; a.churn_day = 1; a.churn_reason = "Muito complicado / muitos campos"

# ---------------- LOOP DIÁRIO (dias 2..30) ----------------
def churn_reason_for(a, day):
    w = {r:1.0 for r in CHURN_REASONS}
    if not a.activated:
        w["Muito complicado / muitos campos"] += 3.0
        w["Não vejo progresso"] += 2.0
    if a.p == 8 and not a.food_found:
        w["Base de alimentos incompleta"] += 6.0
    if a.tipo == "non" or a.p in (9,):  # casual fitness / não engajado
        w["Cansei / parou de motivar"] += 2.0
    if a.p in (6,4,2):  # avançados/science comparam com concorrentes
        w["Prefiro outro app"] += 1.5
        w["Falta feature específica"] += 1.5
    if day > 15:
        w["Cansei / parou de motivar"] += 1.5
    if a.p == 3:  # old-school
        w["Falta feature específica"] += 1.0
    tot = sum(w.values())
    return pick({k:v/tot for k,v in w.items()})

daily_active = [0]*(DAYS+1)
daily_active[1] = sum(1 for a in agents if a.alive)
pro_active_by_day = [0]*(DAYS+1)

for day in range(2, DAYS+1):
    for a in agents:
        if not a.alive:
            continue
        # prob base de retorno
        p = BASE_RETURN[a.tipo]
        # ativação ainda não atingida penaliza a partir do dia 4
        if not a.activated and day >= 4:
            p *= 0.72
        # momentum (sucessos passados) e decaimento por dias sem abrir
        p += a.momentum
        p -= 0.02 * a.missed
        # decaimento global pós-dia 7
        if day > 7:
            p -= 0.02 * (day - 7) / 6.0
        # dieta restrita que não achou comida: colapsa
        if a.p == 8 and not a.food_found:
            p -= 0.30
        p = min(max(p, 0.02), 0.95)

        if random.random() < p:
            # ABRIU o app hoje
            a.missed = 0
            a.momentum = min(a.momentum + 0.035, 0.14)
            a.last_day = day
            # tenta ativar (dias 3-7 janela principal, mas pode até dia 10)
            if not a.activated and 3 <= day <= 10:
                pa = a.act_base
                if a.p == 8 and not a.food_found:
                    pa = 0.06
                if random.random() < pa * 0.5:  # por-dia (acumula ao longo da janela)
                    a.activated = True; a.act_day = day
            # paywall: só depois de ativado e a partir do dia 8
            if a.activated and day >= 8 and not a.pro:
                if random.random() < 0.16:  # encontra trigger Pro nesse dia
                    a.seen_paywall = True
                    conv = WILLING_CONV[a.willing] * a.ai_mult
                    # timing pós-ativação já embutido (só cai aqui se ativado)
                    conv = min(conv, 0.85)
                    if random.random() < conv:
                        a.pro = True; a.pro_day = day
            # convites (network): ativado & (avançado ou pro)
            if a.activated and (a.p in (4,5,2) or a.pro):
                if random.random() < 0.02:
                    a.invites += 1
            # pagante tem forte âncora de hábito
            if a.pro:
                a.momentum = min(a.momentum + 0.02, 0.2)
        else:
            a.missed += 1
            # churn: sem abrir por X dias, ou draw aleatório de desistência
            thresh = 6 if a.tipo == "habitual" else (4 if a.tipo == "casual" else 3)
            base_quit = 0.03 if a.activated else 0.10
            if a.pro:
                base_quit *= 0.35  # pagantes desistem muito menos
            if a.missed >= thresh or random.random() < base_quit:
                a.alive = False; a.churn_day = day; a.churn_reason = churn_reason_for(a, day)
    daily_active[day] = sum(1 for a in agents if a.alive)
    pro_active_by_day[day] = sum(1 for a in agents if a.alive and a.pro)

# ---------------- AGREGAÇÃO ----------------
def pct(x, base=N):
    return 100.0 * x / base

onboarded = sum(1 for a in agents if a.onboarded)
activated = sum(1 for a in agents if a.activated)
alive_d7 = daily_active[7]
alive_d15 = daily_active[15]
alive_d30 = daily_active[30]
seen_pw = sum(1 for a in agents if a.seen_paywall)
converted = sum(1 for a in agents if a.pro)
pro_alive_d30 = sum(1 for a in agents if a.alive and a.pro)
total_invites = sum(a.invites for a in agents)

print("=== FUNIL AGREGADO (N=%d) ===" % N)
print(f"Abriu: {N} (100%)")
print(f"Onboarding concluído: {onboarded} ({pct(onboarded):.1f}%)")
print(f"Ativados (activation): {activated} ({pct(activated):.1f}%)")
print(f"D1 ativos: {daily_active[1]} ({pct(daily_active[1]):.1f}%)")
print(f"D7 ativos: {alive_d7} ({pct(alive_d7):.1f}%)")
print(f"D15 ativos: {alive_d15} ({pct(alive_d15):.1f}%)")
print(f"D30 ativos: {alive_d30} ({pct(alive_d30):.1f}%)")
print(f"Viram paywall: {seen_pw} ({pct(seen_pw):.1f}%)")
print(f"Converteram Pro (bruto): {converted} ({pct(converted):.2f}%)  |  de D7-ativos: {pct(converted,alive_d7):.1f}%  |  de quem viu paywall: {pct(converted,seen_pw):.1f}%")
print(f"Pro ATIVOS no D30: {pro_alive_d30}")
print(f"MRR (D30, pro ativos * R${PRICE:.0f}): R$ {pro_alive_d30*PRICE:,.0f}")
print(f"Convites gerados: {total_invites}  |  k-factor: {total_invites/N:.3f}")

print("\n=== CURVA DE RETENÇÃO (ativos por dia, % de N) ===")
for d in range(1, DAYS+1):
    print(f"D{d:02d}: {daily_active[d]:6d}  {pct(daily_active[d]):5.1f}%")

print("\n=== POR PERSONA ===")
print(f"{'persona':38s} {'N':>6s} {'onb%':>6s} {'D7%':>6s} {'D15%':>6s} {'D30%':>6s} {'conv%':>6s} {'proD30':>7s} {'MRR':>9s}")
for pi,pp in enumerate(PERSONAS):
    grp = [a for a in agents if a.p == pi]
    n = len(grp)
    onb = sum(1 for a in grp if a.onboarded)
    d7 = sum(1 for a in grp if a.churn_day is None or a.churn_day > 7) - sum(1 for a in grp if not a.alive and (a.churn_day or 99) <= 7)
    # recompute clean: alive at day d = churn_day is None or churn_day > d
    d7 = sum(1 for a in grp if a.churn_day is None or a.churn_day > 7)
    d15 = sum(1 for a in grp if a.churn_day is None or a.churn_day > 15)
    d30 = sum(1 for a in grp if a.churn_day is None or a.churn_day > 30) + sum(1 for a in grp if a.alive and a.churn_day is None)
    d30 = sum(1 for a in grp if a.alive)
    conv = sum(1 for a in grp if a.pro)
    proD30 = sum(1 for a in grp if a.alive and a.pro)
    mrr = proD30*PRICE
    print(f"{pp[0]:38s} {n:6d} {pct(onb,n):6.1f} {pct(d7,n):6.1f} {pct(d15,n):6.1f} {pct(d30,n):6.1f} {pct(conv,n):6.1f} {proD30:7d} {mrr:9,.0f}")

print("\n=== MOTIVOS DE CHURN (dos %d que sairam) ===" % (N-alive_d30))
reasons = Counter(a.churn_reason for a in agents if not a.alive and a.churn_reason)
tot_churn = sum(reasons.values())
for r,c in reasons.most_common():
    print(f"{r:40s} {c:6d}  {100*c/tot_churn:5.1f}%")

print("\n=== CHURN POR SEMANA ===")
for wk,(lo,hi) in enumerate([(1,7),(8,14),(15,21),(22,30)],1):
    c = sum(1 for a in agents if a.churn_day and lo <= a.churn_day <= hi)
    print(f"Semana {wk} (D{lo}-{hi}): {c} sairam ({pct(c):.1f}% do total)")

print("\n=== LTV estimado por persona (Pro) ===")
# LTV = preço / churn_mensal_pro (aprox via retenção dos pro ao longo de 30d)
for pi,pp in enumerate(PERSONAS):
    grp = [a for a in agents if a.p == pi and a.pro]
    if not grp:
        print(f"{pp[0]:38s}  sem pagantes suficientes")
        continue
    still = sum(1 for a in grp if a.alive)
    churn_m = max(1 - still/len(grp), 0.03)  # churn mensal dos que converteram
    ltv = PRICE / churn_m
    print(f"{pp[0]:38s}  pagantes={len(grp):4d}  retencao_pro_30d={100*still/len(grp):5.1f}%  churn_mensal={100*churn_m:4.1f}%  LTV≈R${ltv:6.0f}")

# conversão por disposição a pagar
print("\n=== CONVERSÃO POR DISPOSIÇÃO A PAGAR ===")
for w in ["alta","media","baixa"]:
    grp = [a for a in agents if a.willing == w]
    conv = sum(1 for a in grp if a.pro)
    print(f"{w:6s}: {conv}/{len(grp)} = {pct(conv,len(grp)):.1f}%")

# cenário com trial 3 dias (+45% conversão) — projeção
print("\n=== PROJEÇÃO: trial 3 dias grátis (+45% na conversão de quem vê paywall) ===")
extra = int(converted * 0.45)
print(f"Conversões: {converted} -> ~{converted+extra} (+{extra})  |  MRR adicional ~ R$ {extra*PRICE*0.8:,.0f}/mês")
