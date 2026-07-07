"""Popula ~30 dias de histórico fictício, porém realista (sono, treino,
dieta, peso) para o usuário de demo — só para dar dados coerentes ao gráfico
de Evolução multi-métrica no ambiente de desenvolvimento. NÃO faz parte do
fluxo de produção nem do init_db; é uma ferramenta manual:

    cd backend && .venv/Scripts/python -m app.scripts.seed_demo_history

É re-executável: apaga o histórico anterior do usuário de demo antes de
inserir, para não acumular nem duplicar.

Os valores simulam alguém usando o app corretamente: sono na faixa de 7-8h
(com uma noite curta aqui e ali), progressão de carga suave, calorias perto
da meta, peso caindo devagar. Há uma correlação SUTIL e realista embutida —
noite curta -> um pouco mais de caloria no dia seguinte -> carga levemente
menor no treino seguinte — pra pessoa conseguir enxergar esse tipo de relação
sobrepondo as métricas, sem exageros que deixem o gráfico caótico.
"""

import random
from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.models.meal import MealLog
from app.models.sleep_log import SleepLog, WakeFeeling
from app.models.user import User
from app.models.weight_log import WeightLog
from app.models.workout_session import WorkoutSession

DEMO_EMAIL = "lucas@appfit.com"
DAYS = 30
random.seed(7)

# exercise_id -> (peso inicial kg, incremento por sessão kg)
EXERCISES = [
    (609, 40.0, 0.5),
    (611, 34.0, 0.5),
    (589, 30.0, 0.5),
    (592, 15.0, 0.25),
]


def day_start(offset_days_ago: int) -> datetime:
    d = datetime.now(timezone.utc) - timedelta(days=offset_days_ago)
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def wipe_history(db, user_id: int) -> None:
    """Remove o histórico anterior do usuário de demo (inclui filhos via
    cascade de MealLogItem/WorkoutSetLog nas relações)."""
    for meal in db.query(MealLog).filter(MealLog.user_id == user_id).all():
        db.delete(meal)
    for sess in db.query(WorkoutSession).filter(WorkoutSession.user_id == user_id).all():
        db.delete(sess)
    db.query(SleepLog).filter(SleepLog.user_id == user_id).delete()
    db.query(WeightLog).filter(WeightLog.user_id == user_id).delete()
    db.flush()


def main() -> None:
    # importa aqui pra evitar ciclo e deixar claro que são usados no seed
    from app.models.meal import MealLogItem
    from app.models.workout_session import WorkoutSetLog

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if not user:
            print(f"Usuário {DEMO_EMAIL} não encontrado — faça login uma vez antes.")
            return

        wipe_history(db, user.id)

        offsets = list(range(DAYS - 1, -1, -1))  # inclui hoje

        # --- Sono: 7-8h com uma noite curta ocasional (~22%) ---------------
        poor_sleep_day: dict[int, bool] = {}
        for offset in offsets:
            is_short = random.random() < 0.22
            poor_sleep_day[offset] = is_short
            base_day = day_start(offset)
            sleep_at = base_day - timedelta(days=1) + timedelta(
                hours=23, minutes=random.randint(0, 40)
            )
            hours = random.uniform(6.0, 6.6) if is_short else random.uniform(6.9, 8.2)
            wake_at = sleep_at + timedelta(hours=hours)
            quality = random.randint(2, 3) if is_short else random.randint(3, 5)
            feeling = WakeFeeling.CANSADO if is_short else WakeFeeling.DESCANSADO
            db.add(
                SleepLog(
                    user_id=user.id,
                    sleep_at=sleep_at,
                    wake_at=wake_at,
                    quality=quality,
                    wake_feeling=feeling,
                    notes=None,
                )
            )

        # --- Peso: queda leve e suave ao longo do mês, log a cada 2-3 dias -
        weight_created = 0
        offset = DAYS - 1
        while offset >= 0:
            day_index = (DAYS - 1) - offset
            w = 80.6 - 0.03 * day_index + random.uniform(-0.2, 0.2)
            recorded_at = day_start(offset) + timedelta(hours=7, minutes=random.randint(0, 30))
            db.add(WeightLog(user_id=user.id, weight_kg=round(w, 1), recorded_at=recorded_at))
            weight_created += 1
            offset -= random.choice([2, 3])

        # --- Treino: a cada 2-3 dias, progressão suave; leve queda no dia
        #     seguinte a uma noite curta (correlação sutil) -----------------
        workout_created = 0
        session_count = {ex_id: 0 for ex_id, _, _ in EXERCISES}
        offset = DAYS - 1
        while offset >= 0:
            bad = poor_sleep_day.get(offset + 1, False)
            started_at = day_start(offset) + timedelta(hours=18, minutes=random.randint(0, 30))
            completed_at = started_at + timedelta(minutes=random.randint(48, 65))
            session = WorkoutSession(
                user_id=user.id,
                routine_id=1,
                started_at=started_at,
                completed_at=completed_at,
            )
            db.add(session)
            db.flush()

            for sort_order, (exercise_id, base_weight, increment) in enumerate(EXERCISES):
                n = session_count[exercise_id]
                weight = base_weight + increment * n
                if bad:
                    weight *= 0.97  # ~3% a menos, sutil
                session_count[exercise_id] += 1
                for set_number in range(1, 5):
                    reps = random.randint(8, 10) if bad else random.randint(9, 12)
                    db.add(
                        WorkoutSetLog(
                            session_id=session.id,
                            exercise_id=exercise_id,
                            exercise_sort_order=sort_order,
                            set_number=set_number,
                            weight_kg=round(weight, 1),
                            reps=reps,
                            completed_at=completed_at,
                        )
                    )
            workout_created += 1
            offset -= random.choice([2, 3])

        # --- Dieta: perto da meta, com um pouco mais de kcal no dia seguinte
        #     a uma noite curta -------------------------------------------
        meal_created = 0
        for offset in offsets:
            bad = poor_sleep_day.get(offset + 1, False)
            target_kcal = random.uniform(2900, 3300) + (random.uniform(150, 350) if bad else 0)
            splits = [(0.25, 1, 8), (0.40, 3, 12), (0.35, 5, 20)]  # frac, cat_id, hora
            base_day = day_start(offset)
            for frac, cat_id, hour in splits:
                kcal = target_kcal * frac
                logged_at = base_day + timedelta(hours=hour, minutes=random.randint(0, 40))
                meal = MealLog(user_id=user.id, meal_category_id=cat_id, logged_at=logged_at)
                db.add(meal)
                db.flush()
                db.add(
                    MealLogItem(
                        meal_log_id=meal.id,
                        food_id=1,
                        quantity_g=100.0,
                        kcal=round(kcal),
                        protein_g=round(kcal * 0.30 / 4, 1),
                        carbs_g=round(kcal * 0.45 / 4, 1),
                        fat_g=round(kcal * 0.25 / 9, 1),
                    )
                )
                meal_created += 1

        db.commit()
        print(
            f"Seed concluído: {len(offsets)} noites de sono, {weight_created} pesos, "
            f"{workout_created} treinos, {meal_created} refeições ao longo de {DAYS} dias."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
