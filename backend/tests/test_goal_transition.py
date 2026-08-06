"""TROCAR DE OBJETIVO NÃO VIRA A CHAVE DE UMA VEZ.

Sair de um corte pra um bulk (ou o contrário) move a meta de calorias em
centenas de kcal. O coach faz isso em degraus: aplica um passo capado, abre uma
transição e caminha até o alvo nos passos seguintes — é o que um treinador de
verdade faz, e é o que protege músculo (subindo) e adesão (descendo).

Essa regra existia só no caminho da tela de meta (`apply_auto_goal`). Quem
trocava o objetivo pelo QUESTIONÁRIO da aba Objetivo passava por
`plan_service._rebuild_goals`, que gravava a meta nova inteira no mesmo dia. Os
dois caminhos agora chamam a MESMA função (`goal_service.stage_auto_goal`), e
esta suíte é o que impede a regra de voltar a existir em um só lugar.

Sem banco de verdade não dá pra testar isto: a decisão depende da meta vigente
e da transição aberta, que são linhas no banco.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.models.calorie_goal import CalorieGoal, GoalMode
from app.models.coaching_transition import CoachingTransition
from app.models.user import Plan, User
from app.models.user_profile import (
    ActivityLevel,
    BiologicalSex,
    ExperienceLevel,
    Goal,
    TrainingLocation,
    UserProfile,
)
from app.services import goal_service

# Uma "sugestão" no formato que compute_auto_goal/compute_suggestion devolvem.
def _sugestao(kcal: float) -> dict:
    return {"kcal": kcal, "protein_g": 160.0, "carbs_g": 250.0, "fat_g": 70.0}


@pytest.fixture(scope="module")
def db():
    from app.core.db import SessionLocal

    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def user(db):
    email = "__tmp_transicao__@teste.local"

    def limpar():
        u = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if u is not None:
            db.execute(delete(CoachingTransition).where(CoachingTransition.user_id == u.id))
            db.execute(delete(CalorieGoal).where(CalorieGoal.user_id == u.id))
            db.execute(delete(UserProfile).where(UserProfile.user_id == u.id))
            db.execute(delete(User).where(User.id == u.id))
            db.commit()

    limpar()
    u = User(email=email, handle="__tmp_tr__", display_name="T", password_hash="x", plan=Plan.PRO)
    db.add(u)
    db.flush()
    db.add(UserProfile(
        user_id=u.id, age=30, height_cm=180,
        biological_sex=BiologicalSex.MALE, activity_level=ActivityLevel.MODERATE,
        training_location=TrainingLocation.ACADEMIA_COMPLETA,
        experience_level=ExperienceLevel.INTERMEDIARIO, goal=Goal.EMAGRECIMENTO,
    ))
    db.commit()
    db.refresh(u)
    try:
        yield u
    finally:
        limpar()


def _meta(db, user, kcal: float) -> CalorieGoal:
    g = CalorieGoal(user_id=user.id, mode=GoalMode.AUTO, kcal=kcal,
                    protein_g=160, carbs_g=200, fat_g=60)
    db.add(g)
    db.commit()
    return g


def test_primeira_meta_entra_inteira(db, user):
    """Sem meta anterior não existe "salto": não há de onde caminhar."""
    g = goal_service.stage_auto_goal(
        db, user.id, _sugestao(2600), current=None, objective="hipertrofia"
    )
    db.commit()
    assert g.kcal == 2600
    assert goal_service.active_transition(db, user.id) is None


def test_mudanca_pequena_vai_direto(db, user):
    atual = _meta(db, user, 2400)
    g = goal_service.stage_auto_goal(
        db, user.id, _sugestao(2500), current=atual, objective="hipertrofia"
    )
    db.commit()
    assert g.kcal == 2500, "diferença menor que um degrau não precisa de transição"
    assert goal_service.active_transition(db, user.id) is None


def test_salto_grande_aplica_so_um_degrau_e_abre_transicao(db, user):
    """O caso do usuário: emagrecimento (2000) -> hipertrofia (2900). A meta de
    hoje NÃO pode virar 2900."""
    atual = _meta(db, user, 2000)
    g = goal_service.stage_auto_goal(
        db, user.id, _sugestao(2900), current=atual, objective="hipertrofia"
    )
    db.commit()

    assert g.kcal == 2000 + goal_service.TRANSITION_STEP_KCAL, (
        "a meta pulou direto pro alvo — é exatamente o que a transição existe pra impedir"
    )
    tr = goal_service.active_transition(db, user.id)
    assert tr is not None
    assert tr.to_objective == "hipertrofia"
    assert tr.from_kcal == 2000 and tr.target_kcal == 2900


def test_regerar_o_plano_no_meio_da_transicao_nao_empurra_outro_degrau(db, user):
    """Mexer em outra resposta (dias de treino, peso) regera as metas junto. Se
    isso desse mais um degrau, quem editasse o questionário três vezes no mesmo
    dia chegaria no alvo em um dia — sem transição nenhuma, na prática."""
    atual = _meta(db, user, 2000)
    primeiro = goal_service.stage_auto_goal(
        db, user.id, _sugestao(2900), current=atual, objective="hipertrofia"
    )
    db.commit()
    de_novo = goal_service.stage_auto_goal(
        db, user.id, _sugestao(2900),
        current=goal_service.get_current_goal(db, user.id), objective="hipertrofia",
    )
    db.commit()
    assert de_novo.id == primeiro.id, "o segundo passe criou uma meta nova no mesmo dia"
    assert de_novo.kcal == 2250


def test_trocar_de_rumo_no_meio_cancela_a_transicao_antiga(db, user):
    atual = _meta(db, user, 2000)
    goal_service.stage_auto_goal(
        db, user.id, _sugestao(2900), current=atual, objective="hipertrofia"
    )
    db.commit()
    # Desistiu do bulk e voltou pro corte antes de chegar lá.
    goal_service.stage_auto_goal(
        db, user.id, _sugestao(1600),
        current=goal_service.get_current_goal(db, user.id), objective="emagrecimento",
    )
    db.commit()

    abertas = list(db.execute(
        select(CoachingTransition).where(
            CoachingTransition.user_id == user.id,
            CoachingTransition.completed_at.is_(None),
        )
    ).scalars())
    assert len(abertas) == 1, "ficou mais de uma transição aberta ao mesmo tempo"
    assert abertas[0].to_objective == "emagrecimento"
    assert goal_service.get_current_goal(db, user.id).kcal == 2250 - goal_service.TRANSITION_STEP_KCAL


def test_primeiro_objetivo_ignora_a_transicao_de_proposito(db, user):
    """"Considerar como primeiro objetivo" é o recomeço explícito — aí a pessoa
    pediu pra ir direto, e o coach obedece."""
    atual = _meta(db, user, 2000)
    g = goal_service.stage_auto_goal(
        db, user.id, _sugestao(2900), current=atual, objective="hipertrofia", immediate=True
    )
    db.commit()
    assert g.kcal == 2900
    assert goal_service.active_transition(db, user.id) is None
