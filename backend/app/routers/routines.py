from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.security import get_current_user
from app.models.exercise import Exercise
from app.models.routine import Routine, RoutineExercise
from app.models.user import User
from app.schemas.routine import RoutineCreate, RoutineRead, RoutineUpdate
from app.services import routine_service
from app.services.routine_import import parse_csv

router = APIRouter(prefix="/routines", tags=["routines"])


class ImportPreviewRequest(BaseModel):
    # Conteúdo do CSV exportado do outro app. Vem como texto: o app lê o
    # arquivo escolhido e manda — evita lidar com multipart no mobile.
    csv_content: str


class ImportedExerciseOut(BaseModel):
    nome_original: str
    exercise_id: int | None
    exercise_nome: str | None
    confianca: float
    revisar: bool
    series: int
    reps_min: int
    reps_max: int | None


class ImportedRoutineOut(BaseModel):
    nome: str
    exercicios: list[ImportedExerciseOut]


class ImportPreviewResponse(BaseModel):
    rotinas: list[ImportedRoutineOut]
    total_exercicios: int
    casados: int
    para_revisar: int
    sem_par: int


@router.post("/import/preview", response_model=ImportPreviewResponse)
def import_preview(
    payload: ImportPreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Lê o CSV de outro app (Hevy, Strong, Jefit) e PROPÕE as rotinas.

    Não grava nada de propósito. Casar "Bench Press (Barbell)" com "Supino reto
    com barra" é palpite, e palpite errado aqui bagunçaria o treino da pessoa em
    silêncio — a confirmação é feita na tela, com o que ficou duvidoso marcado.
    """
    rotinas = parse_csv(db, payload.csv_content)
    if not rotinas:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Não reconheci esse arquivo. Exporte o CSV de treinos do outro app "
                "(no Hevy: Perfil → Configurações → Exportar dados)."
            ),
        )

    saida, casados, revisar, sem_par = [], 0, 0, 0
    for r in rotinas:
        for e in r.exercicios:
            if e.exercise_id is None:
                sem_par += 1
            elif e.revisar:
                revisar += 1
            else:
                casados += 1
        saida.append(
            {
                "nome": r.nome,
                "exercicios": [
                    {
                        "nome_original": e.nome_original,
                        "exercise_id": e.exercise_id,
                        "exercise_nome": e.exercise_nome,
                        "confianca": e.confianca,
                        "revisar": e.revisar,
                        "series": e.series,
                        "reps_min": e.reps_min,
                        "reps_max": e.reps_max,
                    }
                    for e in r.exercicios
                ],
            }
        )
    return {
        "rotinas": saida,
        "total_exercicios": casados + revisar + sem_par,
        "casados": casados,
        "para_revisar": revisar,
        "sem_par": sem_par,
    }


def _validate_exercises_exist(db: Session, payload_exercises: list) -> None:
    ids = {item.exercise_id for item in payload_exercises}
    found = set(db.execute(select(Exercise.id).where(Exercise.id.in_(ids))).scalars())
    missing = ids - found
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exercícios não encontrados: {sorted(missing)}",
        )


def _load(db: Session, routine_id: int, user_id: int) -> Routine:
    routine = db.execute(
        select(Routine)
        .options(selectinload(Routine.exercises).selectinload(RoutineExercise.exercise))
        .where(Routine.id == routine_id)
    ).scalar_one_or_none()
    if routine is None or routine.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rotina não encontrada")
    return routine


def _replace_exercises(db: Session, routine: Routine, payload_exercises: list) -> None:
    for existing in list(routine.exercises):
        db.delete(existing)
    db.flush()
    for idx, item in enumerate(payload_exercises):
        db.add(
            RoutineExercise(
                routine_id=routine.id,
                exercise_id=item.exercise_id,
                sort_order=idx,
                target_sets=item.target_sets,
                target_reps_min=item.target_reps_min,
                target_reps_max=item.target_reps_max,
                rest_seconds=item.rest_seconds,
                notes=item.notes,
            )
        )


@router.get("", response_model=list[RoutineRead])
def list_routines(
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Routine]:
    stmt = (
        select(Routine)
        .options(selectinload(Routine.exercises).selectinload(RoutineExercise.exercise))
        .where(Routine.user_id == current_user.id)
    )
    if not include_archived:
        stmt = stmt.where(Routine.is_archived.is_(False))
    return list(db.execute(stmt.order_by(Routine.created_at)).scalars())


@router.post("", response_model=RoutineRead, status_code=status.HTTP_201_CREATED)
def create_routine(
    payload: RoutineCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Routine:
    if not routine_service.can_create_active_routine(db, current_user.id, current_user.plan):
        limit = routine_service.ACTIVE_ROUTINE_LIMITS[current_user.plan]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Limite de {limit} rotinas ativas atingido para o plano "
                f"{current_user.plan.value}. Arquive uma rotina para criar outra."
            ),
        )

    _validate_exercises_exist(db, payload.exercises)
    routine = Routine(user_id=current_user.id, name=payload.name)
    db.add(routine)
    db.flush()
    _replace_exercises(db, routine, payload.exercises)
    db.commit()
    return _load(db, routine.id, current_user.id)


class BulkExercise(BaseModel):
    exercise_id: int
    target_sets: int = 3
    target_reps_min: int = 8
    target_reps_max: int | None = None
    rest_seconds: int = 90
    notes: str | None = None

    @field_validator("target_sets", "target_reps_min", "rest_seconds", mode="before")
    @classmethod
    def _null_vira_default(cls, v, info):
        # O plano gerado pode trazer esses campos como null (ex.: RP Training não
        # define descanso por slot). Sem isto, mandar null explícito quebrava o
        # salvamento com 422 ("Input should be a valid integer") — foi o erro na
        # tela ao salvar um método. null -> o default do campo.
        if v is None:
            return {"target_sets": 3, "target_reps_min": 8, "rest_seconds": 90}[info.field_name]
        return v


class BulkRoutine(BaseModel):
    nome: str
    exercicios: list[BulkExercise]


class BulkRoutinesRequest(BaseModel):
    rotinas: list[BulkRoutine]
    substituir_existentes: bool = False


class BulkRoutinesResponse(BaseModel):
    created: int
    archived: int
    skipped_exercises: list[int]


@router.post("/bulk", response_model=BulkRoutinesResponse, status_code=status.HTTP_201_CREATED)
def create_routines_bulk(
    payload: BulkRoutinesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BulkRoutinesResponse:
    """Cria VÁRIAS rotinas de uma vez (o treino que a IA montou), opcionalmente
    arquivando as ativas antes. Atômico: ou entra tudo, ou nada.

    Antes o app fazia isso com N chamadas soltas (1 arquivar por rotina + 1
    criar por rotina); qualquer uma falhando deixava o usuário pela metade e
    mostrava só "tente novamente". Aqui, um exercício inexistente (a IA às vezes
    erra o id) é PULADO em vez de derrubar o treino inteiro, e volta na resposta
    pra ser mostrado com transparência."""
    if not payload.rotinas:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Nenhuma rotina recebida.")

    archived = 0
    if payload.substituir_existentes:
        actives = list(
            db.execute(
                select(Routine).where(Routine.user_id == current_user.id, Routine.is_archived.is_(False))
            ).scalars()
        )
        for r in actives:
            r.is_archived = True
            archived += 1
        db.flush()

    # Filtra ids de exercício que não existem (em vez de estourar 404).
    wanted = {e.exercise_id for r in payload.rotinas for e in r.exercicios}
    existing = set(db.execute(select(Exercise.id).where(Exercise.id.in_(wanted))).scalars())
    skipped = sorted(wanted - existing)

    created = 0
    for rot in payload.rotinas:
        valid = [e for e in rot.exercicios if e.exercise_id in existing]
        if not valid:
            continue
        routine = Routine(user_id=current_user.id, name=rot.nome[:100])
        db.add(routine)
        db.flush()
        for i, e in enumerate(valid):
            db.add(
                RoutineExercise(
                    routine_id=routine.id,
                    exercise_id=e.exercise_id,
                    sort_order=i,
                    target_sets=max(1, e.target_sets),
                    target_reps_min=max(1, e.target_reps_min),
                    target_reps_max=e.target_reps_max,
                    rest_seconds=max(0, e.rest_seconds),
                    notes=e.notes,
                )
            )
        created += 1

    if created == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nenhum exercício do treino foi reconhecido na base. Peça pra IA montar de novo.",
        )

    db.commit()
    return BulkRoutinesResponse(created=created, archived=archived, skipped_exercises=skipped)


@router.get("/{routine_id}", response_model=RoutineRead)
def get_routine(
    routine_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Routine:
    return _load(db, routine_id, current_user.id)


@router.put("/{routine_id}", response_model=RoutineRead)
def update_routine(
    routine_id: int,
    payload: RoutineUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Routine:
    _validate_exercises_exist(db, payload.exercises)
    routine = _load(db, routine_id, current_user.id)
    routine.name = payload.name
    _replace_exercises(db, routine, payload.exercises)
    db.commit()
    return _load(db, routine_id, current_user.id)


@router.delete("/{routine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routine(
    routine_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    routine = _load(db, routine_id, current_user.id)
    db.delete(routine)
    db.commit()


@router.post("/{routine_id}/archive", response_model=RoutineRead)
def archive_routine(
    routine_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Routine:
    routine = _load(db, routine_id, current_user.id)
    routine.is_archived = True
    db.commit()
    return _load(db, routine_id, current_user.id)


@router.post("/{routine_id}/unarchive", response_model=RoutineRead)
def unarchive_routine(
    routine_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Routine:
    if not routine_service.can_create_active_routine(db, current_user.id, current_user.plan):
        limit = routine_service.ACTIVE_ROUTINE_LIMITS[current_user.plan]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Limite de {limit} rotinas ativas atingido para o plano {current_user.plan.value}.",
        )
    routine = _load(db, routine_id, current_user.id)
    routine.is_archived = False
    db.commit()
    return _load(db, routine_id, current_user.id)


@router.post("/{routine_id}/duplicate", response_model=RoutineRead, status_code=status.HTTP_201_CREATED)
def duplicate_routine(
    routine_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Routine:
    if not routine_service.can_create_active_routine(db, current_user.id, current_user.plan):
        limit = routine_service.ACTIVE_ROUTINE_LIMITS[current_user.plan]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Limite de {limit} rotinas ativas atingido para o plano {current_user.plan.value}.",
        )
    original = _load(db, routine_id, current_user.id)
    copy = Routine(user_id=current_user.id, name=f"{original.name} (cópia)")
    db.add(copy)
    db.flush()
    for idx, item in enumerate(original.exercises):
        db.add(
            RoutineExercise(
                routine_id=copy.id,
                exercise_id=item.exercise_id,
                sort_order=idx,
                target_sets=item.target_sets,
                target_reps_min=item.target_reps_min,
                target_reps_max=item.target_reps_max,
                rest_seconds=item.rest_seconds,
                notes=item.notes,
            )
        )
    db.commit()
    return _load(db, copy.id, current_user.id)
