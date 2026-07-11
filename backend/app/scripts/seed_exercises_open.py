"""Importa a base aberta free-exercise-db (873 exercícios, todos com imagem
de demonstração) de app/data/exercises_open.json.

Fonte: https://github.com/yuhonas/free-exercise-db (dados abertos).
Cada exercício vira um Food... digo, Exercise, com:
- nome traduzido para PT-BR por um dicionário de termos de academia
- grupo muscular e equipamento mapeados para os enums do app
- instruções traduzidas de forma básica no execution_text
- video_url apontando para a imagem de demonstração hospedada no GitHub

Idempotente por external_id (guardado como prefixo no nome? não — usamos o
próprio nome traduzido + is_custom=False como no seed curado, mas para evitar
duplicar entre execuções marcamos via origin no execution_text). Para manter
simples e idempotente, deletamos e reinserimos os exercícios dessa origem a
cada execução, identificados pelo prefixo do video_url.

Uso: python -m app.scripts.seed_exercises_open
"""
import json
import re
from pathlib import Path

from sqlalchemy import select

from app.core.db import SessionLocal
from app.data.exercise_translator import translate_exercise_name
from app.models.exercise import Difficulty, Equipment, Exercise, MuscleGroup

JSON_PATH = Path(__file__).parent.parent / "data" / "exercises_open.json"
IMAGE_BASE = "https://raw.githubusercontent.com/yuhonas/free-exercise-db/main/exercises/"

MUSCLE_MAP = {
    "abdominals": MuscleGroup.ABS,
    "abductors": MuscleGroup.GLUTES,
    "adductors": MuscleGroup.QUADS,
    "biceps": MuscleGroup.BICEPS,
    "calves": MuscleGroup.CALVES,
    "chest": MuscleGroup.CHEST,
    "forearms": MuscleGroup.FOREARMS,
    "glutes": MuscleGroup.GLUTES,
    "hamstrings": MuscleGroup.HAMSTRINGS,
    "lats": MuscleGroup.BACK,
    "lower back": MuscleGroup.BACK,
    "middle back": MuscleGroup.BACK,
    "neck": MuscleGroup.TRAPS,
    "quadriceps": MuscleGroup.QUADS,
    "shoulders": MuscleGroup.SHOULDERS,
    "traps": MuscleGroup.TRAPS,
    "triceps": MuscleGroup.TRICEPS,
}

EQUIPMENT_MAP = {
    "barbell": Equipment.BARBELL,
    "dumbbell": Equipment.DUMBBELL,
    "cable": Equipment.CABLE,
    "machine": Equipment.MACHINE,
    "body only": Equipment.BODYWEIGHT,
    "kettlebells": Equipment.KETTLEBELL,
    "bands": Equipment.BAND,
    "e-z curl bar": Equipment.BARBELL,
    "exercise ball": Equipment.OTHER,
    "medicine ball": Equipment.OTHER,
    "foam roll": Equipment.OTHER,
    "other": Equipment.OTHER,
    "none": Equipment.OTHER,
}

DIFFICULTY_MAP = {
    "beginner": Difficulty.BEGINNER,
    "intermediate": Difficulty.INTERMEDIATE,
    "expert": Difficulty.ADVANCED,
}

# Tradução por termos (frases maiores primeiro para não quebrar). Aplicada
# sobre o nome em minúsculas; o resultado recebe capitalização de frase.
NAME_TERMS = [
    ("bench press", "supino"),
    ("incline bench press", "supino inclinado"),
    ("decline bench press", "supino declinado"),
    ("shoulder press", "desenvolvimento de ombro"),
    ("military press", "desenvolvimento militar"),
    ("overhead press", "desenvolvimento acima da cabeça"),
    ("leg press", "leg press"),
    ("leg extension", "cadeira extensora"),
    ("leg curl", "mesa flexora"),
    ("leg raise", "elevação de pernas"),
    ("calf raise", "elevação de panturrilha"),
    ("lateral raise", "elevação lateral"),
    ("front raise", "elevação frontal"),
    ("bicep curl", "rosca de bíceps"),
    ("biceps curl", "rosca de bíceps"),
    ("hammer curl", "rosca martelo"),
    ("preacher curl", "rosca scott"),
    ("wrist curl", "rosca de punho"),
    ("concentration curl", "rosca concentrada"),
    ("tricep extension", "extensão de tríceps"),
    ("triceps extension", "extensão de tríceps"),
    ("triceps pushdown", "tríceps na polia"),
    ("pushdown", "puxada para baixo"),
    ("pull-up", "barra fixa"),
    ("pull up", "barra fixa"),
    ("chin-up", "barra fixa supinada"),
    ("pull down", "puxada"),
    ("pulldown", "puxada"),
    ("lat pulldown", "puxada frontal"),
    ("deadlift", "levantamento terra"),
    ("romanian deadlift", "levantamento terra romeno"),
    ("stiff leg deadlift", "stiff"),
    ("good morning", "good morning"),
    ("hip thrust", "elevação pélvica"),
    ("glute bridge", "ponte de glúteo"),
    ("push-up", "flexão de braço"),
    ("push up", "flexão de braço"),
    ("pushup", "flexão de braço"),
    ("sit-up", "abdominal"),
    ("sit up", "abdominal"),
    ("situp", "abdominal"),
    ("crunch", "abdominal"),
    ("plank", "prancha"),
    ("lunge", "afundo"),
    ("step-up", "subida no banco"),
    ("step up", "subida no banco"),
    ("front squat", "agachamento frontal"),
    ("back squat", "agachamento"),
    ("squat", "agachamento"),
    ("row", "remada"),
    ("bent over row", "remada curvada"),
    ("upright row", "remada alta"),
    ("shrug", "encolhimento"),
    ("fly", "crucifixo"),
    ("flye", "crucifixo"),
    ("pullover", "pullover"),
    ("dip", "mergulho"),
    ("clean", "clean"),
    ("snatch", "snatch"),
    ("jerk", "jerk"),
    ("thruster", "thruster"),
    ("swing", "balanço"),
    ("jump", "salto"),
    ("burpee", "burpee"),
    ("mountain climber", "escalador"),
    ("stretch", "alongamento"),
    ("smr", "liberação miofascial"),
    ("bent over", "curvado"),
    ("bent-over", "curvado"),
    ("kickback", "coice"),
    ("pull-through", "pull-through"),
    ("face pull", "face pull"),
    ("chest press", "supino na máquina"),
    ("press", "pressão"),
    ("raise", "elevação"),
    ("curl", "rosca"),
    ("extension", "extensão"),
    ("adduction", "adução"),
    ("abduction", "abdução"),
    ("twist", "rotação"),
    ("hold", "isometria"),
    ("walk", "caminhada"),
    ("run", "corrida"),
    ("sprint", "tiro"),
]

WORD_TERMS = {
    "barbell": "com barra",
    "dumbbell": "com halteres",
    "dumbbells": "com halteres",
    "cable": "no cabo",
    "machine": "na máquina",
    "smith": "no smith",
    "kettlebell": "com kettlebell",
    "kettlebells": "com kettlebell",
    "band": "com faixa",
    "bands": "com faixa",
    "bodyweight": "peso corporal",
    "seated": "sentado",
    "standing": "em pé",
    "lying": "deitado",
    "incline": "inclinado",
    "decline": "declinado",
    "reverse": "invertido",
    "close grip": "pegada fechada",
    "wide grip": "pegada aberta",
    "grip": "pegada",
    "one arm": "unilateral",
    "single arm": "unilateral",
    "single leg": "unilateral",
    "one leg": "unilateral",
    "alternate": "alternado",
    "alternating": "alternado",
    "arm": "braço",
    "leg": "perna",
    "chest": "peito",
    "shoulder": "ombro",
    "shoulders": "ombros",
    "back": "costas",
    "calf": "panturrilha",
    "glute": "glúteo",
    "hamstring": "posterior de coxa",
    "quad": "quadríceps",
    "triceps": "tríceps",
    "tricep": "tríceps",
    "biceps": "bíceps",
    "bicep": "bíceps",
    "forearm": "antebraço",
    "ab": "abdômen",
    "abs": "abdômen",
    "abdominal": "abdominal",
    "oblique": "oblíquo",
    "hip": "quadril",
    "knee": "joelho",
    "ankle": "tornozelo",
    "neck": "pescoço",
    "front": "frontal",
    "side": "lateral",
    "lateral": "lateral",
    "rear": "posterior",
    "overhead": "acima da cabeça",
    "wide": "aberto",
    "narrow": "fechado",
    "high": "alto",
    "low": "baixo",
    "weighted": "com carga",
    "assisted": "assistido",
    "bench": "no banco",
    "floor": "no solo",
    "ball": "com bola",
    "rope": "com corda",
    "plate": "com anilha",
    "bar": "na barra",
    "chin": "queixo",
    "wrist": "punho",
    "palms": "palmas",
    "palm": "palma",
    "toe": "ponta do pé",
    "heel": "calcanhar",
    "and": "e",
    "with": "com",
    "on": "no",
    "to": "para",
    "the": "",
    "of": "de",
    "for": "para",
    "up": "",
    "down": "para baixo",
    "muscle": "músculo",
    "full": "completo",
    "half": "meio",
    # termos que sobraram na 1ª rodada
    "over": "sobre",
    "bent": "curvado",
    "push": "empurrar",
    "pull": "puxar",
    "two": "dois",
    "one": "um",
    "single": "único",
    "double": "duplo",
    "box": "caixa",
    "split": "afastado",
    "hang": "suspenso",
    "hanging": "suspenso",
    "pulley": "polia",
    "from": "a partir de",
    "kneeling": "ajoelhado",
    "power": "potência",
    "circles": "círculos",
    "circle": "círculo",
    "behind": "atrás",
    "in": "em",
    "rotation": "rotação",
    "leverage": "alavanca",
    "extended": "estendido",
    "flexion": "flexão",
    "extension": "extensão",
    "external": "externa",
    "internal": "interna",
    "close": "fechada",
    "wide": "aberta",
    "medium": "média",
    "flat": "reto",
    "cross": "cruzado",
    "hands": "mãos",
    "hand": "mão",
    "head": "cabeça",
    "body": "corpo",
    "elbow": "cotovelo",
    "elbows": "cotovelos",
    "raised": "elevado",
    "star": "estrela",
    "cross-over": "cruzado",
    "twisting": "com rotação",
    "flip": "giro",
    "roll": "rolamento",
    "rolling": "rolamento",
    "hyperextension": "hiperextensão",
    "raiser": "elevador",
    "climber": "escalador",
    "climbers": "escaladores",
    "wall": "parede",
    "world": "mundo",
    "greatest": "melhor",
    "isometric": "isométrico",
    "static": "estático",
    "dynamic": "dinâmico",
    "explosive": "explosivo",
    "partial": "parcial",
    "advanced": "avançado",
    "beginner": "iniciante",
    "resistance": "resistência",
    "resisted": "resistido",
    "band": "faixa",
    "banded": "com faixa",
    "chair": "cadeira",
    "step": "degrau",
    "stability": "estabilidade",
    "balance": "equilíbrio",
    "linear": "linear",
    "depth": "profundidade",
    "harness": "cinta",
    "belt": "cinto",
    "weighted": "com carga",
    "loaded": "com carga",
    "off": "",
    "kick": "chute",
    "get": "levantar",
    "sit": "sentar",
    "stand": "levantar",
    "toes": "pontas dos pés",
    "chin": "queixo",
    "cross-body": "cruzado",
    "prone": "de bruços",
    "supine": "de costas",
    "iso": "isométrico",
    "inverted": "invertido",
    "upright": "vertical",
    "throw": "arremesso",
    "russian": "russo",
    "scissors": "tesoura",
    "scissor": "tesoura",
    "stomach": "abdominal",
    "vacuum": "vácuo",
    "figure": "figura",
    "windmill": "moinho",
    "superman": "superman",
    "bicycle": "bicicleta",
    "cobra": "cobra",
    "frog": "sapo",
    "spider": "aranha",
    "diagonal": "diagonal",
    "around": "ao redor",
    "world's": "melhor",
    "greatest": "melhor",
    "seal": "foca",
    "bear": "urso",
    "crab": "caranguejo",
    "donkey": "burro",
    "wide-grip": "pegada aberta",
    "close-grip": "pegada fechada",
    "neutral": "neutra",
    "underhand": "supinada",
    "overhand": "pronada",
    "kneeling": "ajoelhado",
    "flutter": "flutuante",
    "pistol": "pistol",
    "sumo": "sumô",
    # 2ª caça de restos
    "delt": "deltoide",
    "delts": "deltoides",
    "deltoid": "deltoide",
    "sled": "trenó",
    "stance": "postura",
    "straight": "reto",
    "chains": "correntes",
    "crossover": "cruzamento",
    "ez": "W",
    "e-z": "W",
    "exercise": "exercício",
    "groin": "virilha",
    "groiners": "virilha",
    "medicine": "medicinal",
    "long": "longo",
    "lift": "levantamento",
    "hammer": "martelo",
    "lat": "dorsal",
    "lats": "dorsais",
    "hops": "saltitos",
    "hop": "saltito",
    "legged": "de perna",
    "suspended": "suspenso",
    "bridge": "ponte",
    "drag": "arrasto",
    "knees": "joelhos",
    "against": "contra",
    "walking": "caminhando",
    "butt": "glúteo",
    "blocks": "blocos",
    "block": "bloco",
    "elevated": "elevado",
    "through": "através",
    "adductor": "adutor",
    "adductors": "adutores",
    "backward": "para trás",
    "forward": "para frente",
    "rollout": "rolamento à frente",
    "hack": "hack",
    "bend": "flexão",
    "bends": "flexões",
    "attachment": "pegador",
    "iron": "ferro",
    "lower": "inferior",
    "upper": "superior",
    "legs": "pernas",
    "flexor": "flexor",
    "ham": "posterior de coxa",
    "hamstrings": "posteriores de coxa",
    "cone": "cone",
    "cones": "cones",
    "inner": "interno",
    "outer": "externo",
    "treadmill": "esteira",
    "pass": "passe",
    "row": "remada",
    "rows": "remadas",
    "curl": "rosca",
    "raise": "elevação",
    "guillotine": "guilhotina",
    "judo": "judô",
    "hands": "mãos",
    "toe": "ponta do pé",
    "extended": "estendido",
    "seated": "sentado",
    "standing": "em pé",
    "lunge": "afundo",
    "lunges": "afundos",
    "run": "corrida",
    "sprint": "tiro",
    "shuffle": "deslocamento lateral",
    "carioca": "carioca",
    "skater": "patinador",
    "tuck": "encolhido",
    "pike": "canivete",
    "hollow": "isometria abdominal",
    "superman": "superman",
    "windmill": "moinho",
    "goblet": "goblet",
    "zercher": "zercher",
    "landmine": "landmine",
    "hyperextensions": "hiperextensões",
    "raises": "elevações",
    # 3ª caça (cauda longa mais frequente)
    "preacher": "scott",
    "pushups": "flexões",
    "pushup": "flexão",
    "situps": "abdominais",
    "chinups": "barras supinadas",
    "pullups": "barras fixas",
    "rack": "rack",
    "speed": "velocidade",
    "bike": "bicicleta",
    "bicycling": "pedalada",
    "stationary": "estática",
    "drill": "exercício",
    "roller": "rolo",
    "bound": "salto",
    "bounds": "saltos",
    "board": "prancha",
    "trainer": "aparelho",
    "skull": "testa",
    "crusher": "esmagador",
    "crawl": "rastejamento",
    "touchers": "toques",
    "touch": "toque",
    "response": "reação",
    "reactive": "reativo",
    "drills": "exercícios",
    "tibialis": "tibial",
    "atlas": "atlas",
    "stone": "pedra",
    "stones": "pedras",
    "sledgehammer": "marreta",
    "tire": "pneu",
    "rope": "corda",
    "ropes": "cordas",
    "battle": "battle",
    "farmer": "fazendeiro",
    "carry": "transporte",
    "carries": "transportes",
    "waiter": "garçom",
    "suitcase": "mala",
    "rack-pull": "rack pull",
    "clean-and-press": "clean and press",
    "jerk": "jerk",
    "muscle-up": "muscle-up",
    "l-sit": "l-sit",
    "l": "L",
    "v-up": "canivete",
    "v-ups": "canivetes",
    "t-bar": "barra T",
    "t": "T",
    "y": "Y",
    "w": "W",
    "high-knee": "joelho alto",
    "high-knees": "joelhos altos",
    "butt-kicks": "chute no glúteo",
    "jumping": "saltando",
    "jack": "polichinelo",
    "jacks": "polichinelos",
    "duck": "pato",
    "gorilla": "gorila",
    "monkey": "macaco",
    "turkish": "turco",
    "cossack": "cossaco",
    "curtsy": "reverência",
    "shrimp": "camarão",
    "nordic": "nórdico",
    "sissy": "sissy",
    "jefferson": "jefferson",
}

# Plurais em inglês que devem cair no singular já traduzido.
PLURALS = {
    "curls": "roscas",
    "squats": "agachamentos",
    "ups": "",
    "raises": "elevações",
    "flyes": "crucifixos",
    "flys": "crucifixos",
    "rows": "remadas",
    "presses": "pressões",
    "extensions": "extensões",
    "lunges": "afundos",
    "dips": "mergulhos",
    "crunches": "abdominais",
    "planks": "pranchas",
    "swings": "balanços",
    "jumps": "saltos",
    "twists": "rotações",
    "raisers": "elevadores",
    "deadlifts": "levantamentos terra",
}


def translate_name(name: str) -> str:
    text = " " + name.lower().replace("-", " ").replace("/", " ") + " "
    for en, pt in NAME_TERMS:
        text = re.sub(rf"(?<=\s){re.escape(en)}(?=\s)", pt, text)
    tokens = [t for t in text.split() if t]
    out = []
    i = 0
    while i < len(tokens):
        two = " ".join(tokens[i : i + 2])
        if two in WORD_TERMS:
            rep = WORD_TERMS[two]
            if rep:
                out.append(rep)
            i += 2
            continue
        w = tokens[i]
        if w in PLURALS:
            rep = PLURALS[w]
            if rep:
                out.append(rep)
        else:
            out.append(WORD_TERMS.get(w, w))
        i += 1
    result = " ".join(x for x in out if x).strip()
    result = re.sub(r"\s+", " ", result)
    return result[:1].upper() + result[1:] if result else name


def run() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    db = SessionLocal()
    try:
        # Idempotência: remove os importados dessa origem (video_url no GitHub)
        # antes de reinserir. Não toca nos curados (video_url nulo).
        db.query(Exercise).filter(Exercise.video_url.like(f"{IMAGE_BASE}%")).delete(
            synchronize_session=False
        )
        db.flush()

        existing_names = {
            n.lower()
            for (n,) in db.execute(select(Exercise.name).where(Exercise.is_custom.is_(False)))
        }

        created = 0
        for row in data:
            primary = row.get("primaryMuscles") or []
            equip = str(row.get("equipment") or "none").lower()
            if not primary or primary[0] not in MUSCLE_MAP:
                continue
            images = row.get("images") or []
            video_url = IMAGE_BASE + images[0] if images else None
            if not video_url:
                continue

            # Tradutor composicional novo (reordena pra gramática PT). Se ele
            # não reconhecer o movimento, cai no palavra-a-palavra antigo.
            name_pt = translate_exercise_name(row["name"])
            # evita colidir com os curados (que têm nomes melhores)
            if name_pt.lower() in existing_names:
                name_pt = f"{name_pt} (variação)"
            if name_pt.lower() in existing_names:
                continue
            existing_names.add(name_pt.lower())

            secondary = [
                MUSCLE_MAP[m].value for m in (row.get("secondaryMuscles") or []) if m in MUSCLE_MAP
            ]
            instructions = " ".join(row.get("instructions") or [])[:900]

            db.add(
                Exercise(
                    name=name_pt,
                    primary_muscle_group=MUSCLE_MAP[primary[0]],
                    secondary_muscle_groups=secondary,
                    equipment=EQUIPMENT_MAP.get(equip, Equipment.OTHER),
                    difficulty=DIFFICULTY_MAP.get(str(row.get("level")), Difficulty.INTERMEDIATE),
                    execution_text=instructions or None,
                    video_url=video_url,
                    is_custom=False,
                )
            )
            created += 1

        db.commit()
        print(f"Exercícios (base aberta com imagem): {created} importados.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
