"""Whitelist curada: os ÚNICOS 50 exercícios visíveis no app.

Cada entrada aponta pro source_external_id da ExerciseDB (chave estável
entre dev e prod — o id inteiro muda, o external não). O gif de cada um foi
conferido visualmente, um por um. O seed usa isto pra deixar SÓ estes 50
visíveis (busca manual, IA e os 10 métodos filtram por is_hidden).
Gerado por scratchpad/gen_whitelist.py.
"""
from app.models.exercise import MuscleGroup

# source_external_id -> (nome PT exibido, grupo muscular primário)
CURATED_50: dict[str, tuple[str, MuscleGroup]] = {
    "0025": ("Supino reto com barra", MuscleGroup.CHEST),  # barbell bench press
    "0289": ("Supino reto com halteres", MuscleGroup.CHEST),  # dumbbell bench press
    "0047": ("Supino inclinado com barra", MuscleGroup.CHEST),  # barbell incline bench press
    "0314": ("Supino inclinado com halteres", MuscleGroup.CHEST),  # dumbbell incline bench press
    "0662": ("Flexão de braços", MuscleGroup.CHEST),  # push-up
    "0279": ("Flexão declinada", MuscleGroup.CHEST),  # decline push-up
    "1269": ("Crossover no cabo", MuscleGroup.CHEST),  # cable standing up straight crossovers
    "0652": ("Barra fixa pronada", MuscleGroup.BACK),  # pull-up
    "1326": ("Barra fixa supinada", MuscleGroup.BACK),  # chin-up
    "0198": ("Puxada alta", MuscleGroup.BACK),  # cable pulldown
    "0027": ("Remada curvada com barra", MuscleGroup.BACK),  # barbell bent over row
    "0292": ("Remada unilateral com halter", MuscleGroup.BACK),  # dumbbell one arm bent-over row
    "0861": ("Remada baixa no cabo", MuscleGroup.BACK),  # cable seated row
    "0606": ("Remada cavalinho", MuscleGroup.BACK),  # lever t bar row
    "1350": ("Remada articulada", MuscleGroup.BACK),  # lever seated row
    "0499": ("Remada invertida com o corpo", MuscleGroup.BACK),  # inverted row
    "1456": ("Desenvolvimento militar", MuscleGroup.SHOULDERS),  # barbell standing close grip military press
    "0405": ("Desenvolvimento com halteres", MuscleGroup.SHOULDERS),  # dumbbell seated shoulder press
    "0334": ("Elevação lateral", MuscleGroup.SHOULDERS),  # dumbbell lateral raise
    "0178": ("Elevação lateral no cabo", MuscleGroup.SHOULDERS),  # cable lateral raise
    "0383": ("Crucifixo inverso", MuscleGroup.SHOULDERS),  # dumbbell reverse fly
    "3662": ("Flexão pike", MuscleGroup.SHOULDERS),  # pike-to-cobra push-up
    "0031": ("Rosca direta", MuscleGroup.BICEPS),  # barbell curl
    "0285": ("Rosca alternada", MuscleGroup.BICEPS),  # dumbbell alternate biceps curl
    "0313": ("Rosca martelo", MuscleGroup.BICEPS),  # dumbbell hammer curl
    "0070": ("Rosca Scott", MuscleGroup.BICEPS),  # barbell preacher curl
    "0201": ("Tríceps na polia", MuscleGroup.TRICEPS),  # cable pushdown
    "0061": ("Tríceps testa", MuscleGroup.TRICEPS),  # barbell lying triceps extension
    "2188": ("Tríceps francês", MuscleGroup.TRICEPS),  # dumbbell seated triceps extension
    "0814": ("Mergulho em banco ou paralelas", MuscleGroup.TRICEPS),  # triceps dip
    "0043": ("Agachamento livre com barra", MuscleGroup.QUADS),  # barbell full squat
    "3533": ("Agachamento sem peso", MuscleGroup.QUADS),  # quads (bodyweight squat)
    "0514": ("Agachamento com salto", MuscleGroup.QUADS),  # jump squat
    "0042": ("Agachamento frontal", MuscleGroup.QUADS),  # barbell front squat
    "0739": ("Leg press", MuscleGroup.QUADS),  # sled 45° leg press
    "0743": ("Hack squat", MuscleGroup.QUADS),  # sled hack squat
    "0809": ("Agachamento búlgaro", MuscleGroup.QUADS),  # suspended split squat
    "1460": ("Afundo ou passada", MuscleGroup.QUADS),  # walking lunge
    "0585": ("Cadeira extensora", MuscleGroup.QUADS),  # lever leg extension
    "0085": ("Levantamento terra romeno", MuscleGroup.HAMSTRINGS),  # barbell romanian deadlift
    "0586": ("Mesa flexora", MuscleGroup.HAMSTRINGS),  # lever lying leg curl
    "1409": ("Elevação pélvica", MuscleGroup.GLUTES),  # barbell glute bridge
    "3013": ("Ponte de glúteos sem peso", MuscleGroup.GLUTES),  # low glute bridge on floor
    "0605": ("Panturrilha em pé", MuscleGroup.CALVES),  # lever standing calf raise
    "0594": ("Panturrilha sentada", MuscleGroup.CALVES),  # lever seated calf raise
    "3665": ("Prancha", MuscleGroup.ABS),  # power point plank
    "3544": ("Prancha lateral", MuscleGroup.ABS),  # bodyweight incline side plank
    "0620": ("Elevação de pernas", MuscleGroup.ABS),  # lying leg raise flat bench
    "0274": ("Abdominal tradicional", MuscleGroup.ABS),  # crunch floor
    "0857": ("Roda abdominal", MuscleGroup.ABS),  # wheel rollout
}
