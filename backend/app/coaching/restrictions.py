"""O que TIRAR do treino por causa de lesão, dor, limitação ou equipamento.

O questionário passou a perguntar região de lesão, região de dor, intensidade da
dor, limitações funcionais e equipamento disponível. Este módulo é o que faz
essas respostas mudarem o plano — sem ele elas seriam mais um dado coletado e
nunca lido, exatamente o defeito que a reescrita do questionário foi corrigir.

## Duas regras que governam tudo aqui

**1. Restrição tira MOVIMENTO, nunca MÚSCULO.** Quem tem ombro lesionado
continua treinando peito — só não recebe desenvolvimento militar nem crucifixo
com halteres. Zerar um grupo muscular inteiro seria transformar uma limitação
pontual num buraco permanente no treino, e a pessoa perderia o que ainda pode
fazer com segurança.

**2. A biblioteca precisa sobrar.** Toda restrição é escrita para deixar
alternativa de pé, e existe um teste que confere isso músculo por músculo, pra
toda combinação de restrições. Um filtro que esvazia a vaga não protege
ninguém: só entrega um treino pela metade.

## Por que casa com a TAXONOMIA e não com o nome do exercício

O filtro de preferências que já existia casa por palavra no nome
(`_PREF_EXCLUI`). Funciona pra "sem agachamento livre", que é literalmente um
nome, e é frágil pra qualquer coisa conceitual: "evitar carga na coluna" não é
uma palavra. Aqui as regras são escritas sobre os atributos que a taxonomia já
declara — padrão de movimento, custo sistêmico, risco articular, estabilidade,
limitante. É a mesma lição do `is_compound`, que era decidido por palavra-chave e
errava o pulldown de braços estendidos.

Este módulo NÃO diagnostica nada (regra 8 do produto). Ele só evita movimento
sobre uma região que a pessoa declarou sensível.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ai.exercise_taxonomy import (
    JointRisk,
    Limiter,
    Pattern,
    Stability,
    Systemic,
    Taxon,
)
from app.models.exercise import Equipment, MuscleGroup

M = MuscleGroup

# Grupos afetados por uma queixa de membro superior e de membro inferior. Uma
# lesão de ombro não deveria mexer no leg press.
_SUPERIOR = frozenset({M.CHEST, M.BACK, M.SHOULDERS, M.TRICEPS, M.BICEPS, M.TRAPS, M.FOREARMS})
_INFERIOR = frozenset({M.QUADS, M.HAMSTRINGS, M.GLUTES, M.CALVES})
_TODOS = _SUPERIOR | _INFERIOR | frozenset({M.ABS, M.FULL_BODY})


@dataclass(frozen=True)
class Restricao:
    """O que uma queixa proíbe, e onde.

    `escopo` limita o alcance: sem ele, "evitar exercício instável" por causa do
    tornozelo tiraria a rosca alternada da pessoa.
    """

    escopo: frozenset = field(default=frozenset())
    patterns: frozenset = field(default=frozenset())
    # Exercício que carrega a coluna / exige muito do sistema.
    sem_sistemico_alto: bool = False
    # Exercício que depende de equilíbrio ou de técnica fina.
    sem_instavel: bool = False
    # Exercício cujo custo articular já é maior que o normal com carga alta.
    sem_risco_articular: bool = False
    # Exercício em que a lombar é quem encerra a série.
    sem_limitante_lombar: bool = False
    # Exercício em que o fôlego é quem encerra a série.
    sem_limitante_cardio: bool = False

    def proibe(self, taxon: Taxon, muscle: MuscleGroup | None) -> bool:
        if muscle is not None and self.escopo and muscle not in self.escopo:
            return False
        if taxon.pattern in self.patterns:
            return True
        if self.sem_sistemico_alto and taxon.systemic is Systemic.ALTO:
            return True
        if self.sem_instavel and taxon.stability is Stability.BAIXA:
            return True
        if self.sem_risco_articular and taxon.joint_risk is not JointRisk.BAIXO:
            return True
        if self.sem_limitante_lombar and taxon.limiter is Limiter.LOMBAR:
            return True
        if self.sem_limitante_cardio and taxon.limiter is Limiter.CARDIO:
            return True
        return False


# --- Por REGIÃO do corpo ----------------------------------------------------
# Vale tanto pra lesão declarada quanto pra dor de intensidade moderada ou forte.
POR_REGIAO: dict[str, Restricao] = {
    # Ombro: o que machuca é carga acima da cabeça e carga na posição alongada.
    # Sai todo desenvolvimento e todo empurrar/puxar de risco articular elevado
    # (supino com barra, crucifixo com halteres, Arnold, paralelas). Ficam
    # máquinas, cabos e Smith, que são a maioria da biblioteca de superior.
    "ombro": Restricao(
        escopo=_SUPERIOR,
        patterns=frozenset({Pattern.PUSH_V}),
        sem_risco_articular=True,
    ),
    # Cotovelo: extensão de tríceps com barra/halter e rosca de barra reta são as
    # queixas clássicas. Todas já estão marcadas com risco articular na taxonomia.
    "cotovelo": Restricao(escopo=_SUPERIOR, sem_risco_articular=True),
    # Punho: mesma família de exercícios (barra fixando a pegada em pronação ou
    # supinação forçada), mais o que exige estabilizar carga livre com a mão.
    "punho": Restricao(escopo=_SUPERIOR, sem_risco_articular=True, sem_instavel=True),
    # Pescoço: barra apoiada nas costas e carga acima da cabeça.
    "cervical": Restricao(
        escopo=_TODOS,
        patterns=frozenset({Pattern.PUSH_V}),
        sem_sistemico_alto=True,
    ),
    # Lombar: é a restrição mais ampla, e precisa ser. Sai tudo que comprime a
    # coluna e tudo que termina com os eretores cedendo — terra, stiff, good
    # morning, remada curvada, agachamento livre, barra por cima da cabeça.
    "lombar": Restricao(escopo=_TODOS, sem_sistemico_alto=True, sem_limitante_lombar=True),
    # Quadril: flexão profunda sob carga e movimento que exige estabilizar o
    # tronco em pé.
    "quadril": Restricao(escopo=_INFERIOR, sem_sistemico_alto=True, sem_instavel=True),
    # Joelho: unilateral em pé castiga o joelho de apoio, e o que já tem risco
    # articular alto de joelho (extensora pesada, agachamento livre) sai junto.
    "joelho": Restricao(escopo=_INFERIOR, sem_instavel=True, sem_risco_articular=True),
    # Tornozelo: qualquer coisa que peça equilíbrio sobre um pé só.
    "tornozelo": Restricao(escopo=_INFERIOR, sem_instavel=True),
}

# --- Por LIMITAÇÃO funcional ------------------------------------------------
POR_LIMITACAO: dict[str, Restricao] = {
    # Mobilidade reduzida: trajetória guiada resolve. Sai o que exige o próprio
    # corpo achar a posição, e o que pede amplitude acima da cabeça.
    "mobilidade": Restricao(
        escopo=_TODOS, patterns=frozenset({Pattern.PUSH_V}), sem_instavel=True
    ),
    "equilibrio": Restricao(escopo=_TODOS, sem_instavel=True),
    # Respiração: sai o que sobe muito a demanda global e o que termina por falta
    # de ar antes do músculo cansar.
    "respiracao": Restricao(escopo=_TODOS, sem_sistemico_alto=True, sem_limitante_cardio=True),
    # Condicionamento baixo já ganha mais descanso (prescription.rest_seconds).
    # Aqui sai só o que tem o fôlego como limitante declarado — insistir nele
    # seria prescrever uma série que acaba antes do estímulo acontecer.
    "condicionamento": Restricao(escopo=_TODOS, sem_limitante_cardio=True),
}

# Dor leve NÃO filtra nada. O manual é explícito em não tratar desconforto
# pequeno como lesão, e zerar exercício por causa de um incômodo de 2/10 tiraria
# da pessoa justamente o movimento que a mantém treinando.
_INTENSIDADES_QUE_FILTRAM = frozenset({"moderada", "forte"})

# --- Equipamento ------------------------------------------------------------
# O que cada item marcado em "o que você tem em casa" habilita. Peso corporal
# está sempre disponível — é o que garante que alguém sem nada ainda treine.
EQUIPAMENTO_DE: dict[str, frozenset] = {
    "halteres": frozenset({Equipment.DUMBBELL}),
    "barra": frozenset({Equipment.BARBELL}),
    "banco": frozenset(),  # não é equipamento de resistência: habilita variações
    "elasticos": frozenset({Equipment.BAND}),
    "barra_fixa": frozenset({Equipment.BODYWEIGHT}),
    "polia": frozenset({Equipment.CABLE}),
    "kettlebell": frozenset({Equipment.KETTLEBELL}),
    "maquina": frozenset({Equipment.MACHINE, Equipment.SMITH_MACHINE}),
}
_SEMPRE_DISPONIVEL = frozenset({Equipment.BODYWEIGHT, Equipment.OTHER})


@dataclass(frozen=True)
class Perfil:
    """O recorte do perfil que este módulo precisa. Existe pra o motor não ter
    que carregar o ORM inteiro nem os testes montarem um usuário no banco."""

    regioes: frozenset = field(default=frozenset())
    limitacoes: frozenset = field(default=frozenset())
    equipamentos: frozenset | None = None  # None = sem restrição de equipamento

    @property
    def vazio(self) -> bool:
        return not self.regioes and not self.limitacoes and self.equipamentos is None


PERFIL_LIVRE = Perfil()


def perfil_de(profile) -> Perfil:
    """Lê do UserProfile as respostas que restringem exercício.

    Lesão e dor são somadas na MESMA lista de regiões: pra escolher exercício,
    "ombro operado" e "ombro que dói ao empurrar" pedem a mesma coisa. O que as
    separa é a dor leve, que não filtra nada.
    """
    if profile is None:
        return PERFIL_LIVRE

    regioes: set[str] = set()
    if getattr(profile, "has_injury", None):
        regioes.update(getattr(profile, "injury_regions", None) or [])
    if getattr(profile, "has_pain", None):
        intensidade = getattr(profile, "pain_intensity", None)
        if intensidade in _INTENSIDADES_QUE_FILTRAM:
            regioes.update(getattr(profile, "pain_regions", None) or [])

    # Equipamento só limita quem treina em casa COM equipamento. Academia (mesmo
    # básica) assume-se completa; "casa sem equipamento" já é resolvido pelo
    # local, que a biblioteca filtra em outro lugar.
    equipamentos: frozenset | None = None
    local = getattr(getattr(profile, "training_location", None), "value", None)
    if local == "casa_com_equipamento":
        marcados = getattr(profile, "home_equipment", None) or []
        disponiveis = set(_SEMPRE_DISPONIVEL)
        for item in marcados:
            disponiveis.update(EQUIPAMENTO_DE.get(item, frozenset()))
        equipamentos = frozenset(disponiveis)

    return Perfil(
        regioes=frozenset(r for r in regioes if r in POR_REGIAO),
        limitacoes=frozenset(
            x for x in (getattr(profile, "limitations", None) or []) if x in POR_LIMITACAO
        ),
        equipamentos=equipamentos,
    )


def proibido(taxon: Taxon, muscle: MuscleGroup | None, equipment, perfil: Perfil) -> bool:
    """True quando este exercício não deve entrar no treino desta pessoa."""
    if perfil.vazio:
        return False
    if perfil.equipamentos is not None and equipment not in perfil.equipamentos:
        return True
    for regiao in perfil.regioes:
        if POR_REGIAO[regiao].proibe(taxon, muscle):
            return True
    for limitacao in perfil.limitacoes:
        if POR_LIMITACAO[limitacao].proibe(taxon, muscle):
            return True
    return False


# --- O que a pessoa precisa LER ---------------------------------------------
def avisos(profile) -> list[str]:
    """Avisos honestos sobre o que foi tirado do treino e por quê.

    Filtrar em silêncio é pior que não filtrar: a pessoa procura o supino livre,
    não acha, e conclui que o app é ruim. E dor forte não é assunto de ajuste de
    treino — é encaminhamento, sem diagnóstico e sem drama (regra 8).
    """
    if profile is None:
        return []
    out: list[str] = []

    if getattr(profile, "has_pain", None) and getattr(profile, "pain_intensity", None) == "forte":
        out.append(
            "Você marcou dor forte. Eu tirei do seu plano os movimentos que carregam essa "
            "região, mas dor nesse nível merece uma avaliação presencial — eu não consigo "
            "examinar você, e treinar por cima disso costuma custar mais tempo do que parar "
            "pra resolver."
        )
    if getattr(profile, "has_injury", None) and getattr(profile, "medical_clearance", None) is False:
        out.append(
            "Como você ainda não tem liberação profissional pra treinar com essa condição, "
            "montei tudo na versão conservadora: nada de carga acima da cabeça ou de "
            "exercício que dependa de equilíbrio na região afetada."
        )

    perfil = perfil_de(profile)
    if perfil.regioes:
        out.append(
            "Tirei do plano os exercícios que carregam: "
            + ", ".join(sorted(perfil.regioes))
            + ". Se alguma dessas regiões melhorar, atualize o questionário que eu devolvo "
            "os movimentos."
        )
    if perfil.equipamentos is not None:
        out.append(
            "Montei só com o equipamento que você marcou ter em casa. Marcando mais itens "
            "no questionário, o plano cresce junto."
        )
    return out
