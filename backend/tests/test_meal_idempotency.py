"""A MESMA refeição não pode entrar duas vezes no diário.

O usuário relatou "às vezes o alimento salva duas vezes". A causa não é o dedo:
o app tem retry automático pra quando o backend está acordando (Railway
hiberna), e numa rede ruim o POST CHEGA ao servidor, a resposta se perde no
caminho de volta e o app tenta de novo — duas refeições idênticas, nenhum erro
em lugar nenhum.

A defesa é uma chave por tentativa, gerada pelo app e reenviada igual no retry:
mesma chave = mesmo registro.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.models.food import Food
from app.models.meal import MealCategory, MealLog, MealLogItem
from app.models.user import Plan, User
from app.schemas.meal import MealLogCreate, MealLogItemCreate
from app.services import meal_service


@pytest.fixture(scope="module")
def db():
    from app.core.db import SessionLocal

    s = SessionLocal()
    if s.execute(select(Food.id).limit(1)).first() is None:
        s.close()
        pytest.skip("base de alimentos não semeada neste banco")
    yield s
    s.close()


@pytest.fixture()
def cenario(db):
    """Usuário temporário + uma categoria de refeição + um alimento qualquer."""
    email = "__tmp_idem__@teste.local"

    def limpar():
        u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if u is not None:
            ids = [
                r for r in db.execute(select(MealLog.id).where(MealLog.user_id == u.id)).scalars()
            ]
            if ids:
                db.execute(delete(MealLogItem).where(MealLogItem.meal_log_id.in_(ids)))
            db.execute(delete(MealLog).where(MealLog.user_id == u.id))
            db.execute(delete(MealCategory).where(MealCategory.user_id == u.id))
            db.execute(delete(User).where(User.id == u.id))
            db.commit()

    limpar()
    u = User(email=email, handle="__tmp_id__", display_name="T", password_hash="x", plan=Plan.FREE)
    db.add(u)
    db.flush()
    cat = MealCategory(user_id=u.id, name="Almoço", sort_order=0)
    db.add(cat)
    food = db.execute(select(Food).limit(1)).scalar_one()
    db.commit()
    try:
        yield u, cat, food
    finally:
        limpar()


def _payload(cat, food, chave: str | None) -> MealLogCreate:
    return MealLogCreate(
        meal_category_id=cat.id,
        logged_at=datetime(2026, 8, 6, 12, tzinfo=timezone.utc),
        items=[MealLogItemCreate(food_id=food.id, quantity_g=100)],
        idempotency_key=chave,
    )


def test_mesma_chave_nao_registra_duas_vezes(db, cenario):
    u, cat, food = cenario
    primeiro = meal_service.log_meal(db, u.id, _payload(cat, food, "abc-123"))
    segundo = meal_service.log_meal(db, u.id, _payload(cat, food, "abc-123"))

    assert segundo.id == primeiro.id, "o retry criou uma segunda refeição"
    total = db.execute(select(MealLog).where(MealLog.user_id == u.id)).scalars().all()
    assert len(total) == 1


def test_chaves_diferentes_registram_de_verdade(db, cenario):
    """Comer o mesmo alimento duas vezes no dia é normal e PRECISA continuar
    entrando duas vezes — a chave protege do retry, não da pessoa."""
    u, cat, food = cenario
    meal_service.log_meal(db, u.id, _payload(cat, food, "k1"))
    meal_service.log_meal(db, u.id, _payload(cat, food, "k2"))

    total = db.execute(select(MealLog).where(MealLog.user_id == u.id)).scalars().all()
    assert len(total) == 2


def test_sem_chave_continua_funcionando(db, cenario):
    """Versão antiga do app (e a dieta aplicada pelo servidor) não manda chave —
    não pode quebrar nem virar tudo o mesmo registro."""
    u, cat, food = cenario
    a = meal_service.log_meal(db, u.id, _payload(cat, food, None))
    b = meal_service.log_meal(db, u.id, _payload(cat, food, None))

    assert a.id != b.id
    total = db.execute(select(MealLog).where(MealLog.user_id == u.id)).scalars().all()
    assert len(total) == 2
