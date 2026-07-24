"""Seed CURADO da biblioteca de exercícios (lista pedida pelo usuário).

117 exercícios com nome limpo em PT-BR, grupo muscular, equipamento e
dificuldade corretos, cobrindo peito, costas, ombro, bíceps, tríceps,
quadríceps, posterior/glúteo, adutores/abdutores, panturrilha e abdômen.

Idempotente: upsert por nome (is_custom=False) — reexecutar atualiza os campos
em vez de duplicar. is_compound é derivado automaticamente pelo listener do
model (classify_is_compound), então não é setado aqui.

Uso: python -m app.scripts.seed_exercises_curated
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.exercise import Difficulty, Equipment, Exercise, MuscleGroup

M = MuscleGroup
E = Equipment
D = Difficulty

# (nome, grupo principal, [grupos secundários], equipamento, dificuldade)
EXERCISES: list[tuple[str, MuscleGroup, list[MuscleGroup], Equipment, Difficulty]] = [
    # --- Peito -------------------------------------------------------------
    ("Supino reto com barra", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.BARBELL, D.INTERMEDIATE),
    ("Supino inclinado com barra", M.CHEST, [M.SHOULDERS, M.TRICEPS], E.BARBELL, D.INTERMEDIATE),
    ("Supino declinado com barra", M.CHEST, [M.TRICEPS], E.BARBELL, D.INTERMEDIATE),
    ("Supino reto com halteres", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.DUMBBELL, D.BEGINNER),
    ("Supino inclinado com halteres", M.CHEST, [M.SHOULDERS, M.TRICEPS], E.DUMBBELL, D.BEGINNER),
    ("Supino reto no Smith", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.SMITH_MACHINE, D.BEGINNER),
    ("Supino inclinado no Smith", M.CHEST, [M.SHOULDERS, M.TRICEPS], E.SMITH_MACHINE, D.BEGINNER),
    ("Supino declinado no Smith", M.CHEST, [M.TRICEPS], E.SMITH_MACHINE, D.BEGINNER),
    ("Supino máquina", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.MACHINE, D.BEGINNER),
    ("Supino inclinado máquina", M.CHEST, [M.SHOULDERS, M.TRICEPS], E.MACHINE, D.BEGINNER),
    ("Chest press", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.MACHINE, D.BEGINNER),
    ("Crucifixo reto com halteres", M.CHEST, [], E.DUMBBELL, D.BEGINNER),
    ("Crucifixo inclinado com halteres", M.CHEST, [], E.DUMBBELL, D.BEGINNER),
    ("Crossover na polia alta", M.CHEST, [], E.CABLE, D.BEGINNER),
    ("Crossover na polia média", M.CHEST, [], E.CABLE, D.BEGINNER),
    ("Crossover na polia baixa", M.CHEST, [], E.CABLE, D.BEGINNER),
    ("Peck deck", M.CHEST, [], E.MACHINE, D.BEGINNER),
    ("Flexão de braços", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.BODYWEIGHT, D.BEGINNER),
    # --- Costas ------------------------------------------------------------
    ("Puxada frontal aberta", M.BACK, [M.BICEPS], E.CABLE, D.BEGINNER),
    ("Puxada frontal pegada neutra", M.BACK, [M.BICEPS], E.CABLE, D.BEGINNER),
    ("Puxada frontal pegada fechada", M.BACK, [M.BICEPS], E.CABLE, D.BEGINNER),
    ("Barra fixa pronada", M.BACK, [M.BICEPS], E.BODYWEIGHT, D.INTERMEDIATE),
    ("Barra fixa supinada", M.BACK, [M.BICEPS], E.BODYWEIGHT, D.INTERMEDIATE),
    ("Remada curvada com barra", M.BACK, [M.BICEPS], E.BARBELL, D.INTERMEDIATE),
    ("Remada unilateral com halter", M.BACK, [M.BICEPS], E.DUMBBELL, D.BEGINNER),
    ("Remada baixa na polia", M.BACK, [M.BICEPS], E.CABLE, D.BEGINNER),
    ("Remada cavalinho", M.BACK, [M.BICEPS], E.BARBELL, D.INTERMEDIATE),
    ("Remada máquina", M.BACK, [M.BICEPS], E.MACHINE, D.BEGINNER),
    ("Remada articulada", M.BACK, [M.BICEPS], E.MACHINE, D.BEGINNER),
    ("Remada com peito apoiado", M.BACK, [M.BICEPS], E.MACHINE, D.BEGINNER),
    ("Remada com peito apoiado e halteres", M.BACK, [M.BICEPS], E.DUMBBELL, D.BEGINNER),
    ("Remada alta na máquina", M.BACK, [M.SHOULDERS, M.BICEPS], E.MACHINE, D.BEGINNER),
    ("Remada Hammer", M.BACK, [M.BICEPS], E.MACHINE, D.BEGINNER),
    ("Pulldown com braços estendidos", M.BACK, [], E.CABLE, D.BEGINNER),
    ("Pullover na máquina", M.BACK, [M.CHEST], E.MACHINE, D.BEGINNER),
    ("Pullover na polia", M.BACK, [M.CHEST], E.CABLE, D.BEGINNER),
    # --- Ombros ------------------------------------------------------------
    ("Desenvolvimento com barra", M.SHOULDERS, [M.TRICEPS], E.BARBELL, D.INTERMEDIATE),
    ("Desenvolvimento com halteres", M.SHOULDERS, [M.TRICEPS], E.DUMBBELL, D.BEGINNER),
    ("Desenvolvimento no Smith", M.SHOULDERS, [M.TRICEPS], E.SMITH_MACHINE, D.BEGINNER),
    ("Desenvolvimento na máquina", M.SHOULDERS, [M.TRICEPS], E.MACHINE, D.BEGINNER),
    ("Desenvolvimento Arnold", M.SHOULDERS, [M.TRICEPS], E.DUMBBELL, D.INTERMEDIATE),
    ("Elevação lateral com halteres", M.SHOULDERS, [], E.DUMBBELL, D.BEGINNER),
    ("Elevação lateral na polia", M.SHOULDERS, [], E.CABLE, D.BEGINNER),
    ("Elevação lateral na máquina", M.SHOULDERS, [], E.MACHINE, D.BEGINNER),
    ("Elevação frontal com halteres", M.SHOULDERS, [], E.DUMBBELL, D.BEGINNER),
    ("Elevação frontal na polia", M.SHOULDERS, [], E.CABLE, D.BEGINNER),
    ("Crucifixo inverso com halteres", M.SHOULDERS, [], E.DUMBBELL, D.BEGINNER),
    ("Crucifixo inverso na máquina", M.SHOULDERS, [], E.MACHINE, D.BEGINNER),
    ("Face pull", M.SHOULDERS, [M.TRAPS], E.CABLE, D.BEGINNER),
    ("Remada alta com barra", M.SHOULDERS, [M.TRAPS], E.BARBELL, D.INTERMEDIATE),
    # --- Bíceps ------------------------------------------------------------
    ("Rosca direta com barra reta", M.BICEPS, [M.FOREARMS], E.BARBELL, D.BEGINNER),
    ("Rosca direta com barra W", M.BICEPS, [M.FOREARMS], E.BARBELL, D.BEGINNER),
    ("Rosca alternada com halteres", M.BICEPS, [M.FOREARMS], E.DUMBBELL, D.BEGINNER),
    ("Rosca simultânea com halteres", M.BICEPS, [M.FOREARMS], E.DUMBBELL, D.BEGINNER),
    ("Rosca martelo", M.BICEPS, [M.FOREARMS], E.DUMBBELL, D.BEGINNER),
    ("Rosca Scott com barra", M.BICEPS, [], E.BARBELL, D.BEGINNER),
    ("Rosca Scott na máquina", M.BICEPS, [], E.MACHINE, D.BEGINNER),
    ("Rosca inclinada com halteres", M.BICEPS, [], E.DUMBBELL, D.BEGINNER),
    ("Rosca na polia", M.BICEPS, [], E.CABLE, D.BEGINNER),
    ("Rosca concentrada", M.BICEPS, [], E.DUMBBELL, D.BEGINNER),
    # --- Tríceps -----------------------------------------------------------
    ("Tríceps na polia com barra", M.TRICEPS, [], E.CABLE, D.BEGINNER),
    ("Tríceps corda", M.TRICEPS, [], E.CABLE, D.BEGINNER),
    ("Tríceps francês com halter", M.TRICEPS, [], E.DUMBBELL, D.BEGINNER),
    ("Tríceps francês na polia", M.TRICEPS, [], E.CABLE, D.BEGINNER),
    ("Tríceps testa com barra", M.TRICEPS, [], E.BARBELL, D.INTERMEDIATE),
    ("Tríceps testa com halteres", M.TRICEPS, [], E.DUMBBELL, D.BEGINNER),
    ("Tríceps máquina", M.TRICEPS, [], E.MACHINE, D.BEGINNER),
    ("Paralelas", M.TRICEPS, [M.CHEST, M.SHOULDERS], E.BODYWEIGHT, D.INTERMEDIATE),
    ("Supino fechado", M.TRICEPS, [M.CHEST], E.BARBELL, D.INTERMEDIATE),
    ("Tríceps coice", M.TRICEPS, [], E.DUMBBELL, D.BEGINNER),
    # --- Quadríceps --------------------------------------------------------
    ("Agachamento livre", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.BARBELL, D.INTERMEDIATE),
    ("Agachamento no Smith", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.SMITH_MACHINE, D.BEGINNER),
    ("Agachamento frontal", M.QUADS, [M.GLUTES], E.BARBELL, D.ADVANCED),
    ("Leg press 45°", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.MACHINE, D.BEGINNER),
    ("Leg press horizontal", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.MACHINE, D.BEGINNER),
    ("Hack squat", M.QUADS, [M.GLUTES], E.MACHINE, D.INTERMEDIATE),
    ("Agachamento pendular", M.QUADS, [M.GLUTES], E.MACHINE, D.INTERMEDIATE),
    ("Cadeira extensora", M.QUADS, [], E.MACHINE, D.BEGINNER),
    ("Afundo com halteres", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.DUMBBELL, D.INTERMEDIATE),
    ("Afundo no Smith", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.SMITH_MACHINE, D.INTERMEDIATE),
    ("Agachamento búlgaro", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.DUMBBELL, D.INTERMEDIATE),
    ("Passada com halteres", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.DUMBBELL, D.INTERMEDIATE),
    # --- Posterior de coxa e glúteos --------------------------------------
    ("Stiff com barra", M.HAMSTRINGS, [M.GLUTES], E.BARBELL, D.INTERMEDIATE),
    ("Stiff com halteres", M.HAMSTRINGS, [M.GLUTES], E.DUMBBELL, D.BEGINNER),
    ("Levantamento terra romeno", M.HAMSTRINGS, [M.GLUTES, M.BACK], E.BARBELL, D.INTERMEDIATE),
    ("Levantamento terra tradicional", M.HAMSTRINGS, [M.GLUTES, M.BACK], E.BARBELL, D.ADVANCED),
    ("Mesa flexora", M.HAMSTRINGS, [], E.MACHINE, D.BEGINNER),
    ("Cadeira flexora", M.HAMSTRINGS, [], E.MACHINE, D.BEGINNER),
    ("Flexora em pé", M.HAMSTRINGS, [], E.MACHINE, D.BEGINNER),
    ("Elevação pélvica com barra", M.GLUTES, [M.HAMSTRINGS], E.BARBELL, D.BEGINNER),
    ("Elevação pélvica no Smith", M.GLUTES, [M.HAMSTRINGS], E.SMITH_MACHINE, D.BEGINNER),
    ("Elevação pélvica na máquina", M.GLUTES, [M.HAMSTRINGS], E.MACHINE, D.BEGINNER),
    ("Glúteo na polia", M.GLUTES, [], E.CABLE, D.BEGINNER),
    ("Glúteo na máquina", M.GLUTES, [], E.MACHINE, D.BEGINNER),
    ("Coice na máquina", M.GLUTES, [], E.MACHINE, D.BEGINNER),
    ("Good morning", M.HAMSTRINGS, [M.GLUTES, M.BACK], E.BARBELL, D.ADVANCED),
    # --- Adutores e abdutores ---------------------------------------------
    ("Cadeira abdutora", M.GLUTES, [], E.MACHINE, D.BEGINNER),
    ("Cadeira adutora", M.QUADS, [], E.MACHINE, D.BEGINNER),
    ("Abdução de quadril na polia", M.GLUTES, [], E.CABLE, D.BEGINNER),
    ("Adução de quadril na polia", M.QUADS, [], E.CABLE, D.BEGINNER),
    # --- Panturrilhas ------------------------------------------------------
    ("Panturrilha em pé", M.CALVES, [], E.MACHINE, D.BEGINNER),
    ("Panturrilha sentada", M.CALVES, [], E.MACHINE, D.BEGINNER),
    ("Panturrilha no leg press", M.CALVES, [], E.MACHINE, D.BEGINNER),
    ("Panturrilha no Smith", M.CALVES, [], E.SMITH_MACHINE, D.BEGINNER),
    ("Panturrilha unilateral", M.CALVES, [], E.DUMBBELL, D.BEGINNER),
    # --- Abdômen -----------------------------------------------------------
    ("Abdominal supra", M.ABS, [], E.BODYWEIGHT, D.BEGINNER),
    ("Abdominal infra", M.ABS, [], E.BODYWEIGHT, D.BEGINNER),
    ("Elevação de pernas", M.ABS, [], E.BODYWEIGHT, D.BEGINNER),
    ("Elevação de joelhos na barra", M.ABS, [], E.BODYWEIGHT, D.INTERMEDIATE),
    ("Abdominal na polia", M.ABS, [], E.CABLE, D.BEGINNER),
    ("Abdominal máquina", M.ABS, [], E.MACHINE, D.BEGINNER),
    ("Prancha abdominal", M.ABS, [], E.BODYWEIGHT, D.BEGINNER),
    ("Prancha lateral", M.ABS, [], E.BODYWEIGHT, D.BEGINNER),
    ("Abdominal bicicleta", M.ABS, [], E.BODYWEIGHT, D.BEGINNER),
    ("Abdominal oblíquo", M.ABS, [], E.BODYWEIGHT, D.BEGINNER),
    ("Abdominal com roda", M.ABS, [], E.OTHER, D.INTERMEDIATE),
    ("Abdominal remador", M.ABS, [], E.BODYWEIGHT, D.BEGINNER),
]


def run() -> None:
    db = SessionLocal()
    try:
        created, updated = 0, 0
        for name, primary, secondary, equipment, difficulty in EXERCISES:
            # .first() (não one_or_none): a base importada pode já ter nomes
            # repetidos — atualiza o primeiro e não duplica o curado.
            existing = db.execute(
                select(Exercise).where(Exercise.name == name, Exercise.is_custom.is_(False))
            ).scalars().first()
            secondary_values = [g.value for g in secondary]
            if existing:
                existing.primary_muscle_group = primary
                existing.secondary_muscle_groups = secondary_values
                existing.equipment = equipment
                existing.difficulty = difficulty
                existing.is_hidden = False
                updated += 1
            else:
                db.add(
                    Exercise(
                        name=name,
                        is_custom=False,
                        primary_muscle_group=primary,
                        secondary_muscle_groups=secondary_values,
                        equipment=equipment,
                        difficulty=difficulty,
                    )
                )
                created += 1
        db.commit()
        print(f"Exercícios curados: {created} criados, {updated} atualizados (total {len(EXERCISES)}).")
    finally:
        db.close()


if __name__ == "__main__":
    run()
