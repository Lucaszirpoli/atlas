"""O que o coach APRENDEU sobre esta pessoa — o modelo do usuário.

O questionário diz quem a pessoa ACHA que é; isto diz quem ela TEM SIDO. São os
traços que só aparecem com o tempo: se ela é constante ou some nos fins de
semana, se registra a dieta todo dia ou só nos dias bons, se termina os treinos
que começa, se abandona o treino no meio. Nada é inventado — todo traço sai de
um contador do próprio histórico, com a evidência do lado.

Quanto mais tempo de app, mais forte fica: `confianca` cresce com a quantidade
de dias observados, e um traço só aparece com base suficiente. É o oposto de
chutar no primeiro dia — no começo o coach admite que ainda não conhece a
pessoa, e vai afirmando mais conforme aprende.

Determinístico, como o resto do coach: o mesmo histórico dá sempre o mesmo
retrato. A IA (Pro) só verbaliza isto — não inventa traço nenhum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.meal import MealLog
from app.models.sleep_log import SleepLog
from app.models.user_profile import UserProfile
from app.models.weight_log import WeightLog
from app.models.workout_session import WorkoutSession

# Dias observados a partir dos quais o retrato deixa de ser chute.
_MIN_DIAS_BAIXA = 7
_MIN_DIAS_MEDIA = 28
_MIN_DIAS_ALTA = 84

# Janela de observação dos hábitos. 90 dias pega a sazonalidade do mês sem
# deixar um comportamento de meio ano atrás pesar no retrato de hoje.
_JANELA_DIAS = 90


@dataclass
class Traco:
    """Uma coisa aprendida. `evidencia` é o número que sustenta a afirmação —
    o coach nunca diz um traço sem poder mostrar de onde ele saiu."""

    chave: str
    texto: str
    evidencia: str


@dataclass
class RetratoDoUsuario:
    dias_observados: int
    confianca: str  # "nenhuma" | "baixa" | "media" | "alta"
    tracos: list[Traco] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "dias_observados": self.dias_observados,
            "confianca": self.confianca,
            "tracos": [{"chave": t.chave, "texto": t.texto, "evidencia": t.evidencia} for t in self.tracos],
        }

    def prompt_lines(self) -> list[str]:
        """Como isto entra no contexto do coach de IA."""
        if self.confianca == "nenhuma":
            return [
                "O QUE EU JÁ SEI SOBRE ESTA PESSOA: quase nada ainda — ela tem pouco tempo de app. "
                "Não afirme padrões de comportamento; pergunte em vez de supor."
            ]
        linhas = [
            f"O QUE EU APRENDI SOBRE ESTA PESSOA (observando {self.dias_observados} dias, "
            f"confiança {self.confianca}):"
        ]
        linhas += [f"- {t.texto} ({t.evidencia})" for t in self.tracos]
        linhas.append(
            "Use isto pra falar com ela como quem a conhece: reconheça o que ela já faz bem e "
            "ataque o ponto onde ela realmente trava. NUNCA use como cobrança ou culpa."
        )
        return linhas


def _confianca(dias: int) -> str:
    if dias >= _MIN_DIAS_ALTA:
        return "alta"
    if dias >= _MIN_DIAS_MEDIA:
        return "media"
    if dias >= _MIN_DIAS_BAIXA:
        return "baixa"
    return "nenhuma"


def _dias_distintos(db: Session, model, user_col, data_col, user_id: int, desde: datetime) -> set:
    linhas = db.execute(
        select(data_col).where(user_col == user_id, data_col >= desde)
    ).scalars()
    return {d.date() for d in linhas if d is not None}


def aprender(db: Session, user_id: int, now: datetime | None = None) -> RetratoDoUsuario:
    """Lê o histórico e devolve o retrato. Barato: são contagens por dia, nada
    de varrer registro a registro."""
    now = now or datetime.now(timezone.utc)

    perfil = db.execute(select(UserProfile).where(UserProfile.user_id == user_id)).scalar_one_or_none()
    inicio = getattr(perfil, "created_at", None)
    if inicio is not None and inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    dias_de_casa = (now - inicio).days if inicio else 0
    dias_observados = max(0, min(dias_de_casa, _JANELA_DIAS))

    retrato = RetratoDoUsuario(dias_observados=dias_observados, confianca=_confianca(dias_observados))
    if retrato.confianca == "nenhuma":
        return retrato

    # A janela de CONTAGEM é a mesma do denominador. Contar 90 dias de registro
    # e dividir por 22 dias de casa dava "44 de 22 dias registrados" — número
    # impossível, e o coach afirmaria em cima dele.
    janela = max(dias_observados, 1)
    semanas = max(janela / 7, 1)
    desde = now - timedelta(days=janela)

    dias_treino = _dias_distintos(db, WorkoutSession, WorkoutSession.user_id, WorkoutSession.started_at, user_id, desde)
    dias_dieta = _dias_distintos(db, MealLog, MealLog.user_id, MealLog.logged_at, user_id, desde)
    dias_peso = _dias_distintos(db, WeightLog, WeightLog.user_id, WeightLog.recorded_at, user_id, desde)
    dias_sono = _dias_distintos(db, SleepLog, SleepLog.user_id, SleepLog.wake_at, user_id, desde)

    # --- Constância de treino ------------------------------------------------
    por_semana = len(dias_treino) / semanas
    if por_semana >= 3.5:
        retrato.tracos.append(Traco(
            "treino_constante",
            "Treina com regularidade alta — constância não é o problema dela.",
            f"{por_semana:.1f} treinos/semana em {janela} dias",
        ))
    elif por_semana >= 1.5:
        retrato.tracos.append(Traco(
            "treino_irregular",
            "Treina, mas com frequência irregular — some e volta.",
            f"{por_semana:.1f} treinos/semana em {janela} dias",
        ))
    elif len(dias_treino) > 0:
        retrato.tracos.append(Traco(
            "treino_raro",
            "Treina pouco. O gargalho dela é começar, não o programa.",
            f"{len(dias_treino)} treinos em {janela} dias",
        ))

    # --- Constância de registro da dieta -------------------------------------
    taxa_dieta = len(dias_dieta) / janela
    if taxa_dieta >= 0.7:
        retrato.tracos.append(Traco(
            "dieta_disciplinada",
            "Registra a dieta quase todo dia — dá pra confiar nos números dela.",
            f"{len(dias_dieta)} de {janela} dias registrados",
        ))
    elif taxa_dieta >= 0.3:
        retrato.tracos.append(Traco(
            "dieta_parcial",
            "Registra a dieta de forma intermitente; as médias dela são otimistas.",
            f"{len(dias_dieta)} de {janela} dias registrados",
        ))
    elif len(dias_dieta) > 0:
        retrato.tracos.append(Traco(
            "dieta_esporadica",
            "Quase não registra a dieta — evite conclusões fortes de caloria com ela.",
            f"{len(dias_dieta)} de {janela} dias registrados",
        ))

    # --- Treino abandonado no meio -------------------------------------------
    total_sessoes = db.execute(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.user_id == user_id, WorkoutSession.started_at >= desde
        )
    ).scalar() or 0
    concluidas = db.execute(
        select(func.count(WorkoutSession.id)).where(
            WorkoutSession.user_id == user_id,
            WorkoutSession.started_at >= desde,
            WorkoutSession.completed_at.is_not(None),
        )
    ).scalar() or 0
    if total_sessoes >= 5:
        taxa = concluidas / total_sessoes
        if taxa >= 0.9:
            retrato.tracos.append(Traco(
                "termina_o_que_comeca",
                "Termina praticamente todo treino que começa.",
                f"{concluidas} de {total_sessoes} sessões concluídas",
            ))
        elif taxa < 0.6:
            retrato.tracos.append(Traco(
                "abandona_treino",
                "Costuma abandonar o treino no meio — o treino pode estar longo demais pra rotina dela.",
                f"só {concluidas} de {total_sessoes} sessões concluídas",
            ))

    # --- O que ela acompanha e o que ignora ----------------------------------
    if len(dias_peso) / semanas >= 1.5:
        retrato.tracos.append(Traco(
            "pesa_com_frequencia",
            "Se pesa com frequência — a tendência de peso dela é confiável.",
            f"{len(dias_peso)} pesagens em {janela} dias",
        ))
    elif len(dias_peso) <= 2 and janela >= _MIN_DIAS_MEDIA:
        retrato.tracos.append(Traco(
            "quase_nao_pesa",
            "Quase não registra peso — sem isso eu fico sem a régua principal do objetivo dela.",
            f"{len(dias_peso)} pesagens em {janela} dias",
        ))
    if len(dias_sono) == 0 and janela >= _MIN_DIAS_MEDIA:
        retrato.tracos.append(Traco(
            "ignora_sono",
            "Nunca registrou sono — não cobre isso, só ofereça quando fizer diferença.",
            f"0 noites em {janela} dias",
        ))

    return retrato
