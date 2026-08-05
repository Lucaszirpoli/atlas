import enum
from datetime import datetime

from sqlalchemy import ARRAY, JSON, Boolean, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class GoalPace(str, enum.Enum):
    """Ritmo do objetivo — escala o déficit/superávit. 'normal' é o recomendado."""

    SLOW = "slow"      # mais devagar, preserva mais músculo, leva mais tempo
    NORMAL = "normal"  # o equilíbrio recomendado pelo coaching
    FAST = "fast"      # mais rápido, mais risco, mais difícil de sustentar


class BiologicalSex(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"


class ActivityLevel(str, enum.Enum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class Goal(str, enum.Enum):
    EMAGRECIMENTO = "emagrecimento"
    HIPERTROFIA = "hipertrofia"
    MANUTENCAO = "manutencao"
    PERFORMANCE = "performance"
    RECOMPOSICAO = "recomposicao"


class ExperienceLevel(str, enum.Enum):
    INICIANTE = "iniciante"
    INTERMEDIARIO = "intermediario"
    AVANCADO = "avancado"


class TrainingLocation(str, enum.Enum):
    ACADEMIA_COMPLETA = "academia_completa"
    ACADEMIA_BASICA = "academia_basica"
    CASA_COM_EQUIPAMENTO = "casa_com_equipamento"
    CASA_SEM_EQUIPAMENTO = "casa_sem_equipamento"


class TrainingStylePreference(str, enum.Enum):
    CURTO_INTENSO = "curto_intenso"
    LONGO_VOLUMOSO = "longo_volumoso"
    IA_DECIDE = "ia_decide"


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )

    biological_sex: Mapped[BiologicalSex] = mapped_column(
        Enum(BiologicalSex, name="biological_sex")
    )
    age: Mapped[int]
    height_cm: Mapped[float]
    activity_level: Mapped[ActivityLevel] = mapped_column(
        Enum(ActivityLevel, name="activity_level")
    )
    goal: Mapped[Goal] = mapped_column(Enum(Goal, name="goal"))
    # Ritmo do objetivo (devagar/normal/rápido) e peso-alvo (opcional). O ritmo
    # escala o déficit/superávit; o alvo dá a estimativa de tempo. Colunas novas
    # -> ensure_columns no init_db (ALTER cedo), não quebra banco antigo.
    goal_pace: Mapped[GoalPace] = mapped_column(
        Enum(GoalPace, name="goal_pace", native_enum=False),
        default=GoalPace.NORMAL, server_default="NORMAL",
    )
    target_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        Enum(ExperienceLevel, name="experience_level")
    )
    training_location: Mapped[TrainingLocation] = mapped_column(
        Enum(TrainingLocation, name="training_location")
    )
    training_style_preference: Mapped[TrainingStylePreference] = mapped_column(
        Enum(TrainingStylePreference, name="training_style_preference"),
        default=TrainingStylePreference.IA_DECIDE,
    )

    available_days: Mapped[list[str]] = mapped_column(
        ARRAY(String(10)).with_variant(JSON(), "sqlite"), default=list
    )
    dietary_restrictions: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)).with_variant(JSON(), "sqlite"), default=list
    )
    injuries_limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    preferred_advanced_technique: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    # A pessoa aceita que o coach use TÉCNICA AVANÇADA (myo-reps, rest-pause,
    # muscle round, drop-set) ou só série normal? Nulo = nunca respondeu; aí
    # vale a regra de segurança de training_brain.advanced_allowed, que nega
    # pra iniciante. Quem treina há pouco tempo precisa de técnica de execução
    # e constância, não de intensificação — e a fadiga extra atrapalha mais do
    # que ajuda nessa fase.
    allow_advanced_techniques: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )

    # Preferências de exercício marcadas no questionário (máquinas x peso livre,
    # evitar agachamento livre / acima da cabeça / impacto, gostar de
    # unilateral). Ver training_brain.EXERCISE_PREFS — cada valor muda a escolha
    # de exercícios no montador. Antes isto era um texto livre que nada lia.
    exercise_prefs: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)).with_variant(JSON(), "sqlite"), default=list
    )
    # O que não coube nas opções acima. Não muda o motor (nada determinístico
    # dá pra extrair de texto livre), mas entra no contexto do coach de IA.
    exercise_preferences_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Os demais campos abertos do questionário — guardados pra que o coach de IA
    # os veja. Antes disparavam a remontagem do plano e eram descartados.
    training_history: Mapped[str | None] = mapped_column(Text, nullable=True)
    food_dislikes: Mapped[str | None] = mapped_column(Text, nullable=True)
    medications: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    strong_points: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)).with_variant(JSON(), "sqlite"), default=list
    )

    # --- Preferências de treino do Coaching (o "cérebro de treino") ----------
    # Como o coach monta/ajusta o treino da pessoa. Todas OPCIONAIS: sem escolha,
    # o coach usa padrões seguros. Colunas novas -> ensure_columns no init_db
    # (ALTER cedo, antes de qualquer select), senão banco antigo quebra o boot.
    # Guardadas como texto simples (valores validados no service) pra evitar as
    # complicações de tipo enum no ALTER — mesma lição do goal_pace.
    weak_point: Mapped[str | None] = mapped_column(String(20), nullable=True)  # LEGADO: 1 grupo | None
    # Pontos fracos a priorizar nos acessórios — até 2 grupos. Substitui o
    # weak_point singular (mantido só como fallback de leitura pra perfis antigos).
    weak_points: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)).with_variant(JSON(), "sqlite"), default=list
    )
    # QUANDO esta lista de pontos fracos passou a valer — o relógio do bloco de
    # especialização.
    #
    # Priorizar um músculo custa: os outros descem pro piso da faixa e ficam em
    # manutenção (volume_landmarks.weekly_plan). Isso é certo por 4 a 8 semanas e
    # errado pra sempre, e "ponto fraco" é uma resposta de questionário — fica
    # marcada até a pessoa trocar. Sem esta data, quem marcasse braço e
    # esquecesse passaria um ano com o resto do corpo parado, sem nunca ligar uma
    # coisa à outra. Com ela, o coach cobra a revisão no prazo.
    #
    # None = sem especialização em curso (nenhum ponto fraco marcado).
    weak_points_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session_length: Mapped[str | None] = mapped_column(String(10), nullable=True)  # curto|medio|longo
    wants_cardio: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None = não escolheu
    periodization: Mapped[str] = mapped_column(
        String(12), default="auto", server_default="auto"
    )  # auto|linear|ondulatoria
    # Dias por semana que a pessoa PODE treinar (2–7). None = automático (o coach
    # infere dos dias do onboarding). É o que define quantos treinos o coach monta.
    training_days_per_week: Mapped[int | None] = mapped_column(nullable=True)

    # --- RESPOSTAS ESTRUTURADAS DO QUESTIONÁRIO ------------------------------
    # Substituem os campos de TEXTO LIVRE que existiam antes (histórico de
    # treino, lesões, preferências, alimentos, medicamentos, observações). Eles
    # eram gravados e nenhuma regra os lia: quem escrevia "dor no ombro direito
    # em supino" via o coach montar supino do mesmo jeito. As colunas abaixo o
    # motor CONSEGUE obedecer — cada uma tem um consumidor determinístico.
    #
    # Todas nulas por padrão: perfil que nunca respondeu mantém o comportamento
    # anterior. Colunas novas -> ensure_columns no init_db (ALTER cedo).

    # Tempo de treino consistente. É daqui que sai o experience_level, no lugar
    # da auto-avaliação (ver training_brain.experience_from_training_time).
    training_time: Mapped[str | None] = mapped_column(String(12), nullable=True)
    # Consegue estimar repetições em reserva? Regula o RIR-alvo e libera (ou não)
    # técnica que depende de precisão perto da falha.
    rir_accuracy: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Lesão e dor, estruturadas por REGIÃO — o que permite filtrar exercício de
    # verdade. `medical_clearance` é o portão de segurança: lesão sem liberação
    # profissional faz o coach trabalhar conservador naquela região.
    has_injury: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    injury_regions: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)).with_variant(JSON(), "sqlite"), default=list
    )
    medical_clearance: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_pain: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    pain_regions: Mapped[list[str]] = mapped_column(
        ARRAY(String(16)).with_variant(JSON(), "sqlite"), default=list
    )
    pain_intensity: Mapped[str | None] = mapped_column(String(12), nullable=True)
    limitations: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)).with_variant(JSON(), "sqlite"), default=list
    )

    # Contexto do lugar. Academia cheia desliga superset (não dá pra segurar duas
    # estações); equipamento de casa define o que existe pra escolher.
    gym_crowding: Mapped[str | None] = mapped_column(String(10), nullable=True)
    home_equipment: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)).with_variant(JSON(), "sqlite"), default=list
    )

    # Estilo de treino. `split_preference` só oferece divisões com frequência
    # ≥2×/semana por grupo — bro-split não está na lista (regra 6 do produto).
    split_preference: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # "Pode colocar exercícios de superior e inferior no mesmo treino?" —
    # pergunta direta que falta em `split_preference` sozinho: alguém com
    # braço/panturrilha como ponto fraco podia cair no split Torso/Limbs
    # (methods.TORSO_LIMBS_SPLIT), cujo dia "membros" MISTURA perna com braço
    # de propósito, sem que a pessoa tivesse como recusar isso sem saber o
    # nome técnico da divisão. False bloqueia full_body E o Torso/Limbs;
    # None (padrão) deixa o coach decidir como hoje.
    avoid_mixing_upper_lower: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    load_preference: Mapped[str | None] = mapped_column(String(12), nullable=True)
    failure_comfort: Mapped[str | None] = mapped_column(String(12), nullable=True)

    # Recuperação. As quatro entram JUNTAS num único fator que desloca o volume
    # semanal (training_brain.recovery_factor) — separadas não decidiriam nada.
    sleep_quality: Mapped[str | None] = mapped_column(String(8), nullable=True)
    stress_level: Mapped[str | None] = mapped_column(String(8), nullable=True)
    recovery_between: Mapped[str | None] = mapped_column(String(12), nullable=True)
    other_sport: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Alimentos que a pessoa não come, agora como lista de opções — o gerador de
    # dieta consegue excluir uma lista; não conseguia ler o texto livre.
    food_dislikes_list: Mapped[list[str]] = mapped_column(
        ARRAY(String(30)).with_variant(JSON(), "sqlite"), default=list
    )

    # Fuso IANA do aparelho ("America/Sao_Paulo"). É o que define QUE DIA é cada
    # registro pra esta pessoa — sem isso o backend fatiava o dia em UTC e tudo
    # que ela registrava depois das 21h caía no dia seguinte. O app manda o fuso
    # do aparelho ao entrar; None = usa o padrão (ver core/usertime.py).
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)

    trains_with_partner: Mapped[bool] = mapped_column(default=False)
    partner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(
        back_populates="profile", foreign_keys=[user_id]
    )
