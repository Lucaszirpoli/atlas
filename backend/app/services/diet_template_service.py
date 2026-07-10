"""Monta as dietas semi-prontas (curadas em app/data/diet_templates.py) para um
usuário: calcula a meta calórica dele (objetivo + peso + altura, via Mifflin —
o MESMO cálculo da meta automática) e ESCALA as porções do molde pra bater com
essa meta. Sem IA, 100% determinístico.

Fluxo:
- `build_context`: devolve peso, altura, IMC, objetivo e meta calórica/proteína.
- `preview`: resolve os alimentos do molde na base, escala tudo pra meta e
  devolve o dia inteiro (por refeição, com gramas/kcal/macros) + os totais.
- `apply`: registra as refeições escaladas no diário de HOJE (append-only,
  reaproveita meal_service.log_meal). A pessoa pode editar/remover depois.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.data.diet_templates import DIET_TEMPLATES, get_template
from app.models.user_profile import UserProfile
from app.schemas.meal import MealLogCreate, MealLogItemCreate
from app.services import food_service, goal_service, meal_service
from app.services.nutrition_calc import compute_auto_goal

_FALLBACK_KCAL = 2000.0  # sem perfil/peso não dá pra calcular; usa uma base neutra


@dataclass(frozen=True)
class _FoodLite:
    """Só os dados do alimento que a escala precisa — NÃO o objeto ORM (que fica
    preso à sessão que o carregou e daria DetachedInstanceError se cacheado
    entre requisições)."""
    id: int
    name: str
    kcal_per_100g: float
    protein_g_per_100g: float
    carbs_g_per_100g: float
    fat_g_per_100g: float


# cache por processo pra não repetir a busca do MESMO alimento a cada request
_food_cache: dict[str, _FoodLite | None] = {}


def _resolve(db: Session, query: str) -> _FoodLite | None:
    if query in _food_cache:
        return _food_cache[query]
    matches = food_service.search_local(db, query, limit=1)
    food = matches[0] if matches else None
    lite = (
        _FoodLite(
            id=food.id,
            name=food.name,
            kcal_per_100g=food.kcal_per_100g,
            protein_g_per_100g=food.protein_g_per_100g,
            carbs_g_per_100g=food.carbs_g_per_100g,
            fat_g_per_100g=food.fat_g_per_100g,
        )
        if food is not None
        else None
    )
    _food_cache[query] = lite
    return lite


def _target_kcal_and_macros(db: Session, user_id: int) -> tuple[float, dict | None]:
    """Meta calórica da pessoa: usa a meta já definida; senão calcula do perfil."""
    current = goal_service.get_current_goal(db, user_id)
    if current is not None:
        return float(current.kcal), {
            "protein_g": current.protein_g,
            "carbs_g": current.carbs_g,
            "fat_g": current.fat_g,
        }
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).one_or_none()
    weight = goal_service.get_latest_weight_kg(db, user_id)
    if profile is not None and weight is not None:
        auto = compute_auto_goal(
            biological_sex=profile.biological_sex,
            weight_kg=weight,
            height_cm=profile.height_cm,
            age=profile.age,
            activity_level=profile.activity_level,
            goal=profile.goal,
        )
        return float(auto["kcal"]), auto
    return _FALLBACK_KCAL, None


def build_context(db: Session, user_id: int) -> dict:
    """Dados que a tela mostra ANTES de escolher: objetivo, peso, altura, IMC, meta."""
    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).one_or_none()
    weight = goal_service.get_latest_weight_kg(db, user_id)
    target_kcal, macros = _target_kcal_and_macros(db, user_id)

    imc = None
    imc_label = None
    if profile is not None and weight and profile.height_cm:
        h_m = profile.height_cm / 100.0
        imc = round(weight / (h_m * h_m), 1)
        imc_label = _imc_label(imc)

    return {
        "goal": profile.goal.value if profile else None,
        "weight_kg": weight,
        "height_cm": profile.height_cm if profile else None,
        "imc": imc,
        "imc_label": imc_label,
        "target_kcal": round(target_kcal),
        "target_protein_g": round(macros["protein_g"]) if macros else None,
        "has_goal_defined": goal_service.get_current_goal(db, user_id) is not None,
    }


def _imc_label(imc: float) -> str:
    if imc < 18.5:
        return "abaixo do peso"
    if imc < 25:
        return "peso normal"
    if imc < 30:
        return "sobrepeso"
    return "obesidade"


def _scaled_meals(db: Session, user_id: int, template: dict) -> tuple[list[dict], float, dict]:
    """Resolve os alimentos, calcula o total-base do molde e escala pra meta.
    Devolve (refeições_escaladas, fator, totais)."""
    target_kcal, _ = _target_kcal_and_macros(db, user_id)

    # 1) resolve tudo e soma o total-base do molde (nas gramas originais)
    base_kcal = 0.0
    resolved: list[tuple[dict, list[tuple[object, float]]]] = []
    for meal in template["meals"]:
        items: list[tuple[object, float]] = []
        for it in meal["items"]:
            food = _resolve(db, it["q"])
            if food is None:
                continue
            grams = float(it["g"])
            base_kcal += food.kcal_per_100g * grams / 100.0
            items.append((food, grams))
        resolved.append((meal, items))

    factor = (target_kcal / base_kcal) if base_kcal > 0 else 1.0
    # trava o fator num intervalo sensato pra não criar porções absurdas
    factor = max(0.5, min(factor, 2.5))

    totals = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    out_meals: list[dict] = []
    for meal, items in resolved:
        out_items = []
        for food, grams in items:
            g = _round_portion(grams * factor)
            k = food.kcal_per_100g * g / 100.0
            p = food.protein_g_per_100g * g / 100.0
            c = food.carbs_g_per_100g * g / 100.0
            f = food.fat_g_per_100g * g / 100.0
            totals["kcal"] += k
            totals["protein_g"] += p
            totals["carbs_g"] += c
            totals["fat_g"] += f
            out_items.append({
                "food_id": food.id,
                "food_name": food.name,
                "quantity_g": g,
                "kcal": round(k),
                "protein_g": round(p, 1),
                "carbs_g": round(c, 1),
                "fat_g": round(f, 1),
            })
        out_meals.append({"category": meal["category"], "items": out_items})

    totals = {k: round(v, 1) if k != "kcal" else round(v) for k, v in totals.items()}
    return out_meals, factor, totals


def _round_portion(g: float) -> float:
    """Arredonda a porção pra um número redondo (5g), mínimo de 5g."""
    return max(5.0, round(g / 5.0) * 5.0)


def preview(db: Session, user_id: int, template_id: str) -> dict | None:
    template = get_template(template_id)
    if template is None:
        return None
    meals, _factor, totals = _scaled_meals(db, user_id, template)
    return {
        "id": template["id"],
        "name": template["name"],
        "tagline": template["tagline"],
        "description": template["description"],
        "goals": template["goals"],
        "meals": meals,
        "totals": totals,
        "context": build_context(db, user_id),
    }


def list_templates(db: Session, user_id: int) -> dict:
    """Lista os moldes com o total de kcal JÁ escalado pra esta pessoa (pra ela
    ver de cara quanto cada dieta daria pra meta dela)."""
    items = []
    for t in DIET_TEMPLATES:
        _meals, _factor, totals = _scaled_meals(db, user_id, t)
        items.append({
            "id": t["id"],
            "name": t["name"],
            "tagline": t["tagline"],
            "description": t["description"],
            "goals": t["goals"],
            "scaled_kcal": totals["kcal"],
            "scaled_protein_g": totals["protein_g"],
        })
    return {"context": build_context(db, user_id), "templates": items}


def apply(db: Session, user_id: int, template_id: str) -> dict | None:
    """Registra a dieta escalada no diário de HOJE, uma refeição por categoria."""
    template = get_template(template_id)
    if template is None:
        return None
    meals, _factor, totals = _scaled_meals(db, user_id, template)
    categories = {c.name: c for c in meal_service.ensure_default_categories(db, user_id)}
    db.flush()

    logged_meals = 0
    logged_items = 0
    now = datetime.now(timezone.utc)
    for meal in meals:
        cat = categories.get(meal["category"])
        if cat is None or not meal["items"]:
            continue
        meal_service.log_meal(
            db,
            user_id,
            MealLogCreate(
                meal_category_id=cat.id,
                logged_at=now,
                items=[MealLogItemCreate(food_id=i["food_id"], quantity_g=i["quantity_g"]) for i in meal["items"]],
            ),
        )
        logged_meals += 1
        logged_items += len(meal["items"])
    db.commit()

    return {
        "template_name": template["name"],
        "meals_logged": logged_meals,
        "items_logged": logged_items,
        "totals": totals,
    }
