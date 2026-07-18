from fastapi import APIRouter, Depends, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.exercise import Difficulty, Equipment, Exercise, MuscleGroup
from app.models.user import User
from app.schemas.exercise import ExerciseCreate, ExerciseRead

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=list[ExerciseRead])
def list_exercises(
    q: str | None = None,
    muscle_group: MuscleGroup | None = None,
    equipment: Equipment | None = None,
    difficulty: Difficulty | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Exercise]:
    stmt = select(Exercise).where(
        # is_hidden esconde a base antiga (free-exercise-db) aposentada pela
        # ExerciseDB, sem apagá-la (rotinas/histórico ainda referenciam o id).
        Exercise.is_hidden.is_(False),
        or_(Exercise.is_custom.is_(False), Exercise.created_by_user_id == current_user.id),
    )
    if q:
        # Casa pelo nome PT E pelo nome em inglês da ExerciseDB — quem tem o
        # movimento na memória em inglês ("bench press") acha o "Supino".
        stmt = stmt.where(or_(Exercise.name.ilike(f"%{q}%"), Exercise.name_en.ilike(f"%{q}%")))
    if muscle_group:
        stmt = stmt.where(Exercise.primary_muscle_group == muscle_group)
    if equipment:
        stmt = stmt.where(Exercise.equipment == equipment)
    if difficulty:
        stmt = stmt.where(Exercise.difficulty == difficulty)
    return list(db.execute(stmt.order_by(Exercise.name)).scalars())


@router.post("", response_model=ExerciseRead, status_code=status.HTTP_201_CREATED)
def create_custom_exercise(
    payload: ExerciseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Exercise:
    exercise = Exercise(is_custom=True, created_by_user_id=current_user.id, **payload.model_dump())
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise
