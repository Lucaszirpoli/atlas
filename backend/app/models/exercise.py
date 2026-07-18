import enum
from datetime import datetime

from sqlalchemy import ARRAY, JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, event, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MuscleGroup(str, enum.Enum):
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    QUADS = "quads"
    HAMSTRINGS = "hamstrings"
    GLUTES = "glutes"
    CALVES = "calves"
    ABS = "abs"
    FOREARMS = "forearms"
    TRAPS = "traps"
    FULL_BODY = "full_body"
    CARDIO = "cardio"


class Equipment(str, enum.Enum):
    BARBELL = "barbell"
    DUMBBELL = "dumbbell"
    MACHINE = "machine"
    CABLE = "cable"
    BODYWEIGHT = "bodyweight"
    KETTLEBELL = "kettlebell"
    BAND = "band"
    SMITH_MACHINE = "smith_machine"
    OTHER = "other"


class Difficulty(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ExerciseCategory(str, enum.Enum):
    """Que TIPO de movimento é — vem do campo `category` do free-exercise-db.

    Existe por um motivo concreto: sem isso, "All Fours Quad Stretch" (um
    ALONGAMENTO) era importado indistinguível de um agachamento e a engine o
    escolhia como exercício de perna. Um terço da base importada (292 de 873)
    não é musculação: 123 alongamentos, 61 pliometrias, 21 strongman, 14 cardio.
    """

    STRENGTH = "strength"
    POWERLIFTING = "powerlifting"
    OLYMPIC = "olympic_weightlifting"
    STRONGMAN = "strongman"
    PLYOMETRICS = "plyometrics"
    STRETCHING = "stretching"
    CARDIO = "cardio"


# Categorias que podem virar exercício de uma rotina de musculação. Alongamento
# e cardio NUNCA entram (não são séries de treino); pliometria/strongman/olímpico
# entram só quando o método pede (ver STRENGTH_CATEGORIES abaixo).
STRENGTH_CATEGORIES: tuple[ExerciseCategory, ...] = (
    ExerciseCategory.STRENGTH,
    ExerciseCategory.POWERLIFTING,
)

# Pool ampliado: métodos como Westside usam trenó/farmer's walk (strongman) e
# saltos (pliometria) de propósito, e 5/3/1 usa levantamentos olímpicos.
EXTENDED_STRENGTH_CATEGORIES: tuple[ExerciseCategory, ...] = STRENGTH_CATEGORIES + (
    ExerciseCategory.OLYMPIC,
    ExerciseCategory.STRONGMAN,
    ExerciseCategory.PLYOMETRICS,
)


class Exercise(Base):
    """Biblioteca de exercícios. is_custom=True para exercícios criados por
    um usuário (com vídeo/gif próprio opcional)."""

    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    # Nome original em inglês da fonte (ExerciseDB). Guardado pra casar importação
    # do Hevy/Strong (que vêm em inglês) inglês-com-inglês — muito mais preciso
    # que traduzir e comparar com o nome PT. Null nos exercícios curados antigos.
    name_en: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    # Id externo na ExerciseDB ("0001"). Chave de idempotência do seed: reimportar
    # atualiza a linha em vez de duplicar. Null em quem não veio da ExerciseDB.
    source_external_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    # Escondido da busca/picker/engine sem apagar (apagar quebraria rotinas e
    # histórico que referenciam o id por FK). Usado pra aposentar a base antiga
    # do free-exercise-db quando a ExerciseDB entra.
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    primary_muscle_group: Mapped[MuscleGroup] = mapped_column(
        Enum(MuscleGroup, name="muscle_group")
    )
    secondary_muscle_groups: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)).with_variant(JSON(), "sqlite"), default=list
    )
    equipment: Mapped[Equipment] = mapped_column(Enum(Equipment, name="equipment"))
    difficulty: Mapped[Difficulty] = mapped_column(Enum(Difficulty, name="difficulty"))
    execution_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Tipo do movimento (musculação / alongamento / cardio / ...). Sem isso a
    # engine e a IA escolhiam alongamento como exercício de treino.
    category: Mapped[ExerciseCategory] = mapped_column(
        Enum(ExerciseCategory, name="exercise_category"),
        default=ExerciseCategory.STRENGTH,
        # .name, não .value: o Enum do SQLAlchemy persiste o NOME do membro
        # (as outras colunas guardam 'CHEST', 'BARBELL'), e um default com o
        # value minúsculo faz a leitura estourar LookupError.
        server_default=ExerciseCategory.STRENGTH.name,
        index=True,
    )

    # Composto (multiarticular) vs isolado — base da proporção intra-sessão
    # dos métodos (Kuba 40/60 etc.). Preenchido pelos listeners abaixo.
    is_compound: Mapped[bool] = mapped_column(Boolean, default=True)

    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def quality_order():
    """Ordena exercícios do MAIS CONSAGRADO pro mais obscuro — pra a engine dos
    métodos e a IA escolherem os básicos da ciência (supino, agachamento,
    remada, rosca) em vez de variações esquisitas (arranco unilateral, mergulho
    assistido, agachamento frankenstein) que só vinham na frente por terem id
    baixo na ExerciseDB (a base começa em '3/4 sit-up', 'assisted...', 'band...').

    Devolve uma lista de cláusulas pra `.order_by(*quality_order())`. Ascendente:
    o menor valor vem primeiro.
    """
    from sqlalchemy import case, func

    # 1) tem GIF vem antes (None -> True=1 fica por último).
    tem_gif = Exercise.video_url.is_(None)
    # 2) variações obscuras/avançadas pro fim: "assistida" (regressão pra quem
    #    não consegue o movimento), levantamentos olímpicos usados como acessório
    #    (clean/arranco/snatch), "complex", ângulos de câmera.
    en = func.lower(func.coalesce(Exercise.name_en, ""))
    obscuro = case(
        (en.like("%assist%"), 4),
        (en.like("%pov%"), 4),
        (en.like("%clean%"), 3),
        (en.like("%snatch%"), 3),
        (en.like("%complex%"), 3),
        (en.like("%bosu%"), 3),
        (en.like("%sled%"), 2),
        (en.like("%frankenstein%"), 2),
        else_=0,
    )
    # 2b) nome PT que COMEÇA com o equipamento ("Com barra skier", "Na máquina
    #     ...") = o tradutor não reconheceu o movimento -> nome torto e exercício
    #     geralmente obscuro. Empurra pro fim, atrás dos nomes limpos ("Supino").
    pt = func.lower(Exercise.name)
    nome_torto = case(
        (pt.like("com %"), 1),
        (pt.like("na %"), 1),
        (pt.like("no %"), 1),
        (pt.like("de %"), 1),
        else_=0,
    )
    # 3) equipamento consagrado primeiro (barra/halter/máquina/cabo), faixa/etc. no fim.
    equip = case(
        (Exercise.equipment == Equipment.BARBELL, 0),
        (Exercise.equipment == Equipment.DUMBBELL, 1),
        (Exercise.equipment == Equipment.MACHINE, 2),
        (Exercise.equipment == Equipment.CABLE, 3),
        (Exercise.equipment == Equipment.SMITH_MACHINE, 4),
        (Exercise.equipment == Equipment.BODYWEIGHT, 5),
        else_=7,
    )
    # 4) nome mais curto = movimento-base ("Supino com barra" < "Elevação frontal
    #    pullover com barra"). 5) desempate estável por id.
    return [tem_gif, obscuro, nome_torto, equip, func.length(Exercise.name), Exercise.id]


@event.listens_for(Exercise, "before_insert")
@event.listens_for(Exercise, "before_update")
def _populate_is_compound(_mapper, _connection, target: "Exercise") -> None:
    from app.services.exercise_classify import classify_is_compound

    target.is_compound = classify_is_compound(
        target.name, target.secondary_muscle_groups, target.equipment
    )
