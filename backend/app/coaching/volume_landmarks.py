"""Volume semanal de séries de TRABALHO EFETIVAS por grupo muscular.

A régua operacional do produto é uma **faixa-base de 5 a 12 séries semanais por
músculo** (spec §6.1). Ela existe pra matar o vício de "3 séries pra tudo": o
mesmo volume distribuído igual pro corpo inteiro ignora que a pessoa tem
prioridades, que alguns músculos já estão desenvolvidos, e que a capacidade de
recuperação é finita.

As regras, na ordem em que mandam:

1. **Faixa-base 5–12.** É o padrão de quem não tem prioridade nenhuma naquele
   músculo. Nunca é o mesmo número pro corpo inteiro por default.
2. **Ponto forte / já desenvolvido / sem prioridade pode ficar perto de 5.**
   Manter não custa o mesmo que crescer.
3. **Ponto fraco recebe mais: 8 a 16**, conforme prioridade, experiência,
   recuperação e frequência.
4. **20 a 22 séries é EXCEPCIONAL** — no máximo um ou dois músculos por vez, e
   só reduzindo o resto.
5. **Equalização obrigatória.** Quando o volume sobe muito numa prioridade, o
   coach reduz os outros grupos. Recuperação é sistêmica, não por músculo: sem
   isso a pessoa só acumula fadiga e para de progredir em tudo ao mesmo tempo.

Os landmarks MEV/MRV continuam existindo como TETO por músculo — glúteo e
posterior não recuperam o mesmo que costas, e a faixa-base não pode passar por
cima disso.
"""

from __future__ import annotations

from app.coaching import training_brain
from app.models.exercise import MuscleGroup

# (MEV, MRV) semanais por grupo muscular — o teto de recuperação de cada um.
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

# Faixa-base operacional (spec §6.1). NÃO é garantia universal: é o ponto de
# partida do sistema, individualizado pelas regras abaixo.
BASE_MIN = 5
BASE_MAX = 12

# Ponto fraco: recebe mais volume, dentro do que ainda dá pra recuperar.
WEAK_MIN = 8
WEAK_MAX = 16

# Excepcional — só com prioridade máxima, em 1 ou 2 músculos, cortando o resto.
EXCEPTIONAL_MIN = 20
EXCEPTIONAL_MAX = 22
MAX_EXCEPTIONAL_MUSCLES = 2

# Iniciante recupera menos volume (fica perto do piso); avançado tolera e
# precisa de mais pra progredir.
_LEVEL_FACTOR = {"iniciante": 0.75, "intermediario": 1.0, "avancado": 1.15}

# Faixa segura de séries por EXERCÍCIO (depois de distribuir o volume do
# músculo entre as vagas que o treinam) — nunca deixa 1 exercício isolado
# carregar todo o volume do músculo nem virar quantidade irrisória.
PER_EXERCISE_MIN = 2
PER_EXERCISE_MAX = 4


def weekly_set_range(muscle: MuscleGroup, level: str | None) -> tuple[int, int]:
    """(MEV, MRV) semanal já ajustado pro nível da pessoa. É o TETO de
    recuperação do músculo — a faixa-base opera por dentro dele."""
    mev, mrv = _LANDMARKS.get(muscle, (8, 18))
    factor = _LEVEL_FACTOR.get(level or "intermediario", 1.0)
    return max(1, round(mev * factor)), max(mev + 2, round(mrv * factor))


def _progress(weeks_accumulating: float | None) -> float:
    """0 a 1 ao longo do mesociclo — o volume sobe do piso da faixa até o topo
    conforme a pessoa acumula semanas sem deload."""
    return min(1.0, max(0.0, (weeks_accumulating or 0.0) / training_brain.MESOCYCLE_WEEKS))


# Extremos de MRV entre todos os músculos — usados pra posicionar cada um
# DENTRO da faixa-base em vez de dar o mesmo número pra todo mundo.
_MRV_MIN = min(mrv for _, mrv in _LANDMARKS.values() if mrv > 0)
_MRV_MAX = max(mrv for _, mrv in _LANDMARKS.values())


def _band_top(muscle: MuscleGroup) -> float:
    """Topo da faixa-base PARA ESTE MÚSCULO.

    A spec é explícita: "não distribuir o mesmo volume para o corpo inteiro por
    padrão". Costas (MRV 22) e glúteo (MRV 16) não recuperam igual, então o
    topo da faixa de cada um é diferente — costas chega nas 12, glúteo para
    antes. A faixa continua sendo 5–12: o que muda é até onde cada músculo vai
    dentro dela.
    """
    _, mrv = _LANDMARKS.get(muscle, (8, 18))
    if _MRV_MAX == _MRV_MIN:
        return BASE_MAX
    posicao = (mrv - _MRV_MIN) / (_MRV_MAX - _MRV_MIN)  # 0..1
    # Mesmo o músculo de menor recuperação chega a ~60% da faixa — o piso da
    # faixa-base continua sendo 5 pra todos.
    return BASE_MIN + (BASE_MAX - BASE_MIN) * (0.6 + 0.4 * posicao)


def weekly_target_sets(
    muscle: MuscleGroup,
    level: str | None,
    weeks_accumulating: float | None,
    *,
    priority: str = "normal",
) -> int:
    """Séries semanais efetivas pro músculo. `priority`:

    - "baixa"       -> ponto forte / já desenvolvido / sem prioridade: perto de 5
    - "normal"      -> faixa-base 5–12, subindo ao longo do mesociclo
    - "alta"        -> ponto fraco: 8–16
    - "excepcional" -> 20–22 (só 1–2 músculos, e com o resto reduzido)

    O teto de recuperação do músculo (MRV ajustado pelo nível) vence sempre:
    prescrever 16 séries de posterior porque virou prioridade não faz o
    posterior recuperar 16.
    """
    _, mrv = weekly_set_range(muscle, level)
    p = _progress(weeks_accumulating)
    fator = _LEVEL_FACTOR.get(level or "intermediario", 1.0)

    if priority == "baixa":
        # Ponto forte / já desenvolvido: manter custa pouco — fica perto de 5.
        alvo = BASE_MIN
    elif priority == "alta":
        alvo = WEAK_MIN + (WEAK_MAX - WEAK_MIN) * p
    elif priority == "excepcional":
        alvo = EXCEPTIONAL_MIN + (EXCEPTIONAL_MAX - EXCEPTIONAL_MIN) * p
    else:
        # Faixa-base, com o TOPO próprio de cada músculo (§6.1: nada de mesmo
        # volume pro corpo inteiro).
        alvo = BASE_MIN + (_band_top(muscle) - BASE_MIN) * p

    alvo = round(alvo * fator)
    teto = mrv if priority == "excepcional" else min(mrv, EXCEPTIONAL_MAX)
    return max(1, min(alvo, teto))


def weekly_plan(
    muscles: list[MuscleGroup],
    level: str | None,
    weeks_accumulating: float | None,
    *,
    weak_points: list[MuscleGroup] | None = None,
    exceptional: list[MuscleGroup] | None = None,
) -> dict[MuscleGroup, int]:
    """O volume semanal de TODOS os músculos da semana, de uma vez.

    Precisa ser calculado junto (e não músculo a músculo) por causa da
    **equalização obrigatória** (§6.1): a capacidade de recuperação é sistêmica,
    então o que sobe num ponto fraco tem que descer em outro lugar. Calcular
    isolado é como cada área da empresa pedir orçamento sem olhar o caixa.
    """
    weak = set(weak_points or [])
    # Excepcional é raro por definição: no máximo 2 músculos, e só entre os que
    # já são ponto fraco (ninguém leva um músculo sem prioridade a 22 séries).
    exc = [m for m in (exceptional or []) if m in weak][:MAX_EXCEPTIONAL_MUSCLES]

    def prioridade(m: MuscleGroup) -> str:
        if m in exc:
            return "excepcional"
        if m in weak:
            return "alta"
        return "normal"

    plano = {m: weekly_target_sets(m, level, weeks_accumulating, priority=prioridade(m)) for m in muscles}
    if not weak:
        return plano

    # --- Equalização --------------------------------------------------------
    # Orçamento: o que a semana custaria se ninguém fosse prioridade. O extra
    # gasto nos pontos fracos sai dos demais, um set por vez, em rodízio — o
    # músculo mais volumoso cede primeiro. Piso: BASE_MIN (a regra é "podem
    # permanecer PRÓXIMOS de 5", não "podem sumir do treino").
    orcamento = sum(
        weekly_target_sets(m, level, weeks_accumulating, priority="normal") for m in muscles
    )
    ajustaveis = [m for m in muscles if m not in weak]
    guarda = 0
    while sum(plano.values()) > orcamento and ajustaveis and guarda < 500:
        guarda += 1
        candidatos = [m for m in ajustaveis if plano[m] > BASE_MIN]
        if not candidatos:
            break  # já estão todos no piso — a fadiga extra é assumida e consciente
        alvo = max(candidatos, key=lambda m: plano[m])
        plano[alvo] -= 1
    return plano
