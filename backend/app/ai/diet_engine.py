"""Motor DETERMINÍSTICO de montagem de dieta — o análogo do methods_engine do
treino. Dada uma meta de macros (kcal/proteína/carbo/gordura) e as restrições
alimentares, monta um dia inteiro de refeições com alimentos REAIS da base que
BATE a meta dos 3 macros dentro de uma tolerância — sem IA, sempre válido.

A ideia que mata a imprecisão do gerador antigo (que escalava só por caloria e
deixava os macros caírem onde caíssem): aqui o CÓDIGO resolve as gramas.

Como bate os 3 macros ao mesmo tempo:
- Alimentos de porção fixa (vegetal, fruta, laticínio, proteína secundária)
  entram com gramas sensatas fixas e contribuem uma base conhecida de P/C/F.
- Sobram 3 alimentos "solucionadores" (1 proteína, 1 carbo, 1 gordura). As
  gramas deles são ajustadas por refinamento iterativo (Gauss-Seidel com
  relaxação): a cada passo, o buraco de cada macro é fechado mexendo na grama
  do alimento cujo macro-dominante é aquele. Como cada macro é dominado pelo
  seu próprio alimento, o laço converge e fecha proteína, carbo e gordura
  juntos — e, batendo os 3, a caloria sai automática (4/4/9).
- validate_diet_plan rejeita/reporta qualquer plano fora da tolerância.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.data import food_roles as fr
from app.services import food_service

KCAL_P, KCAL_C, KCAL_F = 4.0, 4.0, 9.0

# Tolerâncias da validação de fidelidade.
KCAL_TOL_FRAC = 0.07          # ±7% das calorias
MACRO_TOL_G = 12.0            # ±12g em cada macro
MACRO_TOL_FRAC = 0.12        # ou ±12% (usa o maior — metas pequenas)

# Gramas fixas dos alimentos de porção fixa (base conhecida de macros).
VEG_G = 90.0                 # por vegetal (usa 2 → 180g de vegetal/dia)
FRUIT_G = 120.0              # por fruta
DAIRY_G = 170.0

# Limites de grama pros solucionadores (evita porção absurda). 600g é o teto de
# UM alimento; como há 2-3 carbos, a capacidade total do dia é bem maior.
SOLVER_MIN_G = 0.0
SOLVER_MAX_G = 600.0


@dataclass(frozen=True)
class MacroTarget:
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


@dataclass
class _Food:
    """Alimento resolvido + gramas atuais. per-grama = per-100g / 100."""
    food_id: int
    name: str
    macro: str
    kcal100: float
    p100: float
    c100: float
    f100: float
    grams: float
    meals: tuple[str, ...]
    fixed: bool = False       # porção fixa (não é ajustada pelo solver)

    def contrib(self) -> tuple[float, float, float, float]:
        g = self.grams / 100.0
        return (self.kcal100 * g, self.p100 * g, self.c100 * g, self.f100 * g)


@dataclass
class DietPlan:
    target: MacroTarget
    meals: list[dict]                     # [{category, items:[...]}]
    totals: dict                          # {kcal, protein_g, carbs_g, fat_g}
    restrictions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "target": {
                "kcal": round(self.target.kcal),
                "protein_g": round(self.target.protein_g, 1),
                "carbs_g": round(self.target.carbs_g, 1),
                "fat_g": round(self.target.fat_g, 1),
            },
            "meals": self.meals,
            "totals": self.totals,
            "restrictions": self.restrictions,
        }


# cache por processo: query -> dados do alimento (ou None se não achou)
_resolve_cache: dict[str, dict | None] = {}


def _resolve(db: Session, query: str) -> dict | None:
    if query in _resolve_cache:
        return _resolve_cache[query]
    matches = food_service.search_local(db, query, limit=1)
    food = matches[0] if matches else None
    data = (
        {
            "food_id": food.id,
            "name": food.name,
            "kcal100": food.kcal_per_100g,
            "p100": food.protein_g_per_100g,
            "c100": food.carbs_g_per_100g,
            "f100": food.fat_g_per_100g,
        }
        if food is not None
        else None
    )
    _resolve_cache[query] = data
    return data


def _mk_food(db: Session, role: fr.FoodRole, grams: float, fixed: bool) -> _Food | None:
    data = _resolve(db, role.query)
    if data is None:
        return None
    return _Food(
        food_id=data["food_id"], name=data["name"], macro=role.macro,
        kcal100=data["kcal100"], p100=data["p100"], c100=data["c100"], f100=data["f100"],
        grams=grams, meals=role.meals, fixed=fixed,
    )


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(v, hi))


def _totals(foods: list[_Food]) -> tuple[float, float, float, float]:
    k = p = c = f = 0.0
    for fd in foods:
        dk, dp, dc, df = fd.contrib()
        k += dk; p += dp; c += dc; f += df
    return k, p, c, f


_MACRO_DENS = {"protein": "p100", "carb": "c100", "fat": "f100"}
_MACRO_IDX = {"protein": 1, "carb": 2, "fat": 3}  # posição no tuple de _totals


def _refine(foods: list[_Food], target: MacroTarget, iterations: int = 150) -> None:
    """Ajusta as gramas dos alimentos NÃO-fixos pra bater os 3 macros.
    Gauss-Seidel com relaxação: a cada macro, divide o buraco entre TODOS os
    solucionadores daquele macro (proporcional à densidade), pra ter capacidade
    (metas altas de carbo/proteína) e não estourar a grama de um só alimento.
    Ordem proteína→gordura→carbo, repetida, absorve os macros cruzados."""
    solvers: dict[str, list[_Food]] = {"protein": [], "carb": [], "fat": []}
    for fd in foods:
        if not fd.fixed and fd.macro in solvers:
            solvers[fd.macro].append(fd)
    targets = {"protein": target.protein_g, "carb": target.carbs_g, "fat": target.fat_g}
    for _ in range(iterations):
        for macro in ("protein", "fat", "carb"):
            group = solvers[macro]
            if not group:
                continue
            gap = targets[macro] - _totals(foods)[_MACRO_IDX[macro]]
            per_food_gap = gap / len(group)
            for fd in group:
                dens = getattr(fd, _MACRO_DENS[macro]) / 100.0
                if dens < 1e-4:
                    continue
                fd.grams = _clamp(fd.grams + 0.7 * per_food_gap / dens, SOLVER_MIN_G, SOLVER_MAX_G)


def _round_g(g: float) -> float:
    return max(0.0, round(g / 5.0) * 5.0)


def _distribute(foods: list[_Food], meal_names: list[str]) -> list[dict]:
    """Distribui cada alimento pelas refeições preferidas dele (só as que
    existem no plano do dia), dividindo as gramas igualmente entre elas."""
    buckets: dict[str, list[dict]] = {m: [] for m in meal_names}
    for fd in foods:
        g = _round_g(fd.grams)
        if g <= 0:
            continue
        slots = [m for m in fd.meals if m in buckets] or [meal_names[0]]
        share = g / len(slots)
        for m in slots:
            gm = _round_g(share)
            if gm <= 0:
                continue
            gr = gm / 100.0
            buckets[m].append({
                "food_id": fd.food_id,
                "food_name": fd.name,
                "quantity_g": gm,
                "kcal": round(fd.kcal100 * gr),
                "protein_g": round(fd.p100 * gr, 1),
                "carbs_g": round(fd.c100 * gr, 1),
                "fat_g": round(fd.f100 * gr, 1),
            })
    return [{"category": m, "items": buckets[m]} for m in meal_names if buckets[m]]


def build_diet_plan(
    db: Session,
    target: MacroTarget,
    restrictions: list[str] | None = None,
    meals_per_day: int = 4,
    variant: int = 0,
) -> DietPlan:
    """Monta o dia inteiro batendo os macros. `variant` roda os alimentos
    escolhidos (mesma meta, cardápio diferente) para o botão 'gerar outra'."""
    rset = frozenset(restrictions or [])
    meal_names = [fr.CAFE, fr.ALMOCO, fr.LANCHE, fr.JANTAR]
    if meals_per_day <= 3:
        meal_names = [fr.CAFE, fr.ALMOCO, fr.JANTAR]

    foods: list[_Food] = []

    # Alimentos de porção FIXA (base conhecida) -----------------------------
    veg1 = fr.pick_allowed(fr.VEGGIES, rset, variant)
    veg2 = fr.pick_allowed(fr.VEGGIES, rset, variant + 1)
    for v in (veg1, veg2):
        if v is not None:
            fd = _mk_food(db, v, VEG_G, fixed=True)
            if fd:
                foods.append(fd)

    fruit = fr.pick_allowed(fr.FRUITS, rset, variant)
    if fruit is not None:
        fd = _mk_food(db, fruit, FRUIT_G, fixed=True)
        if fd:
            foods.append(fd)

    dairy = fr.pick_allowed(fr.DAIRY, rset, variant)
    if dairy is not None:
        fd = _mk_food(db, dairy, DAIRY_G, fixed=True)
        if fd:
            foods.append(fd)

    # Alimentos SOLUCIONADORES (gramas ajustadas pra bater a meta) ----------
    # Proteína: 1 reforço denso (whey/ervilha) — bate metas altas sem estourar
    # caloria — + 1 proteína "de verdade" no prato. Carbo: 1 do café + 1 do
    # almoço/jantar (capacidade pra metas altas). Gordura: azeite (puro, preciso).
    chosen: list[tuple[fr.FoodRole | None, float]] = []
    booster = fr.pick_allowed(fr.PROTEIN_BOOSTERS, rset, variant)
    whole = fr.pick_allowed(fr.WHOLE_PROTEINS, rset, variant)
    if whole is not None and booster is not None and whole.query == booster.query:
        whole = fr.pick_allowed(fr.WHOLE_PROTEINS, rset, variant + 1)
    chosen.append((booster, 30.0))
    chosen.append((whole, 150.0))

    # Até 3 carbos distintos pra dar capacidade (metas altas de bulking). Um do
    # café (aveia/pão) quando permitido; o resto principais (arroz/tubérculo/
    # macarrão de arroz — todos sem glúten, então quem não come trigo não perde
    # capacidade). Pra metas baixas, o refinamento zera o excedente.
    carb_roles: list[fr.FoodRole] = []
    bfast_carb = fr.pick_allowed(fr.BREAKFAST_CARBS, rset, variant)
    if bfast_carb is not None:
        carb_roles.append(bfast_carb)
    off = 0
    while len(carb_roles) < 3:
        m = fr.pick_allowed(fr.MAIN_CARBS, rset, variant + off)
        off += 1
        if m is None:
            break
        if all(m.query != c.query for c in carb_roles):
            carb_roles.append(m)
        if off > len(fr.MAIN_CARBS) + 2:
            break
    for role in carb_roles:
        chosen.append((role, 120.0))

    chosen.append((fr.pick_allowed(fr.FATS, rset, variant), 15.0))

    seen_ids: set[str] = set()
    for role, g0 in chosen:
        if role is None or role.query in seen_ids:
            continue
        fd = _mk_food(db, role, g0, fixed=False)
        if fd is not None:
            seen_ids.add(role.query)
            foods.append(fd)

    _refine(foods, target)

    meals = _distribute(foods, meal_names)

    # Totais reais do plano final (a partir das gramas JÁ arredondadas).
    tot = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for meal in meals:
        for it in meal["items"]:
            tot["kcal"] += it["kcal"]
            tot["protein_g"] += it["protein_g"]
            tot["carbs_g"] += it["carbs_g"]
            tot["fat_g"] += it["fat_g"]
    tot = {k: round(v, 1) if k != "kcal" else round(v) for k, v in tot.items()}

    return DietPlan(target=target, meals=meals, totals=tot, restrictions=list(rset))


def validate_diet_plan(target: MacroTarget, plan: DietPlan) -> list[str]:
    """Lista violações da meta (vazia = plano fiel). Tolerância por macro é o
    MAIOR entre um piso em gramas e uma fração — metas pequenas não são punidas
    por poucos gramas de diferença."""
    problems: list[str] = []
    t = plan.totals

    kcal_tol = target.kcal * KCAL_TOL_FRAC
    if abs(t["kcal"] - target.kcal) > kcal_tol:
        problems.append(
            f"Calorias fora da meta: {t['kcal']} kcal vs meta {round(target.kcal)} "
            f"(tolerância ±{round(kcal_tol)})."
        )

    for label, key, tgt in (
        ("Proteína", "protein_g", target.protein_g),
        ("Carboidrato", "carbs_g", target.carbs_g),
        ("Gordura", "fat_g", target.fat_g),
    ):
        tol = max(MACRO_TOL_G, tgt * MACRO_TOL_FRAC)
        if abs(t[key] - tgt) > tol:
            problems.append(
                f"{label} fora da meta: {t[key]}g vs meta {round(tgt, 1)}g "
                f"(tolerância ±{round(tol, 1)}g)."
            )
    return problems
