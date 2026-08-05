"""Quanto treino cabe na combinação TEMPO POR SESSÃO × DIAS POR SEMANA.

O produto não bloqueia combinação nenhuma: quem quer treinar 3 dias curtos pode.
Mas 3 dias × 5 exercícios são 15 vagas pra 10 grupos musculares, e não dá pra
todo mundo ter exercício próprio — alguém fica de fora, e a pessoa merece saber
disso ANTES de treinar seis semanas achando que está cobrindo o corpo inteiro.

Este módulo responde uma pergunta só, sem tocar no banco: *com este tempo e esta
frequência, quais grupos musculares ficam sem exercício dedicado?* A conta é
feita em cima dos BLUEPRINTS (que são dados puros) aplicando o mesmo recorte por
tempo que o motor aplica, então ela concorda com o treino que vai sair — não é
uma estimativa paralela que um dia diverge.

O que sai daqui vira aviso na tela de preferências, com uma recomendação de
tempo maior. Aviso, não bloqueio: a pessoa decide.
"""

from __future__ import annotations

from app.ai import session_blueprints as bp
from app.ai.methods import coach_split_for
from app.coaching import training_brain
from app.models.exercise import MuscleGroup

# Grupos que a gente cobra na conta. Abdômen entra desde que o corte por tempo
# passou a ser da semana (`fit_week_to_target`): antes ele era `priority=3` e o
# primeiro a cair em toda combinação, então cobrá-lo teria feito o aviso aparecer
# sempre e virar ruído que ninguém lê. Agora ele só some se realmente não couber,
# e aí a pessoa merece saber.
_GRUPOS_COBRADOS: tuple[MuscleGroup, ...] = (
    MuscleGroup.CHEST,
    MuscleGroup.BACK,
    MuscleGroup.SHOULDERS,
    MuscleGroup.BICEPS,
    MuscleGroup.TRICEPS,
    MuscleGroup.QUADS,
    MuscleGroup.HAMSTRINGS,
    MuscleGroup.GLUTES,
    MuscleGroup.CALVES,
    MuscleGroup.ABS,
)

_LABEL = dict(training_brain.WEAK_POINTS)


def grupos_sem_vaga(
    days: int,
    session_length: str | None,
    weak_points: list[str] | None = None,
    split_preference: str | None = None,
) -> list[MuscleGroup]:
    """Grupos musculares que NÃO ganham exercício próprio nesta combinação.

    Ponto fraco nunca entra na lista: `workout_builder` garante exercício pra ele
    em qualquer configuração (é a regra "quem marcou prioridade não termina a
    semana sem um exercício dela"). Avisar sobre um músculo que o coach vai
    cobrir de qualquer jeito seria mentira.
    """
    alvo = training_brain.session_exercise_target(session_length)
    fracos = set(training_brain.valid_weak_points(weak_points))
    # O MESMO corte que o motor aplica — de semana, não de sessão. Recortando dia
    # a dia (como era), esta conta enxergava panturrilha e abdômen caindo em toda
    # combinação e o aviso ficava permanente; o motor agora protege os dois, e um
    # aviso que não concorda com o treino que sai é pior que aviso nenhum.
    split = coach_split_for(days, list(fracos), split_preference)
    semana = bp.fit_week_to_target([bp.blueprint_for(f) for f in split], alvo)
    com_vaga: set[MuscleGroup] = {vaga.muscle for dia in semana for vaga in dia}
    return [
        m for m in _GRUPOS_COBRADOS if m not in com_vaga and m.value not in fracos
    ]


def tempo_recomendado(
    days: int, weak_points: list[str] | None = None, split_preference: str | None = None
) -> str | None:
    """O MENOR tempo por sessão que cobre o corpo inteiro nesta frequência, ou
    None se nem o mais longo cobre (2 dias por semana é assim: não existe tempo
    de sessão que faça 2 treinos cobrirem tudo com exercício próprio)."""
    for valor, _, _, _ in training_brain.SESSION_LENGTHS:
        if not grupos_sem_vaga(days, valor, weak_points, split_preference):
            return valor
    return None


def aviso(
    days: int, session_length: str | None, weak_points: list[str] | None = None
) -> str | None:
    """O aviso pra tela, ou None quando a combinação cobre tudo.

    Uma frase só, dizendo o que fica de fora e o que fazer a respeito. Sem tom de
    erro: a escolha da pessoa é legítima, e treino curto que ela faz vale mais
    que treino longo que ela não faz.
    """
    faltando = grupos_sem_vaga(days, session_length, weak_points)
    if not faltando:
        return None
    nomes = ", ".join(_LABEL.get(m.value, m.value) for m in faltando)
    plural = len(faltando) > 1
    texto = (
        f"Com {days} dia{'s' if days > 1 else ''} por semana e treino "
        f"{_rotulo(session_length)}, {nomes} "
        f"{'ficam' if plural else 'fica'} sem exercício próprio — "
        f"{'eles seguem sendo trabalhados' if plural else 'ele segue sendo trabalhado'} "
        "de forma indireta pelos outros exercícios."
    )
    recomendado = tempo_recomendado(days, weak_points)
    if recomendado and recomendado != session_length:
        texto += f" Pra cobrir tudo, escolha o tempo {_rotulo(recomendado)}."
    else:
        texto += (
            " Nessa frequência não cabe tudo em nenhum tempo de sessão. "
            "Marcar um deles como ponto fraco garante exercício pra ele."
        )
    return texto


def _rotulo(session_length: str | None) -> str:
    for valor, label, _, _ in training_brain.SESSION_LENGTHS:
        if valor == session_length:
            return label
    return "—"
