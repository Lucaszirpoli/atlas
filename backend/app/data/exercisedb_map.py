"""Mapeia os campos da ExerciseDB (RapidAPI) para os enums do nosso modelo.

A ExerciseDB descreve cada exercício com `bodyPart`, `target`, `secondaryMuscles`,
`equipment`, `category` e `difficulty` — vocabulário próprio, mais fino que o
nosso. Aqui a gente reduz esse vocabulário aos enums de Exercise.

Fonte dos valores: sondagem da própria API (1394 exercícios). Um `target`/
`equipment` desconhecido cai num padrão seguro em vez de estourar — a API pode
ganhar termos novos, e um exercício com músculo "errado" é tolerável; um deploy
que quebra, não.
"""
from __future__ import annotations

from app.models.exercise import Difficulty, Equipment, ExerciseCategory, MuscleGroup

# target (músculo-alvo, mais específico que bodyPart) -> grupo muscular primário.
_TARGET_TO_MUSCLE: dict[str, MuscleGroup] = {
    "abs": MuscleGroup.ABS,
    "pectorals": MuscleGroup.CHEST,
    "serratus anterior": MuscleGroup.CHEST,
    "glutes": MuscleGroup.GLUTES,
    "abductors": MuscleGroup.GLUTES,
    "biceps": MuscleGroup.BICEPS,
    "delts": MuscleGroup.SHOULDERS,
    "triceps": MuscleGroup.TRICEPS,
    "upper back": MuscleGroup.BACK,
    "lats": MuscleGroup.BACK,
    "spine": MuscleGroup.BACK,
    "calves": MuscleGroup.CALVES,
    "quads": MuscleGroup.QUADS,
    "adductors": MuscleGroup.QUADS,
    "hamstrings": MuscleGroup.HAMSTRINGS,
    "forearms": MuscleGroup.FOREARMS,
    "traps": MuscleGroup.TRAPS,
    "levator scapulae": MuscleGroup.TRAPS,
    "cardiovascular system": MuscleGroup.CARDIO,
}

# fallback por bodyPart quando o target for desconhecido.
_BODYPART_TO_MUSCLE: dict[str, MuscleGroup] = {
    "waist": MuscleGroup.ABS,
    "chest": MuscleGroup.CHEST,
    "back": MuscleGroup.BACK,
    "shoulders": MuscleGroup.SHOULDERS,
    "upper arms": MuscleGroup.BICEPS,
    "lower arms": MuscleGroup.FOREARMS,
    "upper legs": MuscleGroup.QUADS,
    "lower legs": MuscleGroup.CALVES,
    "neck": MuscleGroup.TRAPS,
    "cardio": MuscleGroup.CARDIO,
}

_CATEGORY_MAP: dict[str, ExerciseCategory] = {
    "strength": ExerciseCategory.STRENGTH,
    "powerlifting": ExerciseCategory.POWERLIFTING,
    "olympic weightlifting": ExerciseCategory.OLYMPIC,
    "strongman": ExerciseCategory.STRONGMAN,
    "plyometrics": ExerciseCategory.PLYOMETRICS,
    "cardio": ExerciseCategory.CARDIO,
    # A ExerciseDB separa mobilidade/reabilitação/equilíbrio; nenhum é série de
    # musculação, então entram como STRETCHING — o que os mantém fora do pool
    # que a engine e a IA usam pra montar treino (STRENGTH_CATEGORIES).
    "stretching": ExerciseCategory.STRETCHING,
    "mobility": ExerciseCategory.STRETCHING,
    "rehabilitation": ExerciseCategory.STRETCHING,
    "balance": ExerciseCategory.STRETCHING,
}

_DIFFICULTY_MAP: dict[str, Difficulty] = {
    "beginner": Difficulty.BEGINNER,
    "intermediate": Difficulty.INTERMEDIATE,
    "advanced": Difficulty.ADVANCED,
}


def map_muscle(target: str | None, body_part: str | None) -> MuscleGroup:
    if target and target.lower() in _TARGET_TO_MUSCLE:
        return _TARGET_TO_MUSCLE[target.lower()]
    if body_part and body_part.lower() in _BODYPART_TO_MUSCLE:
        return _BODYPART_TO_MUSCLE[body_part.lower()]
    return MuscleGroup.FULL_BODY


def map_secondary(secondary: list[str] | None, primary: MuscleGroup) -> list[str]:
    """secondaryMuscles -> lista de grupos musculares (values), sem o primário
    e sem repetição, na ordem em que aparecem."""
    out: list[str] = []
    for m in secondary or []:
        grp = _TARGET_TO_MUSCLE.get((m or "").lower())
        if grp is None or grp == primary:
            continue
        if grp.value not in out:
            out.append(grp.value)
    return out


def map_category(category: str | None) -> ExerciseCategory:
    return _CATEGORY_MAP.get((category or "").lower(), ExerciseCategory.STRENGTH)


def map_difficulty(difficulty: str | None) -> Difficulty:
    return _DIFFICULTY_MAP.get((difficulty or "").lower(), Difficulty.INTERMEDIATE)


def map_equipment(equipment: str | None) -> Equipment:
    """A ExerciseDB tem ~35 rótulos de equipamento (muitos combinados, tipo
    "dumbbell, exercise ball"). Reduz aos 9 do nosso enum por palavra-chave,
    na ordem de prioridade (o primeiro que casar vence)."""
    e = (equipment or "").lower()
    if not e:
        return Equipment.OTHER
    # Ordem importa: "smith machine" antes de "machine"/"barbell"; "olympic
    # barbell"/"ez barbell"/"trap bar" caem em barra.
    if "smith" in e:
        return Equipment.SMITH_MACHINE
    if "kettlebell" in e:
        return Equipment.KETTLEBELL
    if "barbell" in e or "trap bar" in e:
        return Equipment.BARBELL
    if "dumbbell" in e:
        return Equipment.DUMBBELL
    if "cable" in e or "rope" in e:
        return Equipment.CABLE
    if "resistance band" in e or e == "band" or "with resistance band" in e:
        return Equipment.BAND
    if "leverage machine" in e or "sled machine" in e or e == "machine":
        return Equipment.MACHINE
    if "body weight" in e or e.startswith("assisted") or e == "weighted":
        return Equipment.BODYWEIGHT
    return Equipment.OTHER
