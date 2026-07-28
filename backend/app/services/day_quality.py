"""Qualidade do dia alimentar — o que pode alimentar uma média (spec §10).

Duas regras que valem pra TODAS as análises do coach:

1. **O dia de hoje não entra** enquanto estiver em andamento. Só dia encerrado
   (no fuso da pessoa) vira estatística. Sem isso, às 10h da manhã a pessoa
   "comeu 300 kcal" e o coach concluía que ela está num déficit gigante.

2. **Dia com registro pela metade não é ingestão real.** 400 kcal registradas
   num dia de meta 2.400 quase nunca significam "comi 400 kcal" — significam
   "esqueci de registrar". O sistema pergunta em vez de assumir.

O critério automático é um PONTO DE PARTIDA, nunca a palavra final: a marcação
manual do usuário (models/day_quality.py) sempre vence, e a classificação
também olha o número de refeições, não só a porcentagem de calorias.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.usertime import local_date, today_local
from app.models.calorie_goal import CalorieGoal
from app.models.day_quality import DayMarkStatus, NutritionDayMark
from app.models.meal import MealLog

# Faixas da spec §10.3, sobre o % da meta calórica que foi registrado.
PCT_PROVAVELMENTE_INCOMPLETO = 0.50
PCT_PEDIR_CONFIRMACAO = 0.75

# Um dia com poucas refeições registradas é suspeito mesmo batendo a meta em
# kcal (um "almoço" de 2.000 kcal costuma ser o dia inteiro lançado de uma vez).
MIN_REFEICOES_ESPERADAS = 2


@dataclass
class DayNutrition:
    """Um dia de calendário da pessoa, com o que foi registrado e o veredito
    sobre poder ou não entrar nas médias."""

    day: date
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    meals: int
    # "completo" | "confirmar" | "provavelmente_incompleto"
    quality: str
    # Marcação manual do usuário, quando existe.
    mark: DayMarkStatus | None
    # Fecha a conta: este dia pode alimentar as médias nutricionais?
    valid_for_average: bool
    # Precisa de uma decisão da pessoa (é o que a UI mostra como pendência).
    needs_attention: bool

    @property
    def logged(self) -> bool:
        return self.meals > 0


def classify(kcal: float, goal_kcal: float | None, meals: int) -> str:
    """Critério inicial de completude. Sem meta definida não dá pra falar em
    porcentagem — aí só o número de refeições sustenta o palpite."""
    if meals == 0:
        return "provavelmente_incompleto"
    if goal_kcal is None or goal_kcal <= 0:
        return "completo" if meals >= MIN_REFEICOES_ESPERADAS else "confirmar"

    pct = kcal / goal_kcal
    if pct < PCT_PROVAVELMENTE_INCOMPLETO:
        return "provavelmente_incompleto"
    if pct < PCT_PEDIR_CONFIRMACAO:
        return "confirmar"
    # Acima de 75% da meta: potencialmente válido — mas uma única refeição
    # cobrindo o dia inteiro ainda merece uma conferida.
    return "completo" if meals >= MIN_REFEICOES_ESPERADAS else "confirmar"


def _goal_kcal(db: Session, user_id: int) -> float | None:
    goal = db.execute(
        select(CalorieGoal)
        .where(CalorieGoal.user_id == user_id)
        .order_by(CalorieGoal.created_at.desc(), CalorieGoal.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    return goal.kcal if goal else None


def nutrition_days(
    db: Session,
    user_id: int,
    tz: ZoneInfo,
    since,
    *,
    include_today: bool = False,
) -> list[DayNutrition]:
    """Os dias alimentares da pessoa desde `since` (datetime UTC), agrupados
    pelo dia de CALENDÁRIO dela e já classificados.

    `include_today=False` (padrão) é a regra §10.1: o dia em andamento fica de
    fora de tudo que for cálculo histórico. A tela do diário usa True porque
    ali a pessoa quer ver o dia dela acontecendo.
    """
    meals = db.execute(
        select(MealLog)
        .options(selectinload(MealLog.items))
        .where(MealLog.user_id == user_id, MealLog.logged_at >= since)
    ).scalars()

    hoje = today_local(tz)
    kcal: dict[date, float] = defaultdict(float)
    prot: dict[date, float] = defaultdict(float)
    carb: dict[date, float] = defaultdict(float)
    fat: dict[date, float] = defaultdict(float)
    refeicoes: dict[date, int] = defaultdict(int)

    for meal in meals:
        d = local_date(meal.logged_at, tz)
        if not include_today and d >= hoje:
            continue
        kcal[d] += sum(i.kcal for i in meal.items)
        prot[d] += sum(i.protein_g for i in meal.items)
        carb[d] += sum(i.carbs_g for i in meal.items)
        fat[d] += sum(i.fat_g for i in meal.items)
        refeicoes[d] += 1

    if not kcal:
        return []

    marks = {
        m.day: m.status
        for m in db.execute(
            select(NutritionDayMark).where(
                NutritionDayMark.user_id == user_id, NutritionDayMark.day.in_(list(kcal.keys()))
            )
        ).scalars()
    }
    goal = _goal_kcal(db, user_id)

    dias: list[DayNutrition] = []
    for d in sorted(kcal):
        qualidade = classify(kcal[d], goal, refeicoes[d])
        mark = marks.get(d)
        em_andamento = d >= hoje

        if mark is DayMarkStatus.CONFIRMED:
            valido, atencao = True, False
        elif mark is DayMarkStatus.INCOMPLETE:
            valido, atencao = False, False
        else:
            # Sem decisão da pessoa: "completo" entra; o resto fica pendente e
            # fora das médias até ela resolver. Dia em andamento nunca é
            # pendência — ele ainda vai ser preenchido.
            valido = qualidade == "completo"
            atencao = qualidade != "completo" and not em_andamento

        dias.append(
            DayNutrition(
                day=d,
                kcal=round(kcal[d], 1),
                protein_g=round(prot[d], 1),
                carbs_g=round(carb[d], 1),
                fat_g=round(fat[d], 1),
                meals=refeicoes[d],
                quality=qualidade,
                mark=mark,
                # Um dia em andamento nunca alimenta média (§10.1).
                valid_for_average=valido and not em_andamento,
                needs_attention=atencao,
            )
        )
    return dias


def set_mark(db: Session, user_id: int, day: date, status: DayMarkStatus | None) -> None:
    """Grava (ou remove) a decisão do usuário sobre um dia. `status=None`
    apaga a marcação e devolve o dia à classificação automática."""
    existing = db.execute(
        select(NutritionDayMark).where(
            NutritionDayMark.user_id == user_id, NutritionDayMark.day == day
        )
    ).scalar_one_or_none()

    if status is None:
        if existing is not None:
            db.delete(existing)
        return

    if existing is None:
        db.add(NutritionDayMark(user_id=user_id, day=day, status=status))
    else:
        existing.status = status
