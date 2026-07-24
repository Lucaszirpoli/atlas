"""Volume semanal de séries de TRABALHO por grupo muscular, baseado em
landmarks consagrados na ciência do treino (MEV = mínimo eficaz, MRV = máximo
recuperável). Usado pra decidir QUANTAS séries o coach prescreve por músculo
na semana — em vez do valor fixo antigo (sempre 3 por exercício, ignorando
músculo/nível). Sobe progressivamente do MEV ao MRV ao longo do mesociclo
(mesma lógica de weeks_accumulating do RIR) e nunca ultrapassa o teto."""

from __future__ import annotations

from app.coaching import training_brain
from app.models.exercise import MuscleGroup

# (MEV, MRV) semanais por grupo muscular pra hipertrofia, nível intermediário.
_LANDMARKS: dict[MuscleGroup, tuple[int, int]] = {
    MuscleGroup.CHEST: (8, 20),
    MuscleGroup.BACK: (10, 22),
    MuscleGroup.SHOULDERS: (8, 22),
    MuscleGroup.BICEPS: (8, 20),
    MuscleGroup.TRICEPS: (6, 18),
    MuscleGroup.QUADS: (8, 18),
    MuscleGroup.HAMSTRINGS: (6, 16),
    MuscleGroup.GLUTES: (4, 16),
    MuscleGroup.CALVES: (8, 18),
    MuscleGroup.ABS: (4, 20),
    MuscleGroup.FOREARMS: (4, 16),
    MuscleGroup.TRAPS: (4, 16),
    MuscleGroup.FULL_BODY: (8, 18),
    MuscleGroup.CARDIO: (0, 0),
}

# Iniciante recupera menos volume (fica perto do piso); avançado tolera e
# precisa de mais (perto ou um pouco acima do teto padrão) pra progredir.
_LEVEL_FACTOR = {"iniciante": 0.75, "intermediario": 1.0, "avancado": 1.15}

# Faixa segura de séries por EXERCÍCIO (depois de distribuir o volume do
# músculo entre as vagas que o treinam) — nunca deixa 1 exercício isolado
# carregar todo o volume do músculo (bug real: remada curva sozinha saindo
# com 5+ séries quando o músculo tinha poucas vagas na semana) nem virar
# quantidade irrisória. 4 é o teto de séries retas num único exercício;
# volume que não coube nesse teto fica pro próximo exercício do mesmo
# músculo em vez de empilhar tudo num só.
PER_EXERCISE_MIN = 2
PER_EXERCISE_MAX = 4


def weekly_set_range(muscle: MuscleGroup, level: str | None) -> tuple[int, int]:
    """(MEV, MRV) semanal já ajustado pro nível da pessoa."""
    mev, mrv = _LANDMARKS.get(muscle, (8, 18))
    factor = _LEVEL_FACTOR.get(level or "intermediario", 1.0)
    return max(1, round(mev * factor)), max(mev + 2, round(mrv * factor))


def weekly_target_sets(muscle: MuscleGroup, level: str | None, weeks_accumulating: float | None) -> int:
    """Total de séries de trabalho pro músculo NA SEMANA: começa perto do MEV
    (logo após deload/baseline) e sobe linearmente até o MRV ao longo do
    mesociclo (MESOCYCLE_WEEKS) — nunca passa do teto recuperável."""
    mev, mrv = weekly_set_range(muscle, level)
    progress = min(1.0, max(0.0, (weeks_accumulating or 0.0) / training_brain.MESOCYCLE_WEEKS))
    return round(mev + (mrv - mev) * progress)
