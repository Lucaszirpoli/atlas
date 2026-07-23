"""Base de conhecimento ESTRUTURADA das 10 metodologias de treino da Arvo.

Este módulo é o coração da fidelidade da IA de treino (Fase 4). Em vez de
pedir pro modelo "seguir o método" em texto livre — onde ele sempre acaba
improvisando —, cada método vira PARÂMETROS DE MÁQUINA aqui. O montador
determinístico (methods_engine) usa estes números para construir o esqueleto
do treino (frequência, split, séries, reps, cadência, descanso, proporção
isolado/composto, ordem, proibições) e uma validação rejeita qualquer plano
que os viole. A IA só escolhe o exercício específico de cada vaga e escreve
as dicas — sempre dentro destes trilhos.

Fonte ÚNICA e exclusiva: o relatório analítico da Arvo em
`app/data/arvo_methods_report.txt` (arvo.guru/pt-BR/resources/methods). Nada
aqui deve vir de conhecimento externo — se o guia não especifica, o campo fica
`None` e o motor usa um padrão conservador explicitamente marcado, nunca uma
invenção apresentada como se fosse do método.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Experience(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ProgressionFamily(str, Enum):
    """As quatro famílias de progressão do relatório (regra transversal)."""

    LOAD_OR_REPS = "load_or_reps"  # DC, Mentzer: + reps/carga; correção = mais descanso
    VOLUME_LANDMARKS = "volume_landmarks"  # Kuba, RP: + sets/reps por RIR e landmarks
    DENSITY_QUALITY = "density_quality"  # FST-7, Y3T, Mountain Dog: densidade/pump/técnica
    TM_AMRAP = "tm_amrap"  # 5/3/1, Juggernaut, Westside: TM, AMRAP, percentuais


@dataclass(frozen=True)
class Phase:
    """Uma fase dentro de uma SESSÃO (Mountain Dog) ou de uma SEMANA/ciclo
    (Y3T, FST-7). Carrega os parâmetros que valem só naquela fase."""

    name: str
    reps: str  # faixa, ex "8-12" ou "15-30+"
    sets: str  # ex "2-3" ou "7"
    rir: str | None = None
    tempo: str | None = None  # cadência, ex "3-1-1-1"
    rest_seconds: str | None = None  # ex "30-45" ou "180-240"
    intensity_pct_1rm: str | None = None  # ex "70-85"
    note: str | None = None


@dataclass(frozen=True)
class MethodSpec:
    key: str
    name: str
    author: str
    goal: str
    experience_min: Experience
    progression_family: ProgressionFamily

    # Frequência / agenda -----------------------------------------------------
    # dias por semana suportados (o motor casa com a disponibilidade do user)
    days_per_week: tuple[int, ...] = ()
    # sugestões de agenda por nº de dias (fidelidade: Mentzer 2d = ter/sex)
    schedule_suggestions: dict[int, list[str]] = field(default_factory=dict)
    frequency_per_muscle: str | None = None  # ex "~2x/sem", "1x/sem", "a cada 4-5 dias"
    split_by_days: dict[int, list[str]] = field(default_factory=dict)

    # Parâmetros base da sessão (quando o método é uniforme; senão ver phases)
    sets_per_exercise: str | None = None
    reps: str | None = None
    tempo: str | None = None
    rest_seconds: str | None = None
    rir: str | None = None
    exercises_per_session: str | None = None

    # A REGRA MATEMÁTICA que a IA sempre errava: proporção dentro da sessão.
    # Fração de exercícios COMPOSTOS por sessão (o resto é isolamento). Aplicada
    # intra-treino, harmonicamente — nunca "tudo composto no dia 1".
    compound_ratio: float | None = None  # ex Kuba 0.40, Mentzer 0.90

    # Estrutura multifásica (por sessão OU por semana/ciclo)
    phase_scope: str | None = None  # "session" | "week" | None
    phases: tuple[Phase, ...] = ()

    # Ciclo / periodização ----------------------------------------------------
    mesocycle_weeks: str | None = None
    deload_rule: str | None = None
    progression_rule: str = ""

    # Regras de segurança / proibições (o motor bloqueia sugestões que violem)
    forbidden: tuple[str, ...] = ()  # descrições legíveis das proibições
    equipment_pref: str | None = None
    coaching_notes: tuple[str, ...] = ()

    # Quando um FOCO se repete na semana (ex.: "superior" duas vezes num split de
    # 4 dias), True mantém a MESMA seleção de exercício nas duas ocorrências —
    # correto pros métodos consagrados, cujo A/B é uma sessão fixa que se repete
    # de propósito (DC Training, Mentzer 2d). O plano do coach usa False: cada
    # ocorrência escolhe de novo (dentro do que ainda não foi usado na semana),
    # dando variação real de exercício — é o que evita "só uma remada curvada
    # no treino inteiro" quando dá pra variar pra remada na máquina no repeat.
    repeat_same_session: bool = True

    # Trecho-fonte do relatório (camada RAG: a IA cita daqui, nunca inventa)
    guide_excerpt: str = ""


# ---------------------------------------------------------------------------
# As 10 metodologias — números destilados fielmente do relatório da Arvo.
# ---------------------------------------------------------------------------

METHODS: dict[str, MethodSpec] = {}


def _reg(spec: MethodSpec) -> None:
    METHODS[spec.key] = spec


_reg(
    MethodSpec(
        key="dc_training",
        name="DC Training (Doggcrapp)",
        author="Dante Trudel",
        goal="Hipertrofia rápida com baixa frequência e altíssima intensidade.",
        experience_min=Experience.INTERMEDIATE,
        progression_family=ProgressionFamily.LOAD_OR_REPS,
        days_per_week=(3, 4),
        frequency_per_muscle="cada músculo ~a cada 4-5 dias (rotação A-descanso-B-descanso)",
        split_by_days={3: ["A", "B"], 4: ["A", "B"]},
        sets_per_exercise="1 série de trabalho (rest-pause)",
        reps="7-10 (rest-pause); quadríceps: widowmaker 20 reps @10-12RM",
        rest_seconds="10-15 respirações entre mini-séries do rest-pause",
        exercises_per_session="poucos; 1 série efetiva por exercício",
        mesocycle_weeks="blast 6-12 sem + cruise 10-14 dias",
        deload_rule="cruise de 10-14 dias após cada blast (obrigatório após blocos longos).",
        progression_rule=(
            "Bater o diário: mais reps totais no rest-pause ou mais carga a cada sessão. "
            "Se estagnar, trocar a variação do exercício e/ou entrar em cruise."
        ),
        forbidden=(
            "Não adicionar volume 'por fora' (séries extras) — o método é minimalista.",
            "Não fazer rest-pause sem registrar os números (o diário é a base da progressão).",
        ),
        equipment_pref="Barra, halteres, máquinas e estação segura para alongamento extremo (rack pulls, pullups com peso, presses, leg press).",
        coaching_notes=(
            "Mega-série rest-pause: carga de ~7-10RM, vai à falha, descansa 10-15 respirações, "
            "de novo à falha, descansa, terceira mini-série.",
            "Alongamento com carga de 60-90s após cada grupamento muscular.",
        ),
        guide_excerpt=(
            "O DC combina baixa frequência, rest-pause, alongamento extremo e progressão obrigatória em "
            "diário. Blast 6-12 semanas e cruise 10-14 dias. Núcleo: mega-série rest-pause (~7-10 reps à "
            "falha, 10-15 respirações, repete, terceira mini-série). Quadríceps: widowmaker 20 reps @10-12RM. "
            "Divisão A/B, 1 série de trabalho por exercício, alongamentos 60-90s, cada músculo ~a cada 4-5 dias."
        ),
    )
)

_reg(
    MethodSpec(
        key="mentzer_hit",
        name="Mentzer HIT (Heavy Duty)",
        author="Mike Mentzer",
        goal="Hipertrofia/força com volume mínimo e intensidade máxima (até e além da falha).",
        experience_min=Experience.INTERMEDIATE,
        progression_family=ProgressionFamily.LOAD_OR_REPS,
        days_per_week=(2, 3),
        # Fidelidade: 2 dias clássico = terça e sexta (máxima recuperação).
        schedule_suggestions={2: ["terça", "sexta"], 3: ["segunda", "quarta", "sexta"]},
        frequency_per_muscle="1 ataque semanal por músculo (recuperação de 4-7 dias)",
        split_by_days={
            3: ["peito/costas", "pernas", "ombros/braços"],
            2: ["full body A", "full body B"],
        },
        sets_per_exercise="1-2 séries all-out por exercício (NUNCA adicionar séries)",
        reps="6-10 (topo da faixa com forma rigorosa → subir carga)",
        tempo="4-0-2-0 (excêntrica de 4s, concêntrica forte)",
        exercises_per_session="3-5 exercícios principais por sessão",
        compound_ratio=0.90,  # ~90% compostos / 10% isolamento (pré-exaustão)
        mesocycle_weeks="6-8 sem de progressão + 1 sem totalmente off",
        deload_rule="1 semana inteira sem treino a cada 6-8 semanas.",
        progression_rule=(
            "Ao alcançar o topo da faixa com forma rigorosa, subir a carga 5-10%. "
            "Se NÃO superar o treino anterior, a correção é descansar mais — nunca adicionar séries."
        ),
        forbidden=(
            "Nunca adicionar séries para progredir (progressão é só carga/intensidade).",
            "Não interpretar estagnação como sinal para treinar mais — é sinal de mais descanso.",
        ),
        equipment_pref="Máquinas convergentes, leg press, puxadas, remadas; pareamentos seguros para além-falha (idealmente um parceiro para forçadas/negativas).",
        coaching_notes=(
            "Sessões curtas de 20-30 min.",
            "Técnicas: repetições forçadas, negativas de 8-10s a 105-110% de 1RM, sustentações estáticas seguras.",
            "~10% de isolamento serve para pré-exaustão antes do composto.",
        ),
        guide_excerpt=(
            "Heavy Duty: 1-2 séries 'all out' por exercício, até a falha e além. Sessões de 20-30 min, "
            "recuperação de 4-7 dias por músculo, progressão por carga/intensidade, NUNCA por adicionar "
            "séries. Tempo 4-0-2-0. Divisão clássica de 3 dias (um ataque por músculo/semana) ou full body "
            "de 2 dias para muito avançados. ~90% compostos e 10% isolamento para pré-exaustão. Ao alcançar "
            "o topo da faixa com forma rigorosa, subir 5-10%; se não superar, descansar mais. 1 semana off a "
            "cada 6-8 semanas."
        ),
    )
)

_reg(
    MethodSpec(
        key="kuba",
        name="Método Kuba",
        author="Kuba Cielen",
        goal="Hipertrofia focada em qualidade de repetição e volume controlado (MEV/MAV/MRV).",
        experience_min=Experience.BEGINNER,  # o FAQ do guia diz que serve inclusive para iniciantes
        progression_family=ProgressionFamily.VOLUME_LANDMARKS,
        days_per_week=(3, 4, 5),
        frequency_per_muscle="~2x/semana por músculo (rotação 3-on, 1-off)",
        sets_per_exercise="2 séries de trabalho (após 2-3 aquecimentos graduais)",
        reps="progressão 'reps primeiro, carga depois'",
        tempo="3-1-1-1 (obrigatória: 3s excêntrica, 1s embaixo, 1s concêntrica, 1s topo)",
        rir="0-1 nas séries de trabalho",
        compound_ratio=0.40,  # 40% compostos / 60% isolamentos — A REGRA 60/40
        phase_scope="week",
        phases=(
            Phase(name="Acumulação (sem 1-4)", reps="faixa alvo", sets="do MEV ao MAV", rir="2-3→1", tempo="3-1-1-1", note="Subir sets por músculo semana a semana."),
            Phase(name="Intensificação (sem 5-6)", reps="faixa alvo", sets="MAV/MRV", rir="0-1", tempo="3-1-1-1", note="Introduz myo-reps, drop sets, rest-pause."),
            Phase(name="Deload (sem 7)", reps="faixa alvo", sets="50% do volume", rir="3-4", tempo="3-1-1-1"),
        ),
        mesocycle_weeks="6 semanas + deload (semana 7)",
        deload_rule="Semana 7 com 50% do volume e RIR 3-4; ou quando sinais de fadiga coincidirem com proximidade do MRV.",
        progression_rule=(
            "Bater o topo da faixa de reps por duas sessões, então subir a carga. "
            "Repetições primeiro, carga depois."
        ),
        forbidden=(
            "Evitar exercícios de baixa relação estímulo-fadiga (terra pesado, agachamento pesado), especialmente nas semanas finais.",
            "Não correr a excêntrica — a cadência 3-1-1-1 é obrigatória.",
        ),
        equipment_pref="Máquinas, cabos e halteres de alta relação estímulo-fadiga (remada em máquina, extensora, crucifixo em cabo), com ênfase em posição alongada.",
        coaching_notes=(
            "Prioriza exercício em posição alongada.",
            "60% isolamentos / 40% compostos, aplicado DENTRO de cada sessão.",
        ),
        guide_excerpt=(
            "Kuba: hipertrofia por qualidade de repetição, MEV/MAV/MRV. 2 séries de trabalho por exercício, "
            "cadência obrigatória 3-1-1-1, RIR 0-1, mesociclo de 6 semanas + deload (sem 7 com 50% do volume, "
            "RIR 3-4). Progressão 'reps primeiro, carga depois'. 40% compostos e 60% isolamentos. Técnicas na "
            "intensificação: myo-reps, drop sets, rest-pause. ~2x/semana por músculo em rotação 3-on/1-off. "
            "Limita terra/agachamento pesados nas semanas finais."
        ),
    )
)

_reg(
    MethodSpec(
        key="fst7",
        name="FST-7 (Fascial Stretch Training)",
        author="Hany Rambod",
        goal="Pump, plenitude e detalhe muscular via finalizador de 7 séries.",
        experience_min=Experience.INTERMEDIATE,
        progression_family=ProgressionFamily.DENSITY_QUALITY,
        days_per_week=(5,),  # 5 dias clássico ou PPL
        split_by_days={5: ["peito", "costas", "pernas", "ombros", "braços"]},
        exercises_per_session="composto pesado + composto secundário + isolamento + finalizador FST-7",
        phase_scope="session",
        phases=(
            Phase(name="Composto pesado", reps="6-8", sets="3-4", note="Base de força/tensão."),
            Phase(name="Composto secundário", reps="8-12", sets="3"),
            Phase(name="Isolamento", reps="10-12", sets="2-3"),
            Phase(name="Finalizador FST-7", reps="8-12", sets="7", rest_seconds="30-45", note="Máquina ou cabo, NUNCA composto pesado. Água + pose/contração entre séries."),
        ),
        mesocycle_weeks="8 semanas (sem 1-4 constroem capacidade com 5-6 séries; sem 5-7 usam 7 séries; sem 8 remove FST-7)",
        deload_rule="Semana 8: remove o FST-7 e reduz volume e carga.",
        progression_rule=(
            "Semanas 1-4 começam com 5-6 séries no finalizador e sobem; semanas 5-7 usam as 7 séries com "
            "descansos mínimos e progressão agressiva. Manter 10-12 reps na série 1 e nunca cair bruscamente "
            "abaixo de 8 antes da série 7."
        ),
        forbidden=(
            "O finalizador FST-7 NUNCA em compostos pesados (agachamento/supino/terra) — só máquina ou cabo.",
            "Não pular a hidratação nem sair da estação entre as 7 séries.",
        ),
        equipment_pref="Máquinas e cabos para o finalizador (pec deck, crossover, extensora, flexora, remadas e curls em cabo). Cronômetro e garrafa de água na estação.",
        coaching_notes=(
            "Finalizador: 7 séries de 8-12 reps com apenas 30-45s de descanso.",
            "Entre séries do finalizador: beber água e posar/contrair o músculo.",
        ),
        guide_excerpt=(
            "FST-7: finalizador de 7 séries de 8-12 reps com 30-45s de descanso. Protocolo: composto pesado "
            "3-4×6-8; composto secundário 3×8-12; isolamento 2-3×10-12; finalizador FST-7 7×8-12. O "
            "finalizador deve ser em máquina ou cabo, NUNCA composto pesado. Água e pose entre séries. Sem "
            "1-4 constroem capacidade (5-6 séries); sem 5-7 usam 7 séries; sem 8 remove FST-7."
        ),
    )
)

_reg(
    MethodSpec(
        key="mountain_dog",
        name="Mountain Dog",
        author="John Meadows",
        goal="Hipertrofia multifásica e amigável às articulações.",
        experience_min=Experience.INTERMEDIATE,
        progression_family=ProgressionFamily.DENSITY_QUALITY,
        days_per_week=(4, 5),
        phase_scope="session",
        phases=(
            Phase(name="Fase 1 — Pré-ativação", reps="8-12", sets="2-3", rir="4", rest_seconds="45-60", intensity_pct_1rm="40-50", note="Fluxo sanguíneo e conexão mente-músculo. Não é aquecimento vazio."),
            Phase(name="Fase 2 — Explosivo", reps="3-6", sets="3-6", rir="2", rest_seconds="180-240", intensity_pct_1rm="70-85", note="Com correntes/bandas (resistência acomodativa). Movimento explosivo."),
            Phase(name="Fase 3 — Pump supramax", reps="8-15", sets="3-5", rir="0", rest_seconds="30-60", intensity_pct_1rm="50-70", note="0 RIR ou além. NUNCA bandas/correntes aqui (fadiga alta)."),
            Phase(name="Fase 4 — Alongamento com carga", reps="sustentação", sets="1-2", rest_seconds="30-60", note="Sustentações de 30-60s no alongamento com carga."),
        ),
        mesocycle_weeks="blocos com rotação de exercícios a cada 3-4 semanas",
        deload_rule="Semana de volume reduzido após 8-12 semanas ou quando a fase 2 perder velocidade e a fase 3 piorar a recuperação.",
        progression_rule="Progressão por densidade, carga/velocidade na fase 2 e qualidade do pump na fase 3; rotação de exercícios a cada 3-4 semanas.",
        forbidden=(
            "NUNCA usar bandas/correntes na fase 3 (pump supramax) — risco sob fadiga alta.",
            "Não tratar a fase 1 como aquecimento vazio nem 'moer' reps lentas na fase 2.",
        ),
        equipment_pref="Máquinas, cabos, banco, halteres, correntes e bandas (fundamentais na fase 2), e espaço seguro para alongamento com carga.",
        coaching_notes=("Sessão SEMPRE nas 4 fases fixas, nessa ordem.",),
        guide_excerpt=(
            "Mountain Dog organiza a sessão em 4 fases: (1) pré-ativação 2-3×8-12 @40-50% 1RM, RIR4, 45-60s; "
            "(2) explosivo 3-6×3-6 @70-85% com correntes/bandas, RIR2, 3-4min; (3) pump supramax 3-5×8-15 "
            "@50-70%, 0 RIR+, 30-60s; (4) alongamento com carga 1-2 sustentações de 30-60s. Nunca bandas/"
            "correntes na fase 3. Rotação de exercícios a cada 3-4 semanas."
        ),
    )
)

_reg(
    MethodSpec(
        key="y3t",
        name="Y3T (Yoda 3 Training)",
        author="Neil Hill",
        goal="Variação semanal de estímulo para quebrar a adaptação.",
        experience_min=Experience.INTERMEDIATE,
        progression_family=ProgressionFamily.DENSITY_QUALITY,
        days_per_week=(4, 5),
        phase_scope="week",
        phases=(
            Phase(name="Semana 1 — Pesada", reps="6-8", sets="—", rir="1", tempo="2-0-1-0", rest_seconds="180-240", note="100% compostos."),
            Phase(name="Semana 2 — Híbrida", reps="8-12", sets="—", rir="1 nos compostos / 0 nos isolados", tempo="2-1-1-1", rest_seconds="90-120", note="Mistura de compostos e isolados."),
            Phase(name="Semana 3 — Infernal", reps="15-30+", sets="—", rir="0 e além", tempo="2-2-1-2", rest_seconds="30-60", note="80% isolados. Drop sets, rest-pause, bi-sets, 21s. Segurança máxima."),
        ),
        mesocycle_weeks="ciclos de 3 semanas; rotação de exercícios a cada 9 semanas",
        deload_rule="Deload conservador por volta da semana 10-12, se necessário.",
        progression_rule=(
            "Semana 1 progride ao bater 8 reps em todas as séries; semana 2 ao bater 12 reps ou adicionar 1 "
            "série; semana 3 por densidade, reps totais e drops. Nunca comparar semana 1 com semana 3."
        ),
        forbidden=(
            "Semana 3 (infernal) PROÍBE compostos pesados: agachamento, terra e supino sob fadiga extrema.",
            "Não adicionar trabalho extra na semana 3.",
        ),
        equipment_pref="Barra na semana 1, setup misto na semana 2, máquinas/cabos na semana 3.",
        coaching_notes=("A mesma sessão muda radicalmente entre as 3 semanas do ciclo.",),
        guide_excerpt=(
            "Y3T rotaciona o estímulo em 3 semanas. Sem 1: 6-8 reps, 1 RIR, 3-4min, tempo 2-0-1-0, 100% "
            "compostos. Sem 2: 8-12 reps, 1 RIR compostos/0 isolados, 90-120s, tempo 2-1-1-1, mista. Sem 3: "
            "15-30+ reps, 0 RIR e além com drops/rest-pause/bi-sets/21s, 30-60s, tempo 2-2-1-2, 80% isolados. "
            "Semana infernal proíbe agachamento/terra/supino pesados. Rotação a cada 9 semanas."
        ),
    )
)

_reg(
    MethodSpec(
        key="rp_training",
        name="RP Training (Volume Landmarks)",
        author="Renaissance Periodization",
        goal="Hipertrofia orientada por MEV/MAV/MRV e autorregulação.",
        experience_min=Experience.INTERMEDIATE,
        progression_family=ProgressionFamily.VOLUME_LANDMARKS,
        days_per_week=(4, 5, 6),
        frequency_per_muscle="2x/semana por músculo (típico)",
        # O guia NÃO fixa um número de séries por exercício: a regra do RP é
        # começar no MEV e somar +1 set por músculo por semana até MAV/MRV. Este
        # campo antes trazia a frase de "3-4 EXERCÍCIOS por músculo" (outra
        # coisa), e o app lia o "3" dela como se fosse a série. Sem número aqui,
        # o motor usa o padrão conservador dele, explicitamente.
        sets_per_exercise="começa no MEV e sobe +1 série por músculo a cada semana, até o MRV",
        reps="faixas de hipertrofia; RIR progride de 3 até 0-1 ao longo do bloco",
        rir="3 → 0-1 ao longo do mesociclo",
        mesocycle_weeks="4-6 semanas de acumulação + 1 semana obrigatória de deload",
        deload_rule="Deload de 7 dias quando 2+ sinais de recuperação (desempenho, soreness, pump, articulação) piorarem.",
        progression_rule=(
            "Progressão ADITIVA: acrescentar um set por músculo por semana, do MEV em direção ao MAV/MRV. "
            "Não adicionar reps ou exercícios de forma arbitrária."
        ),
        forbidden=(
            "Não subir volume rápido demais nem usar landmarks fixos sem recalibrar.",
            "Não mentir no RIR — a autorregulação depende do dado honesto.",
        ),
        equipment_pref="Flexível (não fixa máquina vs barra), desde que o volume direto por músculo seja contado corretamente. Compostos como base, isoladores para complementar.",
        coaching_notes=(
            "Começar em MEV, subir sets semanalmente rumo a MAV/MRV, deload ao degradar recuperação.",
            "3-4 exercícios por músculo na semana; compostos como base.",
        ),
        guide_excerpt=(
            "RP: framework de volume landmarks (MEV/MAV/MRV) e autorregulação. Mesociclos de 4-6 semanas de "
            "acumulação + 1 semana de deload. Progressão aditiva: +1 set por músculo por semana. RIR 3→0-1. "
            "3-4 exercícios por músculo/semana, compostos como base. Deload quando 2+ sinais de recuperação "
            "piorarem."
        ),
    )
)

_reg(
    MethodSpec(
        key="wendler_531",
        name="Wendler 5/3/1",
        author="Jim Wendler",
        goal="Força sustentável de longo prazo baseada em percentuais.",
        experience_min=Experience.BEGINNER,
        progression_family=ProgressionFamily.TM_AMRAP,
        days_per_week=(3, 4),
        split_by_days={4: ["agachamento", "supino", "terra", "desenvolvimento"]},
        exercises_per_session="1 lift principal + acessórios (50-100 reps de empurrar/puxar/unilateral-core)",
        phase_scope="week",
        phases=(
            Phase(name="Semana 1 (5s)", reps="5/5/5+", sets="3", intensity_pct_1rm="65/75/85 do TM", note="Última série AMRAP."),
            Phase(name="Semana 2 (3s)", reps="3/3/3+", sets="3", intensity_pct_1rm="70/80/90 do TM"),
            Phase(name="Semana 3 (5/3/1)", reps="5/3/1+", sets="3", intensity_pct_1rm="75/85/95 do TM"),
            Phase(name="Semana 4 (deload)", reps="5/5/5", sets="3", intensity_pct_1rm="40/50/60 do TM"),
        ),
        mesocycle_weeks="ciclos de 4 semanas",
        deload_rule="Semana 4 de deload (40/50/60% do TM).",
        progression_rule=(
            "TM = 90% do 1RM real. Após cada ciclo: +5kg no TM de agachamento/terra e +2,5kg no de "
            "supino/desenvolvimento. O '+' é AMRAP com técnica limpa."
        ),
        forbidden=(
            "Não começar pesado demais (TM superestimado) nem fazer ego-lifting nas AMRAP.",
            "Não pular o deload nem 'hackear' o programa cedo demais.",
        ),
        equipment_pref="Rack, banco, barra, anilhas e acessórios simples. Escala fácil para home gym.",
        coaching_notes=(
            "Divisão clássica de 4 dias, um lift principal por dia.",
            "Após o principal: 50-100 reps totais de empurrar, puxar e unilateral/core. Variante BBB: 5×10 a 50-60% do TM.",
        ),
        guide_excerpt=(
            "5/3/1: percentuais sobre TM=90% do 1RM. Ciclos de 4 semanas. Sem1: 65×5,75×5,85×5+; sem2: "
            "70×3,80×3,90×3+; sem3: 75×5,85×3,95×1+; sem4 deload 40×5,50×5,60×5. '+' = AMRAP. 4 dias, um "
            "lift principal/dia (agachamento, supino, terra, desenvolvimento). Após o principal, 50-100 reps de "
            "empurrar/puxar/unilateral-core. +5kg TM agach/terra, +2,5kg supino/desenv por ciclo."
        ),
    )
)

_reg(
    MethodSpec(
        key="juggernaut",
        name="Método Juggernaut",
        author="Chad Wesley Smith",
        goal="Força com periodização em blocos (ondas 10s/8s/5s/3s).",
        experience_min=Experience.INTERMEDIATE,
        progression_family=ProgressionFamily.TM_AMRAP,
        days_per_week=(3, 4, 5),
        split_by_days={4: ["supino", "agachamento", "desenvolvimento", "terra"]},
        exercises_per_session="1 lift principal + acessórios estilo fisiculturismo",
        phase_scope="week",
        phases=(
            Phase(name="Onda 10s", reps="~10", sets="—", intensity_pct_1rm="60-72,5 do TM", note="4 semanas: acumulação, intensificação, realização (AMRAP), deload."),
            Phase(name="Onda 8s", reps="~8", sets="—", intensity_pct_1rm="65-77,5 do TM"),
            Phase(name="Onda 5s", reps="~5", sets="—", intensity_pct_1rm="72,5-85 do TM"),
            Phase(name="Onda 3s", reps="~3", sets="—", intensity_pct_1rm="80-92,5 do TM"),
        ),
        mesocycle_weeks="16+ semanas (4 ondas de 4 semanas cada)",
        deload_rule="Semana 4 de cada onda é deload obrigatório.",
        progression_rule=(
            "TM = 90% do 1RM. Cada onda: sem1 acumulação, sem2 intensificação, sem3 realização (top set "
            "AMRAP), sem4 deload. Após as 4 ondas: +2,5-5kg em superiores e +5-7,5kg em inferiores."
        ),
        forbidden=(
            "Não usar 1RM superestimado nem pular deloads.",
            "Não transformar o volume de acumulação em grind desnecessário.",
        ),
        equipment_pref="Setup de força clássico: barra, rack, banco e espaço para acessórios.",
        coaching_notes=("Template clássico de 4 dias; pode reduzir para 3 (combinando inferiores) ou 5 dias.",),
        guide_excerpt=(
            "Juggernaut: blocos de 16+ semanas, 4 ondas (10s/8s/5s/3s) sobre TM=90% do 1RM. Cada onda: 4 "
            "semanas (acumulação, intensificação, realização com top set AMRAP, deload). Faixas: 10s ~60-72,5% "
            "TM; 8s ~65-77,5%; 5s ~72,5-85%; 3s ~80-92,5%. 4 dias (supino/agachamento/desenvolvimento/terra) "
            "+ acessórios. +2,5-5kg superiores, +5-7,5kg inferiores após as 4 ondas."
        ),
    )
)

_reg(
    MethodSpec(
        key="westside",
        name="Westside Conjugate",
        author="Louie Simmons",
        goal="Força máxima, velocidade e correção de pontos fracos.",
        experience_min=Experience.ADVANCED,
        progression_family=ProgressionFamily.TM_AMRAP,
        days_per_week=(4,),
        # 4 sessões: 2 ME + 2 DE, ordem ME lower, ME upper, DE lower, DE upper.
        split_by_days={4: ["ME inferior", "ME superior", "DE inferior", "DE superior"]},
        frequency_per_muscle="72h entre sessões semelhantes",
        exercises_per_session="1 lift principal (ME ou DE) + 3-5 acessórios de 10-20 reps para pontos fracos",
        phase_scope="session",
        phases=(
            Phase(name="Max Effort (ME)", reps="1-3RM", sets="—", note="Sobe até 1-3RM em variações de agachamento/supino/terra. Rotacionar a variação a cada 1-3 semanas."),
            Phase(name="Dynamic Effort (DE)", reps="velocidade", sets="10×2 ou 9×3", intensity_pct_1rm="50-60 + bandas/correntes", note="Movido o mais rápido possível."),
            Phase(name="Repetition Effort (acessórios)", reps="10-20", sets="3-5", note="Mira pontos fracos."),
        ),
        mesocycle_weeks="contínuo com rotações de 1-3 semanas nas variações ME",
        deload_rule="Pequeno alívio nos acessórios e DE quando houver fadiga acumulada.",
        progression_rule=(
            "Rotacionar as variações ME a cada 1-3 semanas para evitar acomodação (lei da acomodação). "
            "Progresso medido por 1-3RM nas variações ME e velocidade nos DE."
        ),
        forbidden=(
            "Não repetir sempre os mesmos ME lifts (acomodação) nem transformar o DE em sessão lenta.",
            "Não abandonar o GPP nem usar acessórios sem propósito de ponto fraco.",
        ),
        equipment_pref="Rack, banco, barras/variações especiais, bandas, correntes e idealmente trenó/prowler para GPP.",
        coaching_notes=("Ordem operacional: ME inferior, ME superior, DE inferior, DE superior.",),
        guide_excerpt=(
            "Westside: ME + DE + RE na mesma semana, rotação frequente de exercícios (lei da acomodação). 4 "
            "sessões: 2 ME, 2 DE, 72h entre semelhantes. ME: sobe a 1-3RM em variações; DE: 50-60% com bandas/"
            "correntes, rápido (templates 10×2 e 9×3). 3-5 acessórios de 10-20 reps para pontos fracos. "
            "Sequência: ME lower, ME upper, DE lower, DE upper."
        ),
    )
)


def get_method(key: str) -> MethodSpec | None:
    return METHODS.get(key)


def list_methods() -> list[MethodSpec]:
    return list(METHODS.values())


# ---------------------------------------------------------------------------
# PLANO DO COACH — o treino que o coach monta por conta própria, sem estar preso
# a uma das 10 metodologias. É a opção PADRÃO do "Como eu monto seu treino":
# baseado em ciência, adaptado ao objetivo, e honra QUALQUER frequência 2–7 dias
# (os métodos consagrados só cobrem faixas específicas). NÃO é registrado em
# METHODS de propósito — não é uma metodologia pra navegar no Hub, é o motor
# genérico do coach. Continua determinístico e usando só exercícios reais da base
# (o montador nunca inventa exercício — regra do produto).
# ---------------------------------------------------------------------------

# Split por nº de dias, desenhado pra 2×/semana por grupo (regra 6: nada de
# bro-split como padrão). Os rótulos batem com _FOCUS_MUSCLES do methods_engine.
_COACH_SPLITS: dict[int, list[str]] = {
    2: ["full body a", "full body b"],
    3: ["superior", "inferior", "full body"],
    # 4 dias = upper/lower A/B: os dois superiores e os dois inferiores têm ênfase
    # diferente (A puxa peito/quadríceps; B puxa costas/posterior), então o
    # segundo dia do mesmo tipo não repete nem raspa sobras — sai coerente.
    4: ["superior a", "inferior a", "superior b", "inferior b"],
    5: ["push", "pull", "pernas", "superior", "inferior"],
    6: ["push", "pull", "pernas", "push", "pull", "pernas"],
    7: ["push", "pull", "pernas", "push", "pull", "pernas", "full body"],
}

# Parâmetros da sessão por objetivo — proporção composto/isolado, RIR, descanso.
# REPS: o coach trabalha com 8-12 em todo objetivo (a faixa-padrão de
# hipertrofia, o consenso mais robusto de estímulo x recuperação x adesão) —
# não varia por objetivo; o que muda é ratio/rir/descanso.
_COACH_REPS = "8-12"
_COACH_GOAL_PARAMS: dict[str, dict] = {
    "hipertrofia": {"reps": _COACH_REPS, "ratio": 0.5, "rir": "1-2", "rest": "90-120",
                    "family": ProgressionFamily.VOLUME_LANDMARKS,
                    "goal_txt": "Hipertrofia geral com sobrecarga progressiva e volume 2×/semana por grupo."},
    "emagrecimento": {"reps": _COACH_REPS, "ratio": 0.45, "rir": "1-2", "rest": "60-90",
                      "family": ProgressionFamily.DENSITY_QUALITY,
                      "goal_txt": "Preservar músculo no déficit com densidade e a mesma faixa de reps de sempre."},
    "recomposicao": {"reps": _COACH_REPS, "ratio": 0.5, "rir": "1-2", "rest": "75-90",
                     "family": ProgressionFamily.VOLUME_LANDMARKS,
                     "goal_txt": "Recomposição: força e volume equilibrados, 2×/semana por grupo."},
    "manutencao": {"reps": _COACH_REPS, "ratio": 0.5, "rir": "2", "rest": "90",
                   "family": ProgressionFamily.VOLUME_LANDMARKS,
                   "goal_txt": "Manter massa e força com um estímulo consistente e sustentável."},
    "performance": {"reps": _COACH_REPS, "ratio": 0.6, "rir": "2-3", "rest": "150-180",
                    "family": ProgressionFamily.LOAD_OR_REPS,
                    "goal_txt": "Força e performance: mais compostos e descanso maior, mesma faixa de reps."},
}


def coach_custom_spec(goal: str | None, experience: str | None = None) -> MethodSpec:
    """O plano PRÓPRIO do coach pra um objetivo, pronto pra qualquer frequência
    2–7. Reusa todo o motor determinístico (build_plan/validate_plan) — só troca
    os trilhos (split por dia, reps, proporção) pelos do coach. experience_min
    fica em BEGINNER de propósito: o volume real vem do tempo por sessão, não de
    travar por nível."""
    p = _COACH_GOAL_PARAMS.get(goal or "", _COACH_GOAL_PARAMS["hipertrofia"])
    return MethodSpec(
        key="coach_custom",
        name="Plano do coach",
        author="Atlas",
        goal=p["goal_txt"],
        experience_min=Experience.BEGINNER,
        progression_family=p["family"],
        days_per_week=(2, 3, 4, 5, 6, 7),
        split_by_days={d: list(s) for d, s in _COACH_SPLITS.items()},
        frequency_per_muscle="~2×/semana por grupo muscular",
        sets_per_exercise="3-4",
        reps=p["reps"],
        rir=p["rir"],
        rest_seconds=p["rest"],
        compound_ratio=p["ratio"],
        # Cada ocorrência de um foco repetido (ex.: "superior" 2x na semana)
        # escolhe exercício de novo — dá variação real (equipamento/ângulo
        # diferente) em vez de repetir a sessão idêntica.
        repeat_same_session=False,
        mesocycle_weeks="ciclos de ~6 semanas + deload conforme a periodização escolhida",
        deload_rule="Deload conduzido pela periodização do coach (automática/linear/ondulatória).",
        progression_rule=(
            "Sobrecarga progressiva: feche o topo da faixa de reps com técnica limpa, então suba a carga "
            "e volte à base da faixa. Reps primeiro, carga depois."
        ),
        coaching_notes=(
            "Compostos primeiro, isolados depois, em cada sessão.",
            "Frequência mínima de 2×/semana por grupo — sem bro-split.",
        ),
        guide_excerpt=(
            "Plano do coach: treino baseado em ciência montado pelo próprio coach (fora das 10 metodologias), "
            "adaptado ao seu objetivo e à frequência que você escolheu (2 a 7 dias), com 2×/semana por grupo "
            "muscular, compostos antes de isolados e sobrecarga progressiva."
        ),
    )


# --- Recomendação por perfil ("monte um treino ideal pro seu perfil") -------

_EXP_RANK = {"beginner": 0, "intermediate": 1, "advanced": 2}

# Mapeia a experiência do onboarding (PT) pro nível dos métodos (EN).
_EXP_FROM_PROFILE = {"iniciante": "beginner", "intermediario": "intermediate", "avancado": "advanced"}

# Por objetivo, a ordem de preferência das famílias de progressão (1ª = melhor).
_GOAL_FAMILY_PREF: dict[str, tuple[str, ...]] = {
    "hipertrofia": ("density_quality", "volume_landmarks", "load_or_reps", "tm_amrap"),
    "recomposicao": ("volume_landmarks", "density_quality", "load_or_reps", "tm_amrap"),
    "emagrecimento": ("volume_landmarks", "density_quality", "load_or_reps", "tm_amrap"),
    "manutencao": ("volume_landmarks", "load_or_reps", "density_quality", "tm_amrap"),
    "performance": ("tm_amrap", "load_or_reps", "volume_landmarks", "density_quality"),
}


def recommend_method_for_profile(
    experience: str | None, goal: str | None, days: int | None
) -> str:
    """Escolhe (determinístico) o método que melhor casa com o perfil da pessoa:
    respeita o nível mínimo de experiência, prefere a família de progressão do
    objetivo e um método que suporte a frequência que a pessoa tem. Sempre
    devolve uma chave válida (fallback seguro pra iniciante)."""
    user_rank = _EXP_RANK.get(_EXP_FROM_PROFILE.get(experience or "", ""), 0)
    fam_pref = _GOAL_FAMILY_PREF.get(goal or "", _GOAL_FAMILY_PREF["hipertrofia"])

    def score(m: MethodSpec) -> tuple:
        # 1) família do objetivo (menor índice = melhor); desconhecida vai pro fim
        fam = m.progression_family.value
        fam_score = fam_pref.index(fam) if fam in fam_pref else len(fam_pref)
        # 2) suporta a frequência do usuário?
        days_ok = 0 if (days is not None and days in m.days_per_week) else 1
        # 3) método mais próximo (por baixo) do nível do usuário — não muito fácil
        exp_gap = user_rank - _EXP_RANK[m.experience_min.value]
        return (fam_score, days_ok, exp_gap, m.key)

    eligible = [
        m for m in METHODS.values()
        if _EXP_RANK[m.experience_min.value] <= user_rank
    ] or [METHODS["kuba"]]  # iniciante seguro se nada casar
    return min(eligible, key=score).key
