"""Seed CURADO da biblioteca de exercícios — a ÚNICA lista visível no app.

Cada exercício aqui tem uma imagem conferida visualmente no pacote
`app/static/exercise_images/curated/`. A regra do produto é: **só existe no app
exercício que tem imagem**. Uma foto errada (ou nenhuma) ensina o movimento
errado, então a lista de imagens é a fonte da verdade da biblioteca.

O que este seed faz, nesta ordem:

1. upsert por nome (is_custom=False) dos exercícios abaixo, forçando
   `is_hidden=False`, `category=STRENGTH` e a `video_url` do arquivo de imagem;
2. **esconde todo o resto** (`is_hidden=True` em qualquer exercício não-custom
   fora da lista). Esconder, nunca apagar: rotinas e histórico referenciam o id
   por FK, e apagar quebraria o passado de quem já treinou.

Exercícios criados pelo próprio usuário (`is_custom=True`) não são tocados.

Idempotente — roda em todo boot (ver `init_db.py`) sem duplicar nada.

Uso: python -m app.scripts.seed_exercises_curated
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.exercise import Difficulty, Equipment, Exercise, ExerciseCategory, MuscleGroup

M = MuscleGroup
E = Equipment
D = Difficulty

# Pasta (relativa a app/static) onde vivem as imagens do pacote curado. O
# nome do arquivo é a chave estável entre dev e produção — o id inteiro do
# exercício muda de banco pra banco, o nome do arquivo não.
IMAGE_DIR = Path(__file__).parent.parent / "static" / "exercise_images" / "curated"
IMAGE_URL_PREFIX = "/static/exercise_images/curated"

# (nome, grupo principal, [grupos secundários], equipamento, dificuldade, imagem)
#
# Nota sobre imagens repetidas: alguns aparelhos diferentes compartilham o mesmo
# GIF de origem (as três remadas de máquina, abdução/adução na polia). São
# exercícios distintos de verdade — só a ilustração é genérica.
EXERCISES: list[tuple[str, MuscleGroup, list[MuscleGroup], Equipment, Difficulty, str]] = [
    # --- Peito -------------------------------------------------------------
    ("Supino reto com barra", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.BARBELL, D.INTERMEDIATE, "0025_supino_reto_com_barra.gif"),
    ("Supino inclinado com barra", M.CHEST, [M.SHOULDERS, M.TRICEPS], E.BARBELL, D.INTERMEDIATE, "0047_supino_inclinado_com_barra.gif"),
    ("Supino declinado com barra", M.CHEST, [M.TRICEPS], E.BARBELL, D.INTERMEDIATE, "0033_supino_declinado_com_barra.gif"),
    ("Supino reto com halteres", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.DUMBBELL, D.BEGINNER, "0289_supino_reto_com_halteres.gif"),
    ("Supino inclinado com halteres", M.CHEST, [M.SHOULDERS, M.TRICEPS], E.DUMBBELL, D.BEGINNER, "0314_supino_inclinado_com_halteres.gif"),
    ("Supino reto no Smith", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.SMITH_MACHINE, D.BEGINNER, "0748_supino_reto_no_smith.gif"),
    ("Supino inclinado no Smith", M.CHEST, [M.SHOULDERS, M.TRICEPS], E.SMITH_MACHINE, D.BEGINNER, "0757_supino_inclinado_no_smith.gif"),
    ("Supino declinado no Smith", M.CHEST, [M.TRICEPS], E.SMITH_MACHINE, D.BEGINNER, "0753_supino_declinado_no_smith.gif"),
    ("Supino máquina", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.MACHINE, D.BEGINNER, "0577_supino_maquina.gif"),
    ("Supino inclinado máquina", M.CHEST, [M.SHOULDERS, M.TRICEPS], E.MACHINE, D.BEGINNER, "1479_supino_inclinado_maquina.gif"),
    ("Chest press", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.MACHINE, D.BEGINNER, "0576_chest_press.gif"),
    ("Crucifixo reto com halteres", M.CHEST, [], E.DUMBBELL, D.BEGINNER, "0308_crucifixo_reto_com_halteres.gif"),
    ("Crucifixo inclinado com halteres", M.CHEST, [], E.DUMBBELL, D.BEGINNER, "0319_crucifixo_inclinado_com_halteres.gif"),
    ("Crossover na polia alta", M.CHEST, [], E.CABLE, D.BEGINNER, "0155_crossover_na_polia_alta.gif"),
    ("Crossover na polia média", M.CHEST, [], E.CABLE, D.BEGINNER, "0188_crossover_na_polia_media.gif"),
    ("Crossover na polia baixa", M.CHEST, [], E.CABLE, D.BEGINNER, "0179_crossover_na_polia_baixa.gif"),
    ("Peck deck", M.CHEST, [], E.MACHINE, D.BEGINNER, "0596_peck_deck.gif"),
    ("Flexão de braços", M.CHEST, [M.TRICEPS, M.SHOULDERS], E.BODYWEIGHT, D.BEGINNER, "0662_flexao_de_bracos.gif"),
    # --- Costas ------------------------------------------------------------
    ("Puxada frontal aberta", M.BACK, [M.BICEPS], E.CABLE, D.BEGINNER, "0197_puxada_frontal_aberta.gif"),
    ("Puxada frontal pegada neutra", M.BACK, [M.BICEPS], E.CABLE, D.BEGINNER, "0150_puxada_frontal_pegada_neutra.gif"),
    ("Puxada frontal pegada fechada", M.BACK, [M.BICEPS], E.CABLE, D.BEGINNER, "0974_puxada_frontal_pegada_fechada.gif"),
    ("Barra fixa pronada", M.BACK, [M.BICEPS], E.BODYWEIGHT, D.INTERMEDIATE, "0652_barra_fixa_pronada.gif"),
    ("Barra fixa supinada", M.BACK, [M.BICEPS], E.BODYWEIGHT, D.INTERMEDIATE, "1326_barra_fixa_supinada.gif"),
    ("Remada curvada com barra", M.BACK, [M.BICEPS], E.BARBELL, D.INTERMEDIATE, "0027_remada_curvada_com_barra.gif"),
    ("Remada unilateral com halter", M.BACK, [M.BICEPS], E.DUMBBELL, D.BEGINNER, "0292_remada_unilateral_com_halter.gif"),
    ("Remada baixa na polia", M.BACK, [M.BICEPS], E.CABLE, D.BEGINNER, "0180_remada_baixa_na_polia.gif"),
    ("Remada cavalinho", M.BACK, [M.BICEPS], E.BARBELL, D.INTERMEDIATE, "1349_remada_cavalinho.gif"),
    ("Remada máquina", M.BACK, [M.BICEPS], E.MACHINE, D.BEGINNER, "1350_remada_maquina.gif"),
    ("Remada articulada", M.BACK, [M.BICEPS], E.MACHINE, D.BEGINNER, "0581_remada_articulada.gif"),
    ("Remada com peito apoiado", M.BACK, [M.BICEPS], E.MACHINE, D.BEGINNER, "1350_remada_com_peito_apoiado.gif"),
    ("Remada com peito apoiado e halteres", M.BACK, [M.BICEPS], E.DUMBBELL, D.BEGINNER, "0327_remada_com_peito_apoiado_e_halteres.gif"),
    ("Remada alta na máquina", M.BACK, [M.SHOULDERS, M.BICEPS], E.MACHINE, D.BEGINNER, "0581_remada_alta_na_maquina.gif"),
    ("Remada Hammer", M.BACK, [M.BICEPS], E.MACHINE, D.BEGINNER, "1350_remada_hammer.gif"),
    ("Pulldown com braços estendidos", M.BACK, [], E.CABLE, D.BEGINNER, "0237_pulldown_com_bracos_estendidos.gif"),
    ("Pullover na máquina", M.BACK, [M.CHEST], E.MACHINE, D.BEGINNER, "2285_pullover_na_maquina.gif"),
    ("Pullover na polia", M.BACK, [M.CHEST], E.CABLE, D.BEGINNER, "0184_pullover_na_polia.gif"),
    # --- Ombros ------------------------------------------------------------
    ("Desenvolvimento com barra", M.SHOULDERS, [M.TRICEPS], E.BARBELL, D.INTERMEDIATE, "0091_desenvolvimento_com_barra.gif"),
    ("Desenvolvimento com halteres", M.SHOULDERS, [M.TRICEPS], E.DUMBBELL, D.BEGINNER, "0405_desenvolvimento_com_halteres.gif"),
    ("Desenvolvimento no Smith", M.SHOULDERS, [M.TRICEPS], E.SMITH_MACHINE, D.BEGINNER, "0766_desenvolvimento_no_smith.gif"),
    ("Desenvolvimento na máquina", M.SHOULDERS, [M.TRICEPS], E.MACHINE, D.BEGINNER, "2318_desenvolvimento_na_maquina.gif"),
    ("Desenvolvimento Arnold", M.SHOULDERS, [M.TRICEPS], E.DUMBBELL, D.INTERMEDIATE, "0287_desenvolvimento_arnold.gif"),
    ("Elevação lateral com halteres", M.SHOULDERS, [], E.DUMBBELL, D.BEGINNER, "0334_elevacao_lateral_com_halteres.gif"),
    ("Elevação lateral na polia", M.SHOULDERS, [], E.CABLE, D.BEGINNER, "0192_elevacao_lateral_na_polia.gif"),
    ("Elevação lateral na máquina", M.SHOULDERS, [], E.MACHINE, D.BEGINNER, "0584_elevacao_lateral_na_maquina.gif"),
    ("Elevação frontal com halteres", M.SHOULDERS, [], E.DUMBBELL, D.BEGINNER, "0310_elevacao_frontal_com_halteres.gif"),
    ("Elevação frontal na polia", M.SHOULDERS, [], E.CABLE, D.BEGINNER, "0162_elevacao_frontal_na_polia.gif"),
    ("Crucifixo inverso com halteres", M.SHOULDERS, [], E.DUMBBELL, D.BEGINNER, "0383_crucifixo_inverso_com_halteres.gif"),
    ("Crucifixo inverso na máquina", M.SHOULDERS, [], E.MACHINE, D.BEGINNER, "0602_crucifixo_inverso_na_maquina.gif"),
    ("Face pull", M.SHOULDERS, [M.TRAPS], E.CABLE, D.BEGINNER, "0203_face_pull.gif"),
    ("Remada alta com barra", M.SHOULDERS, [M.TRAPS], E.BARBELL, D.INTERMEDIATE, "0120_remada_alta_com_barra.gif"),
    # --- Bíceps ------------------------------------------------------------
    ("Rosca direta com barra reta", M.BICEPS, [M.FOREARMS], E.BARBELL, D.BEGINNER, "0031_rosca_direta_com_barra_reta.gif"),
    ("Rosca direta com barra W", M.BICEPS, [M.FOREARMS], E.BARBELL, D.BEGINNER, "0447_rosca_direta_com_barra_w.gif"),
    ("Rosca alternada com halteres", M.BICEPS, [M.FOREARMS], E.DUMBBELL, D.BEGINNER, "0285_rosca_alternada_com_halteres.gif"),
    ("Rosca simultânea com halteres", M.BICEPS, [M.FOREARMS], E.DUMBBELL, D.BEGINNER, "0294_rosca_simultanea_com_halteres.gif"),
    ("Rosca martelo", M.BICEPS, [M.FOREARMS], E.DUMBBELL, D.BEGINNER, "0313_rosca_martelo.gif"),
    ("Rosca Scott com barra", M.BICEPS, [], E.BARBELL, D.BEGINNER, "0070_rosca_scott_com_barra.gif"),
    ("Rosca Scott na máquina", M.BICEPS, [], E.MACHINE, D.BEGINNER, "0592_rosca_scott_na_maquina.gif"),
    ("Rosca inclinada com halteres", M.BICEPS, [], E.DUMBBELL, D.BEGINNER, "0318_rosca_inclinada_com_halteres.gif"),
    ("Rosca na polia", M.BICEPS, [], E.CABLE, D.BEGINNER, "0868_rosca_na_polia.gif"),
    ("Rosca concentrada", M.BICEPS, [], E.DUMBBELL, D.BEGINNER, "0297_rosca_concentrada.gif"),
    # --- Tríceps -----------------------------------------------------------
    ("Tríceps na polia com barra", M.TRICEPS, [], E.CABLE, D.BEGINNER, "0201_triceps_na_polia_com_barra.gif"),
    ("Tríceps corda", M.TRICEPS, [], E.CABLE, D.BEGINNER, "0200_triceps_corda.gif"),
    ("Tríceps francês com halter", M.TRICEPS, [], E.DUMBBELL, D.BEGINNER, "2188_triceps_frances_com_halter.gif"),
    ("Tríceps francês na polia", M.TRICEPS, [], E.CABLE, D.BEGINNER, "0194_triceps_frances_na_polia.gif"),
    ("Tríceps testa com barra", M.TRICEPS, [], E.BARBELL, D.INTERMEDIATE, "0061_triceps_testa_com_barra.gif"),
    ("Tríceps testa com halteres", M.TRICEPS, [], E.DUMBBELL, D.BEGINNER, "0351_triceps_testa_com_halteres.gif"),
    ("Tríceps máquina", M.TRICEPS, [], E.MACHINE, D.BEGINNER, "0607_triceps_maquina.gif"),
    ("Paralelas", M.TRICEPS, [M.CHEST, M.SHOULDERS], E.BODYWEIGHT, D.INTERMEDIATE, "0251_paralelas.gif"),
    ("Supino fechado", M.TRICEPS, [M.CHEST], E.BARBELL, D.INTERMEDIATE, "0030_supino_fechado.gif"),
    ("Tríceps coice", M.TRICEPS, [], E.DUMBBELL, D.BEGINNER, "0333_triceps_coice.gif"),
    # --- Quadríceps --------------------------------------------------------
    ("Agachamento livre", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.BARBELL, D.INTERMEDIATE, "0043_agachamento_livre.gif"),
    ("Agachamento no Smith", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.SMITH_MACHINE, D.BEGINNER, "0770_agachamento_no_smith.gif"),
    ("Agachamento frontal", M.QUADS, [M.GLUTES], E.BARBELL, D.ADVANCED, "0042_agachamento_frontal.gif"),
    ("Leg press 45°", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.MACHINE, D.BEGINNER, "0739_leg_press_45.gif"),
    ("Leg press horizontal", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.MACHINE, D.BEGINNER, "2611_leg_press_horizontal.gif"),
    ("Hack squat", M.QUADS, [M.GLUTES], E.MACHINE, D.INTERMEDIATE, "0743_hack_squat.gif"),
    ("Agachamento pendular", M.QUADS, [M.GLUTES], E.MACHINE, D.INTERMEDIATE, "agachamento_pendular.png"),
    ("Cadeira extensora", M.QUADS, [], E.MACHINE, D.BEGINNER, "0585_cadeira_extensora.gif"),
    ("Afundo com halteres", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.DUMBBELL, D.INTERMEDIATE, "0336_afundo_com_halteres.gif"),
    ("Afundo no Smith", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.SMITH_MACHINE, D.INTERMEDIATE, "0769_afundo_no_smith.gif"),
    ("Agachamento búlgaro", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.DUMBBELL, D.INTERMEDIATE, "0099_agachamento_bulgaro.gif"),
    ("Passada com halteres", M.QUADS, [M.GLUTES, M.HAMSTRINGS], E.DUMBBELL, D.INTERMEDIATE, "1460_passada_com_halteres.gif"),
    # --- Posterior de coxa e glúteos --------------------------------------
    ("Stiff com barra", M.HAMSTRINGS, [M.GLUTES], E.BARBELL, D.INTERMEDIATE, "0116_stiff_com_barra.gif"),
    ("Stiff com halteres", M.HAMSTRINGS, [M.GLUTES], E.DUMBBELL, D.BEGINNER, "0432_stiff_com_halteres.gif"),
    ("Levantamento terra romeno", M.HAMSTRINGS, [M.GLUTES, M.BACK], E.BARBELL, D.INTERMEDIATE, "0085_levantamento_terra_romeno.gif"),
    ("Levantamento terra tradicional", M.HAMSTRINGS, [M.GLUTES, M.BACK], E.BARBELL, D.ADVANCED, "0032_levantamento_terra_tradicional.gif"),
    ("Mesa flexora", M.HAMSTRINGS, [], E.MACHINE, D.BEGINNER, "0586_mesa_flexora.gif"),
    ("Cadeira flexora", M.HAMSTRINGS, [], E.MACHINE, D.BEGINNER, "0599_cadeira_flexora.gif"),
    ("Flexora em pé", M.HAMSTRINGS, [], E.MACHINE, D.BEGINNER, "0795_flexora_em_pe.gif"),
    ("Elevação pélvica com barra", M.GLUTES, [M.HAMSTRINGS], E.BARBELL, D.BEGINNER, "1409_elevacao_pelvica_com_barra.gif"),
    ("Elevação pélvica no Smith", M.GLUTES, [M.HAMSTRINGS], E.SMITH_MACHINE, D.BEGINNER, "elevacao_pelvica_no_smith.png"),
    ("Elevação pélvica na máquina", M.GLUTES, [M.HAMSTRINGS], E.MACHINE, D.BEGINNER, "elevacao_pelvica_na_maquina.png"),
    ("Glúteo na polia", M.GLUTES, [], E.CABLE, D.BEGINNER, "0228_gluteo_na_polia.gif"),
    ("Glúteo na máquina", M.GLUTES, [], E.MACHINE, D.BEGINNER, "3193_gluteo_na_maquina.gif"),
    ("Coice na máquina", M.GLUTES, [], E.MACHINE, D.BEGINNER, "2286_coice_na_maquina.gif"),
    ("Good morning", M.HAMSTRINGS, [M.GLUTES, M.BACK], E.BARBELL, D.ADVANCED, "0044_good_morning.gif"),
    # --- Adutores e abdutores ---------------------------------------------
    ("Cadeira abdutora", M.GLUTES, [], E.MACHINE, D.BEGINNER, "0597_cadeira_abdutora.gif"),
    ("Cadeira adutora", M.QUADS, [], E.MACHINE, D.BEGINNER, "0598_cadeira_adutora.gif"),
    ("Abdução de quadril na polia", M.GLUTES, [], E.CABLE, D.BEGINNER, "0168_abducao_de_quadril_na_polia.gif"),
    ("Adução de quadril na polia", M.QUADS, [], E.CABLE, D.BEGINNER, "0168_aducao_de_quadril_na_polia.gif"),
    # --- Panturrilhas ------------------------------------------------------
    ("Panturrilha em pé", M.CALVES, [], E.MACHINE, D.BEGINNER, "0605_panturrilha_em_pe.gif"),
    ("Panturrilha sentada", M.CALVES, [], E.MACHINE, D.BEGINNER, "0594_panturrilha_sentada.gif"),
    ("Panturrilha no leg press", M.CALVES, [], E.MACHINE, D.BEGINNER, "1391_panturrilha_no_leg_press.gif"),
    ("Panturrilha no Smith", M.CALVES, [], E.SMITH_MACHINE, D.BEGINNER, "0763_panturrilha_no_smith.gif"),
    ("Panturrilha unilateral", M.CALVES, [], E.DUMBBELL, D.BEGINNER, "0400_panturrilha_unilateral.gif"),
    # --- Abdômen -----------------------------------------------------------
    # "Abdominal infra" e reverse crunch são o mesmo movimento (o pacote traz o
    # mesmo GIF com os dois nomes) — entra uma vez só.
    ("Abdominal supra", M.ABS, [], E.BODYWEIGHT, D.BEGINNER, "0175_abdominal_supra.gif"),
    ("Abdominal infra", M.ABS, [], E.BODYWEIGHT, D.BEGINNER, "0872_abdominal_infra.gif"),
    ("Elevação de pernas", M.ABS, [], E.BODYWEIGHT, D.BEGINNER, "0012_elevacao_de_pernas.gif"),
    ("Elevação de joelhos na barra", M.ABS, [], E.BODYWEIGHT, D.INTERMEDIATE, "0010_elevacao_de_joelhos_na_barra.gif"),
    ("Abdominal na polia", M.ABS, [], E.CABLE, D.BEGINNER, "0212_abdominal_na_polia.gif"),
    ("Abdominal máquina", M.ABS, [], E.MACHINE, D.BEGINNER, "1452_abdominal_maquina.gif"),
    ("Prancha abdominal", M.ABS, [], E.BODYWEIGHT, D.BEGINNER, "0464_prancha_abdominal.gif"),
    ("Prancha lateral", M.ABS, [], E.BODYWEIGHT, D.BEGINNER, "3544_prancha_lateral.gif"),
    ("Abdominal bicicleta", M.ABS, [], E.BODYWEIGHT, D.BEGINNER, "0972_abdominal_bicicleta.gif"),
    ("Abdominal oblíquo", M.ABS, [], E.BODYWEIGHT, D.BEGINNER, "0635_abdominal_obliquo.gif"),
    ("Abdominal com roda", M.ABS, [], E.OTHER, D.INTERMEDIATE, "0857_abdominal_com_roda.gif"),
    ("Abdominal remador", M.ABS, [], E.BODYWEIGHT, D.BEGINNER, "0969_abdominal_remador.gif"),
    ("Rotação russa", M.ABS, [], E.BODYWEIGHT, D.BEGINNER, "0687_russian_twist.gif"),
    ("Dead bug", M.ABS, [], E.BODYWEIGHT, D.BEGINNER, "0276_dead_bug.gif"),
]


def run() -> None:
    db = SessionLocal()
    try:
        created, updated, sem_imagem = 0, 0, []
        mantidos: set[int] = set()

        for name, primary, secondary, equipment, difficulty, image in EXERCISES:
            if not (IMAGE_DIR / image).exists():
                # Sem o arquivo no pacote o exercício não entra — a regra é
                # "só existe exercício com imagem". Não derruba o boot.
                sem_imagem.append(name)
                continue

            # .first() com ordem estável por id (não one_or_none): a base
            # importada tem nomes repetidos, e queremos sempre a MESMA linha
            # (a mais antiga, que é a referenciada pelas rotinas existentes).
            existing = (
                db.execute(
                    select(Exercise)
                    .where(Exercise.name == name, Exercise.is_custom.is_(False))
                    .order_by(Exercise.id)
                )
                .scalars()
                .first()
            )
            secondary_values = [g.value for g in secondary]
            video_url = f"{IMAGE_URL_PREFIX}/{image}"

            if existing:
                existing.primary_muscle_group = primary
                existing.secondary_muscle_groups = secondary_values
                existing.equipment = equipment
                existing.difficulty = difficulty
                existing.is_hidden = False
                # Tudo aqui é musculação. Sem forçar, um exercício importado
                # como STRETCHING/CARDIO ficaria invisível pro motor de treino.
                existing.category = ExerciseCategory.STRENGTH
                existing.video_url = video_url
                mantidos.add(existing.id)
                updated += 1
            else:
                ex = Exercise(
                    name=name,
                    is_custom=False,
                    primary_muscle_group=primary,
                    secondary_muscle_groups=secondary_values,
                    equipment=equipment,
                    difficulty=difficulty,
                    category=ExerciseCategory.STRENGTH,
                    video_url=video_url,
                    is_hidden=False,
                )
                db.add(ex)
                db.flush()  # precisa do id pra entrar em `mantidos`
                mantidos.add(ex.id)
                created += 1

        # Esconde TODO o resto. Não apaga: rotinas e sessões antigas apontam
        # pro id por FK e continuam abrindo normalmente — o exercício só some
        # da busca, do picker, da IA e dos 10 métodos.
        escondidos = 0
        for ex in db.execute(
            select(Exercise).where(Exercise.is_custom.is_(False), Exercise.is_hidden.is_(False))
        ).scalars():
            if ex.id not in mantidos:
                ex.is_hidden = True
                escondidos += 1

        db.commit()
        print(
            f"Biblioteca curada: {created} criados, {updated} atualizados, "
            f"{escondidos} escondidos (visíveis agora: {len(mantidos)})."
        )
        if sem_imagem:
            print(f"  ATENÇÃO — sem arquivo de imagem, ficaram de fora: {sem_imagem}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
