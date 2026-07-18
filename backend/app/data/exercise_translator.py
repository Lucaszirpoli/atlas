"""Tradutor COMPOSICIONAL de nomes de exercício (inglês -> português).

O problema da seed antiga: traduzia palavra-por-palavra mantendo a ORDEM do
inglês ("Alternating Hammer Curl" -> "Alternado rosca martelo"). Aqui a gente
entende a estrutura do nome e recompõe na gramática do português:

    [modificadores] [equipamento] MOVIMENTO
        ->  MOVIMENTO [modificadores concordados] [frase de equipamento]

    "Incline Barbell Bench Press" -> "Supino inclinado com barra"
    "Alternating Hammer Curl"     -> "Rosca martelo alternada"
    "Seated Cable Row"            -> "Remada sentada no cabo"

Cada movimento carrega seu gênero (m/f) pra concordar os adjetivos
("Supino inclinado" vs "Remada inclinada"). Equipamento vira frase preposicional
invariável ("com barra", "no cabo"). Quando não reconhece o movimento, cai num
fallback palavra-a-palavra (ainda melhor que nada).
"""
from __future__ import annotations

import re

# --- MOVIMENTOS: frase em inglês -> (nome PT, gênero) ---------------------
# Ordenado por especificidade na hora de casar (frases mais longas primeiro).
_MOVEMENTS: dict[str, tuple[str, str]] = {
    "press": ("Supino", "m"),  # "press" sozinho (Dumbbell Press etc.) = supino
    "bench press": ("Supino", "m"),
    "incline bench press": ("Supino inclinado", "m"),
    "decline bench press": ("Supino declinado", "m"),
    "chest press": ("Supino na máquina", "m"),
    "floor press": ("Supino no chão", "m"),
    "close grip bench press": ("Supino pegada fechada", "m"),
    "hammer curl": ("Rosca martelo", "f"),
    "bicep curl": ("Rosca direta", "f"),
    "biceps curl": ("Rosca direta", "f"),
    "preacher curl": ("Rosca scott", "f"),
    "concentration curl": ("Rosca concentrada", "f"),
    "spider curl": ("Rosca spider", "f"),
    "wrist curl": ("Rosca de punho", "f"),
    "reverse curl": ("Rosca inversa", "f"),
    "drag curl": ("Rosca drag", "f"),
    "zottman curl": ("Rosca zottman", "f"),
    "leg curl": ("Mesa flexora", "f"),
    "lying leg curl": ("Mesa flexora deitada", "f"),
    "seated leg curl": ("Cadeira flexora", "f"),
    "curl": ("Rosca", "f"),
    "leg press": ("Leg press", "m"),
    "leg extension": ("Cadeira extensora", "f"),
    "leg raise": ("Elevação de pernas", "f"),
    "calf raise": ("Elevação de panturrilha", "f"),
    "lateral raise": ("Elevação lateral", "f"),
    "front raise": ("Elevação frontal", "f"),
    "rear delt raise": ("Elevação posterior", "f"),
    "rear lateral raise": ("Elevação posterior", "f"),
    "raise": ("Elevação", "f"),
    "shoulder press": ("Desenvolvimento de ombro", "m"),
    "military press": ("Desenvolvimento militar", "m"),
    "overhead press": ("Desenvolvimento", "m"),
    "arnold press": ("Desenvolvimento Arnold", "m"),
    "push press": ("Push press", "m"),
    "leg press": ("Leg press", "m"),
    "tricep extension": ("Extensão de tríceps", "f"),
    "triceps extension": ("Extensão de tríceps", "f"),
    "overhead tricep extension": ("Tríceps testa em pé", "m"),
    "tricep pushdown": ("Tríceps na polia", "m"),
    "triceps pushdown": ("Tríceps na polia", "m"),
    "pushdown": ("Tríceps na polia", "m"),
    "skullcrusher": ("Tríceps testa", "m"),
    "kickback": ("Tríceps coice", "m"),
    "lat pulldown": ("Puxada", "f"),
    "pulldown": ("Puxada", "f"),
    "pullover": ("Pullover", "m"),
    "upright row": ("Remada alta", "f"),
    "bent over row": ("Remada curvada", "f"),
    "t bar row": ("Remada cavalinho", "f"),
    "seated row": ("Remada sentada", "f"),
    "row": ("Remada", "f"),
    "deadlift": ("Levantamento terra", "m"),
    "romanian deadlift": ("Levantamento terra romeno", "m"),
    # "Stiff" é O nome brasileiro — enterrar como "Levantamento terra pernas
    # retas" fazia ninguém achar procurando "stiff".
    "stiff leg deadlift": ("Stiff", "m"),
    "straight leg deadlift": ("Stiff", "m"),
    "sumo deadlift": ("Levantamento terra sumô", "m"),
    "squat": ("Agachamento", "m"),
    "front squat": ("Agachamento frontal", "m"),
    "hack squat": ("Agachamento hack", "m"),
    "goblet squat": ("Agachamento goblet", "m"),
    "sumo squat": ("Agachamento sumô", "m"),
    "split squat": ("Agachamento búlgaro", "m"),
    "bulgarian split squat": ("Agachamento búlgaro", "m"),
    # Adutora/abdutora — o nome que o brasileiro USA e PROCURA (a "cadeira
    # abdutora"). O "abduction"/"adduction" cru era um dos nomes esquisitos, e
    # "Abdução de quadril" ninguém achava procurando "abdutora".
    "hip abduction": ("Abdutora", "f"),
    "hip adduction": ("Adutora", "f"),
    "hip abductor": ("Abdutora", "f"),
    "hip adductor": ("Adutora", "f"),
    "abduction": ("Abdutora", "f"),
    "adduction": ("Adutora", "f"),
    "lunge": ("Afundo", "m"),
    "walking lunge": ("Afundo caminhando", "m"),
    "step up": ("Subida no banco", "f"),
    "hip thrust": ("Elevação pélvica", "f"),
    "glute bridge": ("Ponte de glúteo", "f"),
    "fly": ("Crucifixo", "m"),
    "flye": ("Crucifixo", "m"),
    "chest fly": ("Crucifixo", "m"),
    "reverse fly": ("Crucifixo invertido", "m"),
    "cable crossover": ("Crossover", "m"),
    "crossover": ("Crossover", "m"),
    "shrug": ("Encolhimento", "m"),
    "face pull": ("Face pull", "m"),
    "dip": ("Mergulho", "m"),
    "chest dip": ("Mergulho no paralelas", "m"),
    "tricep dip": ("Mergulho para tríceps", "m"),
    "crunch": ("Abdominal", "m"),
    "reverse crunch": ("Abdominal invertido", "m"),
    "bicycle crunch": ("Abdominal bicicleta", "m"),
    "cable crunch": ("Abdominal na polia", "m"),
    "sit up": ("Abdominal", "m"),
    "situp": ("Abdominal", "m"),
    "plank": ("Prancha", "f"),
    "side plank": ("Prancha lateral", "f"),
    "russian twist": ("Rotação russa", "f"),
    "leg raise": ("Elevação de pernas", "f"),
    "hanging leg raise": ("Elevação de pernas na barra", "f"),
    "mountain climber": ("Escalador", "m"),
    "pull up": ("Barra fixa", "f"),
    "pullup": ("Barra fixa", "f"),
    "chin up": ("Barra fixa supinada", "f"),
    "chinup": ("Barra fixa supinada", "f"),
    "push up": ("Flexão de braço", "f"),
    "pushup": ("Flexão de braço", "f"),
    "good morning": ("Bom dia", "m"),
    "thruster": ("Thruster", "m"),
    "clean": ("Clean", "m"),
    "clean and jerk": ("Clean and jerk", "m"),
    "snatch": ("Arranco", "m"),
    "power clean": ("Clean de força", "m"),
    "swing": ("Balanço", "m"),
    "kettlebell swing": ("Balanço com kettlebell", "m"),
    "high pull": ("Puxada alta", "f"),
    "hyperextension": ("Hiperextensão", "f"),
    "back extension": ("Extensão lombar", "f"),
    "adductor": ("Cadeira adutora", "f"),
    "abductor": ("Cadeira abdutora", "f"),
    "wood chop": ("Lenhador", "m"),
    "woodchop": ("Lenhador", "m"),
    "burpee": ("Burpee", "m"),
    "farmers walk": ("Caminhada do fazendeiro", "f"),
    "external rotation": ("Rotação externa", "f"),
    "internal rotation": ("Rotação interna", "f"),
    "rotation": ("Rotação", "f"),
    "twist": ("Rotação de tronco", "f"),
    "pistol squat": ("Agachamento pistol", "m"),
    "step up": ("Subida no banco", "f"),
    "sit up": ("Abdominal", "m"),
    "jerk": ("Jerk", "m"),
}

# --- EQUIPAMENTO: inglês -> frase preposicional (invariável) --------------
_EQUIPMENT: dict[str, str] = {
    "barbell": "com barra",
    "dumbbell": "com halteres",
    "dumbbells": "com halteres",
    "cable": "no cabo",
    "cables": "no cabo",
    "machine": "na máquina",
    "lever": "na máquina",
    "smith": "no smith",
    "smith machine": "no smith",
    "kettlebell": "com kettlebell",
    "kettlebells": "com kettlebell",
    "ez bar": "com barra W",
    "ez-bar": "com barra W",
    "band": "com elástico",
    "bands": "com elástico",
    "resistance band": "com elástico",
    "medicine ball": "com bola medicinal",
    "stability ball": "na bola",
    "exercise ball": "na bola",
    "plate": "com anilha",
    "weighted": "com peso",
    "rope": "com corda",
}

# --- MODIFICADORES: inglês -> {m, f} (ou frase invariável) ----------------
_MODIFIERS: dict[str, dict[str, str] | str] = {
    "incline": {"m": "inclinado", "f": "inclinada"},
    "decline": {"m": "declinado", "f": "declinada"},
    "seated": {"m": "sentado", "f": "sentada"},
    "lying": {"m": "deitado", "f": "deitada"},
    "kneeling": {"m": "ajoelhado", "f": "ajoelhada"},
    "bent over": {"m": "curvado", "f": "curvada"},
    "bent-over": {"m": "curvado", "f": "curvada"},
    "alternating": {"m": "alternado", "f": "alternada"},
    "alternate": {"m": "alternado", "f": "alternada"},
    "reverse": {"m": "invertido", "f": "invertida"},
    "inclined": {"m": "inclinado", "f": "inclinada"},
    "standing": "em pé",
    "single arm": "unilateral",
    "single-arm": "unilateral",
    "one arm": "unilateral",
    "one-arm": "unilateral",
    "close grip": "pegada fechada",
    "close-grip": "pegada fechada",
    "wide grip": "pegada aberta",
    "wide-grip": "pegada aberta",
    "neutral grip": "pegada neutra",
    "overhead": "acima da cabeça",
    "front": "frontal",
    "rear": "posterior",
    "side": "lateral",
    "cross body": "cruzado",
    "45 degree": "a 45 graus",
    "45-degree": "a 45 graus",
}

# Termos que sobram (músculos, alvos) — traduzidos mesmo fora de movimento.
_LEFTOVER_TERMS: dict[str, str] = {
    "hamstring": "posterior de coxa",
    "hamstrings": "posterior de coxa",
    "quad": "quadríceps",
    "quads": "quadríceps",
    "quadriceps": "quadríceps",
    "glute": "glúteo",
    "glutes": "glúteos",
    "tricep": "tríceps",
    "triceps": "tríceps",
    "bicep": "bíceps",
    "biceps": "bíceps",
    "lat": "dorsal",
    "lats": "dorsais",
    "chest": "peito",
    "shoulder": "ombro",
    "shoulders": "ombros",
    "abs": "abdômen",
    "abdominal": "abdominal",
    "calf": "panturrilha",
    "calves": "panturrilha",
    "forearm": "antebraço",
    "forearms": "antebraços",
    "trap": "trapézio",
    "traps": "trapézio",
    "oblique": "oblíquo",
    "obliques": "oblíquos",
    "stretch": "alongamento",
    "grip": "pegada",
    "jump": "salto",
    "jumps": "saltos",
    "hold": "isometria",
    "sprint": "tiro",
    "walk": "caminhada",
    "climb": "escalada",
    "extension": "extensão",
    "extensions": "extensão",
    "curl": "rosca",
    "press": "supino",
    "raise": "elevação",
    "throw": "arremesso",
    "neck": "pescoço",
    "back": "costas",
    "middle": "do meio",
    "upper": "superior",
    "lower": "inferior",
    "bodyweight": "livre",
    "prone": "pronado",
    "supine": "supinado",
    "elevated": "elevado",
    "feet": "pés",
    "knee": "joelho",
    "knees": "joelhos",
    "hip": "quadril",
    "hips": "quadril",
    "ankle": "tornozelo",
    "chop": "corte",
    "pull": "puxada",
    "push": "empurrar",
    "bench": "no banco",
    "arm": "braço",
    "arms": "braços",
    "leg": "perna",
    "legs": "pernas",
    "circle": "círculo",
    "circles": "círculos",
    "bound": "salto",
    "long": "",
    "head": "",
    "two": "",
    "bar": "barra",
    "rollout": "rollout",
    # Termos que vazavam crus pro nome final ("Rosca de punho palm down over
    # no banco", "Encolhimento behind costas"). Ficam aqui, não em _MODIFIERS,
    # porque aparecem soltos quando o movimento já foi casado.
    "palm": "",
    "palms": "",
    "seesaw": "alternado",
    "behind": "atrás de",
    "bent": "curvado",
    "double": "duplo",
    "single": "unilateral",
    "jerk": "arremesso",
    "over": "",
    "around": "em círculo",
    "through": "",
    "inner": "interna",
    "outer": "externa",
    "wide": "aberta",
    "close": "fechada",
    "world": "",
    "windmill": "moinho",
    "hang": "suspenso",
    "split": "afundo",
    "pulley": "polia",
    "leverage": "na máquina",
    "facing": "",
    "in": "",
    "down": "",
    "rear": "posterior",
    "side": "lateral",
    "low": "baixa",
    "high": "alta",
    "medium": "média",
    "narrow": "fechada",
    "alternating": "alternado",
    "alternate": "alternado",
    "legged": "",
    "twist": "com rotação",
    "twisting": "com rotação",
    "slam": "arremesso",
    "mixed": "mista",
    "chin": "na barra fixa",
    "straight": "reta",
    "cross": "cruzado",
    "body": "corpo",
    "weighted": "com peso",
    "assisted": "assistida",
    "negative": "negativa",
    "partial": "parcial",
    "isometric": "isométrico",
    # Palavras que ainda apareciam cruas nos nomes traduzidos (round 2).
    "abduction": "abdução",
    "adduction": "adução",
    "abductor": "abdutora",
    "adductor": "adutora",
    "flexion": "flexão",
    "flexor": "flexora",
    "inverse": "inversa",
    "wall": "na parede",
    "sled": "",
    "version": "",
    "scapular": "escapular",
    "self": "",
    "eccentric": "excêntrica",
    "prisoner": "",
    "pov": "",
    "goblet": "goblet",
    # Movimentos que aparecem como SECUNDÁRIOS num nome composto (o núcleo já
    # foi casado antes): sem isto vazavam em inglês ("... twist row" -> "row").
    "row": "remada",
    "fly": "crucifixo",
    "flye": "crucifixo",
    "squat": "agachamento",
    "lunge": "afundo",
    "deadlift": "levantamento terra",
    "pushdown": "na polia",
    "pulldown": "puxada",
    "thrust": "elevação",
    # Modificadores/ruído que faltavam nos nomes mais obscuros.
    "floor": "no chão",
    "advanced": "avançado",
    "renegade": "renegado",
    "kick": "chute",
    "kicks": "chutes",
    "flutter": "",
    "complex": "",
    "position": "",
    "from": "",
    "bottom": "",
    "bottoms": "",
    "get": "",
    "style": "",
}

_STOPWORDS = {"the", "a", "an", "with", "and", "on", "of", "to", "for", "your", "smr", "up", "ups"}

# Singularização mínima pra casar movimentos no plural ("Curls", "Step Ups").
_SPECIAL_SINGULAR = {
    "presses": "press", "flyes": "fly", "flys": "fly", "crunches": "crunch",
    "dips": "dip", "rows": "row", "raises": "raise", "curls": "curl",
    "lunges": "lunge", "extensions": "extension", "shrugs": "shrug",
    "squats": "squat", "deadlifts": "deadlift", "pulldowns": "pulldown",
    "pushups": "pushup", "pullups": "pullup", "swings": "swing",
    "thrusters": "thruster", "burpees": "burpee", "twists": "twist",
    "climbers": "climber", "ups": "up",
}


def _singular(tok: str) -> str:
    if tok in _SPECIAL_SINGULAR:
        return _SPECIAL_SINGULAR[tok]
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _norm(name: str) -> str:
    s = name.lower().replace("/", " ").replace("-", " ")
    s = re.sub(r"\(.*?\)", " ", s)  # tira parênteses "(single response)"
    s = re.sub(r"[^a-z0-9 ]", " ", s)  # tira pontuação solta (smr, etc.)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _match_longest(tokens: list[str], table: dict) -> tuple[str | None, int, int]:
    """Acha a frase mais longa de `table` presente em `tokens`. Devolve
    (chave, índice_inicial, tamanho_em_tokens)."""
    best = (None, -1, 0)
    for start in range(len(tokens)):
        for length in range(min(4, len(tokens) - start), 0, -1):
            phrase = " ".join(tokens[start : start + length])
            if phrase in table and length > best[2]:
                best = (phrase, start, length)
    return best


def _tr_leftover(tok: str) -> str:
    """Traduz um token solto. Um termo mapeado para "" deve ser DESCARTADO.

    Cuidado com o encadeamento por `or` aqui: "" é falsy, então
    `_LEFTOVER_TERMS.get(tok) or ... or _singular(tok)` tratava "descartar"
    como "não achei" e devolvia a palavra em inglês intacta — era por isso que
    "Two-Arm Kettlebell Jerk" virava "Jerk two braço com kettlebell" mesmo com
    "two": "" no dicionário. Testar a PRESENÇA da chave, não a verdade do valor.
    """
    for key in (tok, _singular(tok)):
        if key in _LEFTOVER_TERMS:
            return _LEFTOVER_TERMS[key]
    return _singular(tok)


def translate_exercise_name(english: str) -> str:
    original = _norm(english).split()
    if not original:
        return english
    # tokens singularizados só pra CASAR (movimentos/equipamento no plural);
    # índices continuam alinhados com `original` (singularização é 1:1).
    tokens = [_singular(t) for t in original]

    # 1) movimento (o núcleo) — frase mais longa que casar
    mv_key, mv_start, mv_len = _match_longest(tokens, _MOVEMENTS)
    if mv_key is None:
        return _fallback(tokens, english)
    mv_pt, gender = _MOVEMENTS[mv_key]
    used = set(range(mv_start, mv_start + mv_len))

    # 2) equipamento(s) — remove do restante, vira frase preposicional
    equip_phrases: list[str] = []
    remaining = [i for i in range(len(tokens)) if i not in used]
    changed = True
    while changed:
        changed = False
        sub = [tokens[i] for i in remaining]
        eq_key, eq_start, eq_len = _match_longest(sub, _EQUIPMENT)
        if eq_key is not None:
            frase = _EQUIPMENT[eq_key]
            # Dedup: "leverage machine" casa "leverage" E "machine", ambos ->
            # "na máquina". E alguns movimentos já embutem o equipamento ("chest
            # press" -> "Supino na máquina"), então o "machine"/"lever" do nome
            # repetiria: "Supino na máquina ... na máquina". Consome os tokens de
            # qualquer jeito, mas só acrescenta a frase se ela ainda não apareceu
            # (nem na lista de equipamentos, nem já dentro do movimento).
            if frase not in equip_phrases and frase not in mv_pt:
                equip_phrases.append(frase)
            drop = remaining[eq_start : eq_start + eq_len]
            remaining = [i for i in remaining if i not in drop]
            changed = True

    # 3) modificadores — concorda com o gênero do movimento
    mod_phrases: list[str] = []
    changed = True
    while changed:
        changed = False
        sub = [tokens[i] for i in remaining]
        md_key, md_start, md_len = _match_longest(sub, _MODIFIERS)
        if md_key is not None:
            val = _MODIFIERS[md_key]
            mod_phrases.append(val[gender] if isinstance(val, dict) else val)
            drop = remaining[md_start : md_start + md_len]
            remaining = [i for i in remaining if i not in drop]
            changed = True

    # 4) tokens que sobraram (músculo/alvo) — traduz e mantém no fim
    leftovers = [_tr_leftover(original[i]) for i in remaining if original[i] not in _STOPWORDS]

    parts = [mv_pt]
    parts.extend(mod_phrases)
    if leftovers:
        parts.append(" ".join(leftovers))
    parts.extend(equip_phrases)
    result = " ".join(p for p in parts if p).strip()
    result = re.sub(r"\s+", " ", result)
    return result[:1].upper() + result[1:]


def _fallback(tokens: list[str], original_str: str) -> str:
    """Sem movimento reconhecido: traduz equipamento/modificador/músculo
    soltos e mantém o resto. Melhor que o inglês cru, mesmo sem reordenar."""
    sing = [_singular(t) for t in tokens]
    out = []
    i = 0
    while i < len(sing):
        matched = False
        for length in (2, 1):
            phrase = " ".join(sing[i : i + length])
            if phrase in _EQUIPMENT:
                out.append(_EQUIPMENT[phrase]); i += length; matched = True; break
            if phrase in _MODIFIERS:
                v = _MODIFIERS[phrase]
                out.append(v["m"] if isinstance(v, dict) else v); i += length; matched = True; break
            if phrase in _LEFTOVER_TERMS:
                out.append(_LEFTOVER_TERMS[phrase]); i += length; matched = True; break
        if not matched:
            out.append(sing[i]); i += 1
    result = re.sub(r"\s+", " ", " ".join(o for o in out if o and o not in _STOPWORDS)).strip()
    return (result[:1].upper() + result[1:]) if result else original_str
