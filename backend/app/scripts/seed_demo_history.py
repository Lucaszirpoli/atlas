"""Popula 30 dias de histórico fictício (sono, treino, dieta, peso) para o
usuário de demo — só para dar dados reais ao gráfico de Evolução multi-métrica
no ambiente de desenvolvimento. NÃO faz parte do fluxo de produção nem do
init_db; é uma ferramenta manual, rodar uma vez só:

    cd backend && .venv/Scripts/python -m app.scripts.seed_demo_history

Embute de propósito uma correlação (dormiu mal -> comeu mais no dia seguinte
-> treino um pouco pior) para o usuário conseguir ver esse tipo de insight
sobrepondo métricas no gráfico.
"""

import random
from datetime import datetime, time, timedelta, timezone

from app.core.db import SessionLocal
from app.models.meal import MealLog, MealLogItem
from app.models.sleep_log import SleepLog, WakeFeeling
from app.models.user import User
from app.models.weight_log import WeightLog
from app.models.workout_session import WorkoutSession, WorkoutSetLog

DEMO_EMAIL = "lucas@appfit.com"
DAYS = 30
random.seed(42)

# exercise_id -> (nome curto, peso inicial kg, incremento por sessão kg)
EXERCISES = [
    (609, 42.0, 0.6),
    (611, 36.0, 0.5),
    (589, 32.0, 0.5),
    (592, 16.0, 0.3),
]


def day_start(offset_days_ago: int) -> datetime:
    d = datetime.now(timezone.utc) - timedelta(days=offset_days_ago)
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def main() -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if not user:
            print(f"Usuário {DEMO_EMAIL} não encontrado — rode o app e faça login uma vez antes.")
            return

        # dias -29 .. -1 (hoje já tem peso real registrado nos testes manuais,
        # deixamos hoje de fora pra não conflitar)
        offsets = list(range(DAYS - 1, 0, -1))

        poor_sleep_day: dict[int, bool] = {}
        sleep_created = 0
        for offset in offsets:
            is_poor = random.random() < 0.3
            poor_sleep_day[offset] = is_poor
            base_day = day_start(offset)
            sleep_at = base_day - timedelta(days=1) + timedelta(
                hours=23 if not is_poor else 24, minutes=random.randint(0, 45)
            )
            hours = random.uniform(5.3, 6.6) if is_poor else random.uniform(6.9, 8.6)
            wake_at = sleep_at + timedelta(hours=hours)
            quality = random.randint(1, 2) if is_poor else random.randint(3, 5)
            feeling = (
                WakeFeeling.MUITO_CANSADO
                if is_poor and quality == 1
                else WakeFeeling.CANSADO
                if is_poor
                else WakeFeeling.DESCANSADO
            )
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
            sleep_created += 1

        # Peso: a cada ~2-3 dias, tendência leve de queda ao longo do mês
        weight_created = 0
        w = 81.6
        offset = DAYS - 1
        while offset > 0:
            w += random.uniform(-0.25, 0.15)
            recorded_at = day_start(offset) + timedelta(hours=7, minutes=random.randint(0, 40))
            db.add(WeightLog(user_id=user.id, weight_kg=round(w, 1), recorded_at=recorded_at))
            weight_created += 1
            offset -= random.choice([2, 3])

        # Treino: a cada ~2-3 dias, carga progressiva, com leve queda no dia
        # seguinte a uma noite mal dormida (correlação de propósito).
        workout_created = 0
        session_count = {ex_id: 0 for ex_id, _, _ in EXERCISES}
        offset = DAYS - 1
        while offset > 0:
            prev_offset = offset + 1
            bad_day = poor_sleep_day.get(prev_offset, False)
            started_at = day_start(offset) + timedelta(hours=18, minutes=random.randint(0, 30))
            completed_at = started_at + timedelta(minutes=random.randint(45, 70))
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
                if bad_day:
                    weight *= random.uniform(0.90, 0.96)
                session_count[exercise_id] += 1
                for set_number in range(1, 5):
                    reps = random.randint(8, 12) if not bad_day else random.randint(6, 10)
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

        # Dieta: refeições todo dia, kcal mais alto no dia seguinte a uma
        # noite mal dormida.
        meal_created = 0
        for offset in offsets:
            prev_offset = offset + 1
            bad_day = poor_sleep_day.get(prev_offset, False)
            target_kcal = random.uniform(3100, 3500) + (random.uniform(500, 900) if bad_day else 0)

            splits = [("cafe", 0.25, 1), ("almoco", 0.40, 3), ("jantar", 0.35, 5)]
            base_day = day_start(offset)
            for _, frac, cat_id in splits:
                kcal = target_kcal * frac
                logged_at = base_day + timedelta(
                    hours=8 if cat_id == 1 else 12 if cat_id == 3 else 20,
                    minutes=random.randint(0, 40),
                )
                meal = MealLog(user_id=user.id, meal_category_id=cat_id, logged_at=logged_at)
                db.add(meal)
                db.flush()
                db.add(
                    MealLogItem(
                        meal_log_id=meal.id,
                        food_id=1,
                        quantity_g=100.0,
                        kcal=round(kcal),
                        protein_g=round(kcal * 0.15 / 4, 1),
                        carbs_g=round(kcal * 0.55 / 4, 1),
                        fat_g=round(kcal * 0.30 / 9, 1),
                    )
                )
                meal_created += 1

        db.commit()
        print(
            f"Seed concluído: {sleep_created} noites de sono, {weight_created} pesos, "
            f"{workout_created} treinos, {meal_created} refeições ao longo de {DAYS} dias."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
