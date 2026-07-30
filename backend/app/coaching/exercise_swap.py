"""Trocar UM exercício da rotina pelo melhor substituto, pela regra mestra.

É o botão de trocar da prévia do treino. A pessoa não escolhe o substituto: ela
diz "esse aqui não", e o coach escolhe — do mesmo jeito que escolheu na montagem,
pelas mesmas regras. Trocar não pode virar uma porta lateral pra montar um treino
que a regra reprovaria.

O que o substituto preserva, na ordem em que a exigência cai (a mesma escada de
`methods_engine._pick_for_slot`, e pelo mesmo motivo: só relaxa quando a exigência
anterior não deixou candidato nenhum):

  1. músculo + padrão de movimento + região (a FUNÇÃO exata da vaga);
  2. músculo + padrão (solta a região);
  3. músculo + classe de ordem (solta o padrão, mas nunca troca um composto por
     um isolador — isso mudaria a ordem do treino, não só o exercício).

E em toda passada valem, sem exceção: o tier manda (S antes de A antes de B antes
de C), as preferências da pessoa excluem e ordenam, nenhum exercício que já está
na rotina volta, e a troca não pode criar uma terceira vaga da mesma função
(Princípio 4 — o teto de 2 é o mesmo que `plan_review.redundancias` cobra).

A troca mexe na ROTINA (o molde), não na sessão: acontece antes de treinar, é
disso que a pessoa está falando quando diz "quero trocar esse exercício". Séries,
reps e descanso são preservados — o volume da semana foi calculado com esta vaga
existindo, e trocar o exercício não muda o que o músculo precisa receber.
"""

from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from app.ai import methods_engine
from app.ai.exercise_taxonomy import taxon_for_exercise, tier_rank
from app.coaching import training_brain
from app.models.exercise import Exercise
from app.models.routine import RoutineExercise
from app.models.user import User

# Teto de vagas com a mesma função numa rotina. O mesmo do plan_review: 2 é
# volume legítimo (o "segundo estímulo do grupo prioritário"), 3 é a mesma coisa
# três vezes.
_MAX_MESMA_FUNCAO = 2


def melhor_substituto(
    db: Session, user: User, alvo: RoutineExercise, na_rotina: list[RoutineExercise]
) -> Exercise | None:
    """O exercício que entra no lugar do `alvo`, ou None se a base não tem
    substituto que sirva sem quebrar a regra."""
    original = alvo.exercise or db.get(Exercise, alvo.exercise_id)
    if original is None:
        return None
    taxon_original = taxon_for_exercise(original)

    profile = getattr(user, "profile", None)
    prefs = frozenset(
        training_brain.valid_exercise_prefs(getattr(profile, "exercise_prefs", None))
        if profile is not None
        else ()
    )
    prefere_maquinas = "maquinas" in prefs

    ja_na_rotina = {re.exercise_id for re in na_rotina}
    # Funções que a rotina já pratica, SEM contar a vaga que está saindo — ela
    # abre espaço pra própria função ao sair.
    funcoes: Counter = Counter()
    for re in na_rotina:
        if re.id == alvo.id:
            continue
        ex = re.exercise or db.get(Exercise, re.exercise_id)
        if ex is not None:
            t = taxon_for_exercise(ex)
            funcoes[(t.pattern, t.region)] += 1

    candidatos = [
        c
        for c in methods_engine.load_candidates(db)
        if c.ex.primary_muscle_group == original.primary_muscle_group
        and c.ex.id not in ja_na_rotina
        and not methods_engine.proibido_por_preferencia(c.nome_norm, prefs)
        and funcoes[(c.taxon.pattern, c.taxon.region)] < _MAX_MESMA_FUNCAO
    ]
    if not candidatos:
        return None

    def equivalencia(c) -> tuple:
        return (
            tier_rank(c.taxon.tier),
            methods_engine.peso_de_preferencia(c.nome_norm, c.ex.equipment, prefs),
            0 if (prefere_maquinas and c.ex.equipment in methods_engine.ESTAVEIS) else 1,
        )

    mesma_ordem = [c for c in candidatos if c.taxon.order_class == taxon_original.order_class]
    mesmo_padrao = [c for c in mesma_ordem if c.taxon.pattern is taxon_original.pattern]

    for tentativa in (
        [c for c in mesmo_padrao if c.taxon.region == taxon_original.region],
        mesmo_padrao,
        mesma_ordem,
    ):
        if not tentativa:
            continue
        ordenados = sorted(tentativa, key=lambda c: (*equivalencia(c), c.qualidade))
        escolhido = methods_engine.escolher_com_variacao(
            ordenados, equivalencia, user.id, "troca", alvo.id
        )
        return escolhido.ex
    return None


def explicar(original: Exercise, substituto: Exercise) -> str:
    """Por que ESTE substituto — em uma frase que a pessoa entende."""
    t_orig, t_novo = taxon_for_exercise(original), taxon_for_exercise(substituto)
    if t_novo.pattern is t_orig.pattern and t_novo.region == t_orig.region:
        return (
            f"{substituto.name} cumpre exatamente o mesmo papel de {original.name} no seu treino — "
            "mesmo padrão de movimento, mesma região do músculo. Suas séries e reps continuam iguais."
        )
    if t_novo.pattern is t_orig.pattern:
        return (
            f"{substituto.name} mantém o padrão de movimento de {original.name}, "
            "pegando o músculo de um ângulo um pouco diferente. Suas séries e reps continuam iguais."
        )
    return (
        f"{substituto.name} entra no lugar de {original.name} mantendo o papel dele no treino. "
        "Suas séries e reps continuam iguais."
    )
