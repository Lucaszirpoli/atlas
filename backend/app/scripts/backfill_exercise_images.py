"""Busca na ExerciseDB (RapidAPI) um GIF demonstrativo pra cada exercício
curado que ainda não tem imagem (os importados da base aberta já têm, ver
seed_exercises_open.py) e salva localmente em app/static/exercise_images/.

Cada exercício custa até 2 chamadas (busca por nome + download da imagem do
melhor candidato) — dentro da cota do plano gratuito (690/mês). Idempotente:
pula exercícios que já têm video_url ou cujo arquivo já existe em disco.

Uso: python -m app.scripts.backfill_exercise_images
"""
from __future__ import annotations

import difflib
import re
import time
from pathlib import Path

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.data.exercise_translator import translate_exercise_name
from app.models.exercise import Equipment, Exercise, MuscleGroup

API_HOST = "exercisedb.p.rapidapi.com"
STATIC_DIR = Path(__file__).parent.parent / "static" / "exercise_images"
MATCH_THRESHOLD = 0.45

# Termo de busca em inglês por padrão de movimento — usado só pra achar
# candidatos na ExerciseDB, não precisa ser uma tradução perfeita.
MOVEMENT_QUERY: list[tuple[re.Pattern, str]] = [
    (re.compile(r"supino declinado", re.I), "decline bench press"),
    (re.compile(r"supino inclinado", re.I), "incline bench press"),
    (re.compile(r"supino", re.I), "bench press"),
    (re.compile(r"crucifixo|voador", re.I), "fly"),
    (re.compile(r"crossover", re.I), "cable crossover"),
    (re.compile(r"puxada frontal|puxada supinada|puxada tri[aâ]ngulo|pulldown|lat pull", re.I), "lat pulldown"),
    (re.compile(r"barra fixa|pull.?up", re.I), "pull up"),
    (re.compile(r"remada", re.I), "row"),
    (re.compile(r"rosca martelo", re.I), "hammer curl"),
    (re.compile(r"rosca scott", re.I), "preacher curl"),
    (re.compile(r"rosca", re.I), "biceps curl"),
    (re.compile(r"tr[ií]ceps.*polia|puxada.*tr[ií]ceps|pushdown", re.I), "triceps pushdown"),
    (re.compile(r"tr[ií]ceps.*testa|skull", re.I), "skullcrusher"),
    (re.compile(r"mergulho|paralelas|dip", re.I), "dip"),
    (re.compile(r"desenvolvimento.*arnold|arnold", re.I), "arnold press"),
    (re.compile(r"desenvolvimento|militar", re.I), "shoulder press"),
    (re.compile(r"eleva[çc][ãa]o lateral", re.I), "lateral raise"),
    (re.compile(r"eleva[çc][ãa]o frontal", re.I), "front raise"),
    (re.compile(r"encolhimento", re.I), "shrug"),
    (re.compile(r"agachamento frontal", re.I), "front squat"),
    (re.compile(r"agachamento|hack|leg press", re.I), "squat"),
    (re.compile(r"afundo|passada|b[uú]lgaro|lunge", re.I), "lunge"),
    (re.compile(r"levantamento terra|stiff|deadlift", re.I), "deadlift"),
    (re.compile(r"hip thrust|eleva[çc][ãa]o p[eé]lvica", re.I), "hip thrust"),
    (re.compile(r"good morning", re.I), "good morning"),
    (re.compile(r"cadeira extensora", re.I), "leg extension"),
    (re.compile(r"mesa flexora|cadeira flexora", re.I), "leg curl"),
    (re.compile(r"panturrilha", re.I), "calf raise"),
    (re.compile(r"abdominal|abd[uô]men", re.I), "crunch"),
    (re.compile(r"prancha", re.I), "plank"),
    (re.compile(r"flex[ãa]o (hindu|archer|declinada|diamante|com apoio|de bra[çc]o)", re.I), "push up"),
    (re.compile(r"pullover", re.I), "pullover"),
    (re.compile(r"peck deck", re.I), "fly"),
    (re.compile(r"puxada aberta", re.I), "lat pulldown"),
    (re.compile(r"rack pull", re.I), "rack pull"),
    (re.compile(r"hiperextens[ãa]o", re.I), "hyperextension"),
    (re.compile(r"face pull", re.I), "face pull"),
    (re.compile(r"tr[ií]ceps.*franc[êe]s", re.I), "overhead triceps extension"),
    (re.compile(r"tr[ií]ceps.*coice|kickback", re.I), "triceps kickback"),
    (re.compile(r"flexora.*unilateral|nordic curl", re.I), "nordic curl"),
    (re.compile(r"subida no banco|step.?up", re.I), "step up"),
    (re.compile(r"ponte de gl[uú]teo", re.I), "glute bridge"),
    (re.compile(r"coice.*gl[uú]teo|coice no cabo", re.I), "glute kickback"),
    (re.compile(r"abdu[çc][ãa]o de quadril|abdu[çc][ãa]o com faixa", re.I), "hip abduction"),
    (re.compile(r"adu[çc][ãa]o de quadril", re.I), "hip adduction"),
    (re.compile(r"eleva[çc][ãa]o de joelhos", re.I), "captains chair"),
    (re.compile(r"rota[çc][ãa]o de tronco|woodchopper|russian twist|russa", re.I), "russian twist"),
    (re.compile(r"mountain climber", re.I), "mountain climber"),
    (re.compile(r"burpee", re.I), "burpee"),
    (re.compile(r"thruster", re.I), "thruster"),
    (re.compile(r"clean and press|clean.*press", re.I), "clean and press"),
    (re.compile(r"snatch", re.I), "snatch"),
    (re.compile(r"kettlebell swing", re.I), "kettlebell swing"),
    (re.compile(r"goblet squat", re.I), "goblet squat"),
    (re.compile(r"turkish get.?up", re.I), "turkish get up"),
    (re.compile(r"farmer|caminhada do fazendeiro", re.I), "farmers walk"),
    (re.compile(r"wall ball", re.I), "wall ball"),
    (re.compile(r"box jump", re.I), "box jump"),
    (re.compile(r"muscle.?up", re.I), "muscle up"),
    (re.compile(r"clamshell", re.I), "clamshell"),
    (re.compile(r"caminhada do urso|bear crawl", re.I), "bear crawl"),
    (re.compile(r"superman", re.I), "superman"),
    (re.compile(r"bird dog", re.I), "bird dog"),
    (re.compile(r"extens[ãa]o de punho", re.I), "wrist extension"),
    (re.compile(r"dead bug", re.I), "dead bug"),
]

EQUIPMENT_HINT = {
    Equipment.BARBELL: "barbell",
    Equipment.DUMBBELL: "dumbbell",
    Equipment.MACHINE: "machine",
    Equipment.CABLE: "cable",
    Equipment.BODYWEIGHT: "body weight",
    Equipment.KETTLEBELL: "kettlebell",
    Equipment.BAND: "band",
    Equipment.SMITH_MACHINE: "smith",
    Equipment.OTHER: "",
}

MUSCLE_HINT = {
    MuscleGroup.CHEST: ("chest", "pectorals"),
    MuscleGroup.BACK: ("back", "lats", "upper back"),
    MuscleGroup.SHOULDERS: ("shoulders", "delts"),
    MuscleGroup.BICEPS: ("upper arms", "biceps"),
    MuscleGroup.TRICEPS: ("upper arms", "triceps"),
    MuscleGroup.QUADS: ("upper legs", "quads", "quadriceps"),
    MuscleGroup.HAMSTRINGS: ("upper legs", "hamstrings"),
    MuscleGroup.GLUTES: ("upper legs", "glutes"),
    MuscleGroup.CALVES: ("lower legs", "calves"),
    MuscleGroup.ABS: ("waist", "abs"),
    MuscleGroup.FOREARMS: ("lower arms", "forearms"),
    MuscleGroup.TRAPS: ("back", "traps", "neck"),
    MuscleGroup.FULL_BODY: (),
    MuscleGroup.CARDIO: ("cardio",),
}


def guess_query(name_pt: str) -> str | None:
    for pattern, query in MOVEMENT_QUERY:
        if pattern.search(name_pt):
            return query
    return None


def score_candidate(exercise: Exercise, candidate: dict) -> float:
    score = 0.0
    equip_hint = EQUIPMENT_HINT.get(exercise.equipment, "")
    if equip_hint and equip_hint in (candidate.get("equipment") or "").lower():
        score += 0.4
    hints = MUSCLE_HINT.get(exercise.primary_muscle_group, ())
    body = f"{candidate.get('bodyPart', '')} {candidate.get('target', '')}".lower()
    if any(h in body for h in hints):
        score += 0.2
    candidate_pt = translate_exercise_name(candidate.get("name", ""))
    ratio = difflib.SequenceMatcher(None, exercise.name.lower(), candidate_pt.lower()).ratio()
    score += ratio * 0.4
    return score


def run(limit: int | None = None) -> None:
    if not settings.rapidapi_exercisedb_key:
        print("RAPIDAPI_EXERCISEDB_KEY não configurada no .env — abortando.")
        return

    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    headers = {"x-rapidapi-host": API_HOST, "x-rapidapi-key": settings.rapidapi_exercisedb_key}
    client = httpx.Client(headers=headers, timeout=20)

    db = SessionLocal()
    try:
        exercises = db.execute(
            select(Exercise).where(Exercise.video_url.is_(None), Exercise.is_custom.is_(False))
        ).scalars().all()
        if limit:
            exercises = exercises[:limit]

        print(f"{len(exercises)} exercícios sem imagem. Buscando na ExerciseDB...")
        matched, skipped_no_query, skipped_low_score, errors = 0, 0, 0, 0

        for ex in exercises:
            dest = STATIC_DIR / f"{ex.id}.gif"
            if dest.exists():
                ex.video_url = f"{settings.public_base_url}/static/exercise_images/{ex.id}.gif"
                matched += 1
                db.commit()
                continue

            query = guess_query(ex.name)
            if not query:
                skipped_no_query += 1
                continue

            try:
                resp = client.get(f"https://{API_HOST}/exercises/name/{query}")
                resp.raise_for_status()
                candidates = resp.json()
            except Exception as exc:  # noqa: BLE001 — só queremos logar e seguir
                print(f"  [erro busca] {ex.name}: {exc}")
                errors += 1
                continue

            if not candidates:
                skipped_low_score += 1
                continue

            best = max(candidates, key=lambda c: score_candidate(ex, c))
            if score_candidate(ex, best) < MATCH_THRESHOLD:
                skipped_low_score += 1
                continue

            try:
                img = client.get(
                    f"https://{API_HOST}/image",
                    params={"exerciseId": best["id"], "resolution": 180},
                )
                img.raise_for_status()
                dest.write_bytes(img.content)
            except Exception as exc:  # noqa: BLE001
                print(f"  [erro imagem] {ex.name} -> {best['name']}: {exc}")
                errors += 1
                continue

            ex.video_url = f"{settings.public_base_url}/static/exercise_images/{ex.id}.gif"
            matched += 1
            db.commit()
            print(f"  OK: {ex.name} -> {best['name']} ({best['id']})")

            remaining = resp.headers.get("x-ratelimit-requests-remaining")
            if remaining and int(remaining) < 20:
                print(f"Cota quase no fim ({remaining} restantes) — parando por segurança.")
                break

            time.sleep(0.3)  # gentil com o rate limit por hora

        db.commit()
        print(
            f"\nConcluído: {matched} imagens salvas, {skipped_no_query} sem termo de busca reconhecido, "
            f"{skipped_low_score} sem candidato confiável, {errors} erros."
        )
    finally:
        db.close()
        client.close()


if __name__ == "__main__":
    run()
