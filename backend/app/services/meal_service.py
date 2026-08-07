from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.food import Food
from app.models.meal import DEFAULT_MEAL_CATEGORY_NAMES, MealCategory, MealLog, MealLogItem
from app.schemas.meal import MealLogCreate, MealLogItemUpdate


def ensure_default_categories(db: Session, user_id: int) -> list[MealCategory]:
    existing = list(
        db.execute(select(MealCategory).where(MealCategory.user_id == user_id)).scalars()
    )
    if existing:
        return existing

    categories = [
        MealCategory(user_id=user_id, name=name, sort_order=idx)
        for idx, name in enumerate(DEFAULT_MEAL_CATEGORY_NAMES)
    ]
    db.add_all(categories)
    db.flush()
    return categories


def _snapshot_item(food: Food, quantity_g: float) -> dict:
    factor = quantity_g / 100.0
    return {
        "kcal": food.kcal_per_100g * factor,
        "protein_g": food.protein_g_per_100g * factor,
        "carbs_g": food.carbs_g_per_100g * factor,
        "fat_g": food.fat_g_per_100g * factor,
        "fiber_g": food.fiber_g_per_100g * factor if food.fiber_g_per_100g is not None else None,
        "sodium_mg": food.sodium_mg_per_100g * factor if food.sodium_mg_per_100g is not None else None,
        "sugar_g": food.sugar_g_per_100g * factor if food.sugar_g_per_100g is not None else None,
    }


def log_meal(db: Session, user_id: int, payload: MealLogCreate) -> MealLog:
    # MESMA CHAVE = MESMO REGISTRO. O app manda uma chave por tentativa; se ela
    # já entrou, esta chamada é a segunda cópia de um POST que o servidor já
    # atendeu (a resposta se perdeu e o app retentou) e devolver o registro
    # existente é a resposta certa — criar outro é duplicar a refeição no
    # diário, que foi o bug relatado de "salvou duas vezes".
    if payload.idempotency_key:
        ja = db.execute(
            select(MealLog).where(
                MealLog.user_id == user_id,
                MealLog.idempotency_key == payload.idempotency_key,
            ).limit(1)
        ).scalar_one_or_none()
        if ja is not None:
            return ja

    food_ids = [item.food_id for item in payload.items]
    foods = {f.id: f for f in db.execute(select(Food).where(Food.id.in_(food_ids))).scalars()}

    meal_log = MealLog(
        user_id=user_id,
        meal_category_id=payload.meal_category_id,
        logged_at=payload.logged_at,
        idempotency_key=payload.idempotency_key,
    )
    db.add(meal_log)
    db.flush()

    for item in payload.items:
        food = foods[item.food_id]
        db.add(
            MealLogItem(
                meal_log_id=meal_log.id,
                food_id=food.id,
                quantity_g=item.quantity_g,
                unit_label=item.unit_label,
                unit_amount=item.unit_amount,
                **_snapshot_item(food, item.quantity_g),
            )
        )

    db.commit()
    db.refresh(meal_log)
    return meal_log


def update_meal_item(
    db: Session, user_id: int, item_id: int, payload: MealLogItemUpdate
) -> MealLogItem | None:
    """Corrige a quantidade de um item já registrado e reconta os valores
    nutricionais (kcal/macros) pela tabela do alimento. Retorna None se o item
    não existe ou não é do usuário. Não cria histórico novo — é a correção de
    um erro de digitação na hora, permitida pelo model."""
    item = db.get(MealLogItem, item_id)
    if item is None:
        return None
    meal_log = db.get(MealLog, item.meal_log_id)
    if meal_log is None or meal_log.user_id != user_id:
        return None

    food = db.get(Food, item.food_id)
    if food is None:
        return None

    item.quantity_g = payload.quantity_g
    item.unit_label = payload.unit_label
    item.unit_amount = payload.unit_amount
    for key, value in _snapshot_item(food, payload.quantity_g).items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item


def delete_meal_item(db: Session, user_id: int, item_id: int) -> bool:
    """Remove UM alimento da refeição, sem mexer nos outros. Antes disso não
    existia — o único delete era o da refeição inteira (`MealLog`), e o "x" ao
    lado de um alimento no diário acabava apagando os outros alimentos
    registrados junto dele, que foi o bug relatado ("excluí um alimento da
    janta e excluiu todos os outros"). Se era o último item, a refeição
    (agora vazia) some junto — não faz sentido um registro sem nenhum
    alimento dentro."""
    item = db.get(MealLogItem, item_id)
    if item is None:
        return False
    meal_log = db.get(MealLog, item.meal_log_id)
    if meal_log is None or meal_log.user_id != user_id:
        return False

    db.delete(item)
    db.flush()

    restantes = db.execute(
        select(func.count()).select_from(MealLogItem).where(MealLogItem.meal_log_id == meal_log.id)
    ).scalar_one()
    if restantes == 0:
        db.delete(meal_log)

    db.commit()
    return True
