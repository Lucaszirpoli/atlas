"""Monta e SALVA o treino completo da pessoa a partir das preferências do
Coaching ('Como eu monto seu treino'). Núcleo reutilizável: o endpoint
/coaching/build-workout e a ferramenta do chat do coach chamam o mesmo código.

Determinístico (sem IA): escolhe o método que casa com experiência/objetivo/
frequência, aplica ponto fraco + tempo por sessão, e grava como as rotinas
ativas — arquivando as antigas (nunca deleta, regra 4).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import exercise_taxonomy, methods_engine, plan_review
from app.ai.exercise_taxonomy import Pattern
from app.ai.methods import coach_custom_spec
from app.ai.methods_engine import build_plan
from app.coaching import cycle_state, prescription, training_brain, volume_landmarks
from app.models.coaching_technique_cue import CoachingTechniqueCue
from app.models.exercise import MuscleGroup
from app.models.routine import Routine, RoutineExercise
from app.models.user import User


# Teto de vagas acrescentadas numa montagem. É uma trava de segurança do laço
# (o alvo semanal no pico do mesociclo pede ~32 vagas contra as ~20 do plano
# base), não uma meta — quem para o laço de verdade é o alvo ter sido atingido.
_MAX_VAGAS_EXTRAS = 24

# Exercícios por sessão que o coach não passa, mesmo com volume sobrando. É o
# mesmo teto que build_plan já respeita; passar disso deixa de ser treino e
# vira maratona, por mais denso que a técnica avançada deixe a sessão.
_MAX_EXERCICIOS_POR_SESSAO = 9

# Técnicas avançadas por sessão. Elas são o que segura o tempo quando o volume
# manda acrescentar exercício, mas todas trabalham perto da falha — em exercício
# demais viram fadiga que não recupera, e aí o volume extra não vira estímulo.
_MAX_TECNICAS_POR_SESSAO = 3

# Vagas mínimas por músculo na semana. É a regra 6 do produto (frequência mínima
# de 2×/semana por grupo muscular, sem bro-split) em forma de trava: nem a
# equalização mais agressiva pode deixar um músculo com um treino só na semana.
_MIN_VAGAS_POR_MUSCULO = 2

# Trava do laço de poda (como _MAX_VAGAS_EXTRAS é a do laço de preenchimento).
# Quem para o laço de verdade é não sobrar excesso.
_MAX_VAGAS_PODADAS = 24


# `_parse_reps` e `_first_int` viviam aqui pra ler "8-12" e "90-120" do TEXTO do
# MethodSpec. Sumiram junto com a fonte: reps e descanso agora saem da mecânica
# do exercício (`prescription`), não de uma string igual pra todo mundo.


def _muscle_or_none(valor: str | None) -> MuscleGroup | None:
    """O músculo da vaga como enum. A vaga guarda o VALOR em texto, e um valor
    que o enum não conhece não pode derrubar a montagem — só significa que a
    taxonomia vai cair no palpite conservador dela."""
    try:
        return MuscleGroup(valor) if valor else None
    except ValueError:
        return None


def revert_technique_cues(db: Session, user_id: int) -> int:
    """Reverte TODAS as dicas de técnica ativas da pessoa. Devolve quantas.

    Existe pra um caso específico: a dica de técnica sobrevive a remontagens de
    propósito (comentário mais abaixo, no laço de teto de séries) — é o que faz
    uma técnica aplicada manualmente continuar valendo depois de refazer o
    treino. Mas isso quer dizer que DESLIGAR "técnicas avançadas" no questionário
    não fazia nada sozinho: as dicas de antes ficavam ativas pra sempre, e a
    pessoa via o treino continuar com myo-reps/rest-pause/etc. mesmo tendo
    respondido "não". Quem muda a preferência pra False precisa chamar isto —
    ver `plan_service.apply_answers_to_profile` e
    `routers.coaching.set_training_prefs`, os dois lugares que gravam a escolha.

    Não mexe em `target_sets` já gravado (a mesma limitação do "Desfazer" manual
    em `/technique-cues/{id}/remove` — o número de séries só volta ao normal na
    PRÓXIMA vez que o treino for remontado)."""
    agora = datetime.now(timezone.utc)
    cues = list(
        db.execute(
            select(CoachingTechniqueCue).where(
                CoachingTechniqueCue.user_id == user_id,
                CoachingTechniqueCue.reverted_at.is_(None),
            )
        ).scalars()
    )
    for cue in cues:
        cue.reverted_at = agora
    return len(cues)


def _reparar_cobertura(
    db: Session,
    plan,
    pendencias: list[str],
    *,
    prefer_machines: bool,
    exercise_prefs: list[str],
) -> list[str]:
    """Tenta CONSERTAR o que a revisão global apontou, e devolve o que sobrou.

    A regra mestra manda reestruturar o treino quando a validação reprova, e a
    lacuna que dá pra consertar mecanicamente é a de cobertura regional
    (Princípio 6): falta 'peito clavicular' na semana -> acrescenta um exercício
    dessa região exata num dia que já treina peito.

    Desequilíbrio e redundância NÃO são reparados aqui de propósito: eles vêm da
    estrutura do blueprint, então consertar caso a caso esconderia um erro de
    desenho que tem que ser corrigido no blueprint (e os testes cobram isso).
    O que sobra volta como pendência, pra ficar registrado em vez de silencioso.
    """
    if not pendencias:
        return []
    faltando = plan_review.regioes_descobertas(plan)
    for musculo, regiao in faltando:
        methods_engine.add_accessory_slot(
            db, plan, musculo,
            prefer_machines=prefer_machines,
            exercise_prefs=exercise_prefs,
            max_per_session=_MAX_EXERCICIOS_POR_SESSAO,
            region=regiao,
        )
    return plan_review.review(plan)


def build_and_save(db: Session, user: User) -> dict:
    """Monta o treino pelas prefs e substitui as rotinas ativas. Devolve um
    resumo (método, dias, rotinas, ponto fraco, cardio, periodização)."""
    profile = getattr(user, "profile", None)
    if profile is None:
        raise ValueError("Complete seu perfil primeiro.")

    exp = profile.experience_level.value if profile.experience_level else None
    goal = profile.goal.value if profile.goal else None
    # Dias por semana: a escolha explícita da pessoa ("Dias por semana", 2–7)
    # manda; sem ela, infere dos dias do onboarding; sem nada, 3 (seguro).
    days = training_brain.valid_training_days(profile.training_days_per_week)
    if days is None:
        days = len(profile.available_days) if profile.available_days else None
    if days is None:
        days = 3
    days = max(training_brain.TRAINING_DAYS_MIN, min(days, training_brain.TRAINING_DAYS_MAX))
    # PADRÃO: o coach monta o plano DELE (fora das 10 metodologias), adaptado ao
    # objetivo e à frequência escolhida. Determinístico e só com exercícios reais
    # da base — o motor nunca inventa exercício.
    method = coach_custom_spec(goal, exp)

    weak_values = training_brain.resolve_weak_points(profile)
    wps: list[MuscleGroup] = []
    for w in weak_values:
        try:
            wps.append(MuscleGroup(w))
        except ValueError:
            pass
    session_target = training_brain.session_exercise_target(profile.session_length)
    # Sessão curta: prioriza compostos multiarticulares e máquinas que pegam
    # vários músculos, pra render mais estímulo no pouco tempo.
    tempo_sessao = training_brain.valid_session_length(profile.session_length)
    curto = tempo_sessao == "curto"
    prefs_exercicio = training_brain.valid_exercise_prefs(getattr(profile, "exercise_prefs", None))
    plan = build_plan(
        db, method, available_days=days, weak_points=wps,
        session_target=session_target, time_efficient=curto,
        # Preferências marcadas no questionário (máquinas x peso livre, evitar
        # agachamento livre/acima da cabeça/impacto, unilateral). Chegam até a
        # escolha de cada exercício — é o que faz a resposta virar treino.
        exercise_prefs=prefs_exercicio,
        # O id da pessoa. Duas pessoas que responderam a mesma coisa continuam
        # recebendo o mesmo PLANO (mesma divisão, mesmas prioridades, mesmo
        # volume) — o que muda é qual dos exercícios equivalentes preenche cada
        # vaga, pra o treino ser reconhecivelmente dela. Ver methods_engine.seed.
        seed=user.id,
    )

    # --- REGRA DE COERÊNCIA GLOBAL ------------------------------------------
    # "Antes de finalizar qualquer programa de treinamento, a IA deve validar
    # automaticamente [...]. Se qualquer resposta for negativa, o treino deve
    # ser reestruturado antes de ser entregue."
    #
    # Roda aqui, e não só dentro do build_plan, porque as vagas de volume
    # acrescentadas mais abaixo também podem quebrar a coerência — então a
    # revisão final acontece DEPOIS de todo mundo ter mexido no plano (ver o
    # segundo `review` no fim desta função).
    pendencias = plan_review.review(plan, method=method)
    pendencias = _reparar_cobertura(db, plan, pendencias, prefer_machines=curto,
                                    exercise_prefs=prefs_exercicio)

    # Volume semanal por grupo muscular (regra: sobe/desce série por músculo
    # dentro da faixa MEV-MRV baseada em evidência, ajustada por nível — nunca
    # um número fixo igual pra todo exercício, regra 6/espec. Parte 3 item 3).
    # Conta quantas vagas da semana treinam cada músculo como principal, pega
    # o alvo semanal do músculo e distribui entre essas vagas.
    weeks_acc = cycle_state.weeks_accumulating(db, user.id, datetime.now(timezone.utc))
    slot_count_by_muscle: dict[str, int] = {}
    for s in plan.sessions:
        for sl in s.slots:
            if sl.exercise_id is None:
                continue
            slot_count_by_muscle[sl.muscle_group] = slot_count_by_muscle.get(sl.muscle_group, 0) + 1

    # O volume de TODOS os músculos sai de uma vez: subir o ponto fraco obriga a
    # baixar o resto (equalização do §6.1). Calcular músculo a músculo não
    # enxerga o custo sistêmico e a semana inteira estoura junto.
    musculos: list[MuscleGroup] = []
    desconhecidos: list[str] = []
    for muscle_value in slot_count_by_muscle:
        try:
            musculos.append(MuscleGroup(muscle_value))
        except ValueError:
            desconhecidos.append(muscle_value)

    # Sono, estresse, dor entre sessões e outro esporte viram UM fator que
    # desloca o volume da semana inteira (training_brain.recovery_factor). Quem
    # está dormindo mal recebe o mesmo desenho de treino com menos série — não um
    # treino diferente, que seria imprevisível pra quem acompanha a evolução.
    recuperacao = training_brain.recovery_factor(profile)
    plano_semanal = volume_landmarks.weekly_plan(
        musculos, exp, weeks_acc, weak_points=wps, session_length=tempo_sessao,
        recovery=recuperacao,
    )

    # --- VOLUME QUE NÃO CABE NAS VAGAS -> OUTRO EXERCÍCIO -------------------
    # Uma vaga entrega no máximo PER_EXERCISE_MAX séries de trabalho efetivas.
    # Quando o alvo semanal de um músculo não cabe nas vagas que ele tem, a
    # saída é ACRESCENTAR EXERCÍCIO, não empilhar série na mesma vaga: passar do
    # teto por vaga é fadiga sem estímulo novo. Sem isto o clamp do teto cortava
    # o excedente em silêncio e a semana saía subdosada sem ninguém saber.
    #
    # Vale pra TODO músculo, não só pro ponto fraco — equilibrar com exercício é
    # o mecanismo, e a densidade (técnica avançada, abaixo) é o que segura o
    # tempo. O músculo com maior falta é servido primeiro; empate pelo nome pra
    # a montagem continuar determinística.
    #
    # O alvo semanal SOBE ao longo do mesociclo (volume_landmarks._progress), o
    # que faz o número de exercícios subir junto — que é o que fase de
    # acumulação significa. No início do ciclo quase nada é acrescentado.
    # --- PODA: VAGA DEMAIS PRO ALVO ----------------------------------------
    # Antes de acrescentar exercício pra quem está devendo, TIRAR de quem está
    # sobrando. Uma vaga entrega no mínimo PER_EXERCISE_MIN séries, então um
    # músculo com mais vagas do que o alvo comporta não entrega o alvo: ele
    # entrega o piso vezes o número de vagas.
    #
    # É AQUI que a equalização do §6.1 ganhava e perdia no mesmo passo. O alvo do
    # financiador caía pra 5, e logo depois costas com 5 vagas saía com 10 séries
    # (2 por vaga) — o dobro do alvo, mais volume que o próprio ponto fraco. A
    # pessoa trocava o ponto fraco no questionário e via o treino não mudar nada,
    # porque de fato não mudava: os dois lados da conta eram desfeitos pelo clamp.
    #
    # Podar é o que LIBERA a vaga (e o tempo de sessão) que o ponto fraco vai
    # ocupar logo abaixo. Duas travas: frequência mínima de 2×/semana por grupo
    # nunca é violada, e o equilíbrio da semana não pode sair da tolerância —
    # financiar braço não pode custar a simetria empurrar/puxar do treino.
    empurrar_puxar = plan_review.desequilibrio_empurrar_puxar(plan)
    joelho_quadril = plan_review.desequilibrio_joelho_quadril(plan)

    def _mantem_equilibrio(sl) -> bool:
        direcao = plan_review.direcao_do_slot(sl)
        depois_ep = empurrar_puxar - (1 if direcao == "empurrar" else -1 if direcao == "puxar" else 0)
        depois_jq = joelho_quadril
        if sl.pattern == Pattern.KNEE.value:
            depois_jq -= 1
        elif sl.pattern == Pattern.HIP.value:
            depois_jq += 1
        return (
            abs(depois_ep) < plan_review.TOLERANCIA_EQUILIBRIO
            and abs(depois_jq) < plan_review.TOLERANCIA_EQUILIBRIO
        )

    limite_de_vagas = {
        m: max(_MIN_VAGAS_POR_MUSCULO, volume_landmarks.slot_range(plano_semanal[m])[1])
        for m in musculos
    }
    exercicios_podados: list[str] = []
    travados: set[MuscleGroup] = set()
    # UMA vaga por vez, sempre do músculo com maior excesso — e não um músculo
    # até o fim antes de passar pro próximo. A diferença importa por causa do
    # guarda de equilíbrio: podando costas até o fim primeiro, a semana ficava
    # com 2 puxadas a menos que empurradas na terceira remoção e o guarda travava
    # costas ali, com o excesso quase inteiro ainda de pé — e peito, que ia
    # devolver o equilíbrio, só seria podado depois. Alternando, os dois lados
    # descem juntos e a semana nunca sai da tolerância.
    for _ in range(_MAX_VAGAS_PODADAS):
        excessos = [
            (slot_count_by_muscle.get(m.value, 0) - limite_de_vagas[m], m.value, m)
            for m in musculos
            if m not in travados and slot_count_by_muscle.get(m.value, 0) > limite_de_vagas[m]
        ]
        if not excessos:
            break
        _, _, muscle = max(excessos, key=lambda e: (e[0], e[1]))
        removida = methods_engine.drop_surplus_slot(
            plan, muscle,
            pode_remover=_mantem_equilibrio,
            min_por_sessao=training_brain.MIN_EXERCISES_PER_SESSION,
        )
        if removida is None:
            # Tudo que sobrava nesse músculo é protegido (região exigida,
            # abertura do dia, equilíbrio da semana). O excesso fica e é
            # consciente — mas o laço continua servindo os outros músculos.
            travados.add(muscle)
            continue
        slot_count_by_muscle[muscle.value] -= 1
        exercicios_podados.append(removida.exercise_name)
        empurrar_puxar = plan_review.desequilibrio_empurrar_puxar(plan)
        joelho_quadril = plan_review.desequilibrio_joelho_quadril(plan)

    exercicios_extras: list[str] = []
    ids_extras: set[int] = set()
    for _ in range(_MAX_VAGAS_EXTRAS):
        faltas = [
            (plano_semanal[m] - slot_count_by_muscle.get(m.value, 0) * volume_landmarks.PER_EXERCISE_MAX, m.value, m)
            for m in musculos
            if plano_semanal[m] > slot_count_by_muscle.get(m.value, 0) * volume_landmarks.PER_EXERCISE_MAX
        ]
        if not faltas:
            break
        # PONTO FRACO PRIMEIRO. Antes a fila era só "quem está devendo mais", e o
        # ponto fraco disputava as vagas livres da sessão (teto de 9 exercícios)
        # em pé de igualdade com quem não é prioridade nenhuma — quando a sessão
        # enchia, quem ficava sem era justamente ele. Prioridade que só vale
        # enquanto sobra espaço não é prioridade.
        _, _, muscle = max(faltas, key=lambda f: (f[2] in wps, f[0], f[1]))
        slot = methods_engine.add_accessory_slot(
            db, plan, muscle, prefer_machines=curto,
            exercise_prefs=prefs_exercicio,
            max_per_session=_MAX_EXERCICIOS_POR_SESSAO,
            seed=user.id,
        )
        if slot is None:
            # Sem exercício novo desse músculo na base (ou sessões cheias): o
            # alvo dele não fecha. Tira ele da fila pra não travar o laço e
            # deixar os outros músculos sem serem servidos.
            slot_count_by_muscle[muscle.value] = slot_count_by_muscle.get(muscle.value, 0)
            plano_semanal[muscle] = slot_count_by_muscle[muscle.value] * volume_landmarks.PER_EXERCISE_MAX
            continue
        slot_count_by_muscle[muscle.value] = slot_count_by_muscle.get(muscle.value, 0) + 1
        exercicios_extras.append(slot.exercise_name)
        ids_extras.add(slot.exercise_id)

    # --- TODO PONTO FRACO TEM EXERCÍCIO NA SEMANA ---------------------------
    # A promoção (methods_engine._priorizar_ponto_fraco) e a proteção contra o
    # corte por tempo cobrem o caso normal: o músculo tem vaga em algum dia e
    # essa vaga sobrevive. Sobra um canto que nenhuma das duas alcança — o
    # músculo não ter vaga em blueprint NENHUM da divisão. Glúteo em quem treina
    # 2 dias é o caso real: o full body de 2 dias não tem vaga de glúteo, então
    # não há o que promover nem o que proteger, e a pessoa marcava glúteo como
    # prioridade pra receber zero exercício dele.
    #
    # Aqui a regra é dita direto, sem depender do desenho de cada blueprint:
    # quem marcou um músculo como prioridade termina a semana com pelo menos um
    # exercício dele. O resto do volume vem pelos caminhos de sempre.
    for muscle in wps:
        if slot_count_by_muscle.get(muscle.value, 0) > 0:
            continue
        slot = methods_engine.add_accessory_slot(
            db, plan, muscle, prefer_machines=curto,
            exercise_prefs=prefs_exercicio,
            max_per_session=_MAX_EXERCICIOS_POR_SESSAO,
            seed=user.id,
            permitir_musculo_novo=True,
        )
        if slot is None:
            continue  # a base não tem exercício desse músculo — reportado na revisão
        slot_count_by_muscle[muscle.value] = 1
        exercicios_extras.append(slot.exercise_name)
        ids_extras.add(slot.exercise_id)
        # O músculo passa a existir no plano da semana, então precisa de alvo de
        # volume — senão a distribuição de séries mais abaixo não sabe o que
        # fazer com ele e cai no padrão de 3.
        if muscle not in plano_semanal:
            musculos.append(muscle)
            plano_semanal[muscle] = volume_landmarks.weekly_target_sets(
                muscle, exp, weeks_acc, priority="alta", session_length=tempo_sessao,
                recovery=recuperacao,
            )

    # --- PISO DE EXERCÍCIOS POR SESSÃO --------------------------------------
    # O volume da SEMANA fecha por muitos caminhos, e nenhum deles pode ser
    # entregar um dia com 3 exercícios. A poda já respeita o piso, mas ela não é
    # a única forma de um dia sair curto: o recorte por tempo, uma vaga que a
    # base não conseguiu preencher ou um blueprint enxuto chegam no mesmo lugar.
    # Aqui é o último passo antes da revisão — a garantia de que TODO dia
    # entregue é um treino inteiro.
    #
    # A vaga extra vai pro músculo daquele dia que está mais longe de fechar o
    # próprio alvo semanal (o ponto fraco primeiro, pelo mesmo motivo de sempre).
    # Quando nenhum músculo do dia tem folga no alvo, a vaga entra assim mesmo e
    # o músculo passa um pouco do alvo: um dia inteiro vale mais que a última
    # série de precisão do volume semanal — e o teto por exercício, que é o que
    # protege da fadiga inútil, continua valendo.
    for sessao in plan.sessions:
        for _ in range(training_brain.MIN_EXERCISES_PER_SESSION):
            if len(sessao.slots) >= training_brain.MIN_EXERCISES_PER_SESSION:
                break
            do_dia = {sl.muscle_group for sl in sessao.slots}
            candidatos = [m for m in musculos if m.value in do_dia]
            if not candidatos:
                break

            def folga(m: MuscleGroup) -> int:
                return plano_semanal[m] - slot_count_by_muscle.get(m.value, 0) * volume_landmarks.PER_EXERCISE_MIN

            candidatos.sort(key=lambda m: (m not in wps, -folga(m), m.value))
            entrou = None
            for muscle in candidatos:
                entrou = methods_engine.add_accessory_slot(
                    db, plan, muscle, prefer_machines=curto,
                    exercise_prefs=prefs_exercicio,
                    max_per_session=_MAX_EXERCICIOS_POR_SESSAO,
                    seed=user.id,
                    session=sessao,
                )
                if entrou is not None:
                    break
            if entrou is None:
                break  # a base não tem mais nada que sirva neste dia
            slot_count_by_muscle[muscle.value] = slot_count_by_muscle.get(muscle.value, 0) + 1
            exercicios_extras.append(entrou.exercise_name)
            ids_extras.add(entrou.exercise_id)

    # Revisão global FINAL: as vagas de volume acima entraram depois da primeira
    # checagem, então é aqui que o treino que vai ser entregue é conferido.
    pendencias = plan_review.review(plan, method=method)

    base_by_muscle: dict[str, int] = {}
    remainder_by_muscle: dict[str, int] = {}
    for muscle_value in desconhecidos:
        base_by_muscle[muscle_value], remainder_by_muscle[muscle_value] = 3, 0
    for muscle in musculos:
        n_slots = slot_count_by_muscle[muscle.value]
        weekly = plano_semanal[muscle]
        base_by_muscle[muscle.value] = weekly // n_slots
        remainder_by_muscle[muscle.value] = weekly % n_slots

    # Substitui o treino ativo: arquiva o que existe (não deleta) e cria o novo.
    for r in db.execute(
        select(Routine).where(Routine.user_id == user.id, Routine.is_archived.is_(False))
    ).scalars():
        r.is_archived = True
    db.flush()

    # TÉCNICA AVANÇADA = DENSIDADE. Ela é o que paga o tempo dos exercícios que
    # o volume mandou acrescentar: a mesma quantidade de séries de trabalho
    # efetivas sai com descanso de 15–40s dentro da série em vez de 60–90s
    # entre séries retas. Ganham técnica:
    #
    #   - o último composto e o último isolado do dia, quando a sessão é CURTA
    #     (os dois porque composto vem sempre antes na ordem: pegar só "o
    #     último exercício" pegaria sempre um isolado e muscle round nunca
    #     apareceria);
    #   - todo exercício ACRESCENTADO pelo preenchimento de volume acima, em
    #     qualquer tamanho de sessão — ele só existe pra fechar o alvo semanal,
    #     então é exatamente onde a densidade tem que entrar.
    #
    # Com teto por sessão: técnica perto da falha em exercício demais é fadiga
    # que não recupera (o próprio texto do rest-pause diz "é pontual, não pra
    # toda sessão"). Não sobrescreve dica já ativa por outro motivo (ex.: platô)
    # nem duplica ao refazer o treino.
    technique_applied: list[str] = []
    # Todo RoutineExercise criado nesta montagem, por exercício (o mesmo
    # exercício pode aparecer em mais de um dia). O teto por técnica é aplicado
    # numa passada só, DEPOIS — ver o bloco "TETO DE SÉRIES" no fim.
    routine_exercises_by_id: dict[int, list[RoutineExercise]] = {}
    is_compound_by_id: dict[int, bool] = {}

    nomes: list[str] = []
    total_ex = 0
    for s in plan.sessions:
        slots = [sl for sl in s.slots if sl.exercise_id is not None]
        if not slots:
            continue
        nome = f"{method.name} — {s.day_label} · {s.focus}"[:100]
        routine = Routine(user_id=user.id, name=nome)
        db.add(routine)
        db.flush()
        for i, sl in enumerate(slots):
            # FAIXA DE REPETIÇÕES E DESCANSO saem do EXERCÍCIO, não do método.
            #
            # Antes `sl.reps` trazia o 8-12 fixo do MethodSpec pra tudo, e o
            # descanso vinha do objetivo da pessoa. Agachamento livre e elevação
            # lateral recebiam a mesma prescrição, o que o manual rejeita: a
            # faixa é consequência da estabilidade, do perfil de resistência, do
            # risco articular e de quem encerra a série (Cap. XI); o descanso, do
            # custo real do movimento (Cap. XV).
            taxon = exercise_taxonomy.taxon_for(
                sl.exercise_name, _muscle_or_none(sl.muscle_group), bool(sl.is_compound)
            )
            rmin, rmax = prescription.rep_band(
                taxon, load_preference=getattr(profile, "load_preference", None)
            )
            descanso = prescription.rest_seconds(
                taxon, goal=goal, limitations=getattr(profile, "limitations", None)
            )
            # Base do volume-alvo do músculo dividido pelas vagas; o resto da
            # divisão vai pro(s) primeiro(s) exercício(s) do músculo na semana.
            sets = base_by_muscle.get(sl.muscle_group, 3)
            if remainder_by_muscle.get(sl.muscle_group, 0) > 0:
                sets += 1
                remainder_by_muscle[sl.muscle_group] -= 1
            # Trava de segurança, não regra de distribuição: depois da poda e do
            # preenchimento acima, o número de vagas já cabe no alvo e a divisão
            # cai naturalmente entre 2 e 3. Ela só morde quando a poda não
            # conseguiu tirar a vaga excedente (região exigida, equilíbrio da
            # semana) — e aí o excesso é assumido, não escondido.
            sets = max(volume_landmarks.PER_EXERCISE_MIN, min(sets, volume_landmarks.PER_EXERCISE_MAX))
            routine_exercise = RoutineExercise(
                routine_id=routine.id, exercise_id=sl.exercise_id, sort_order=i,
                target_sets=sets,
                target_reps_min=max(1, rmin), target_reps_max=max(rmin, rmax),
                rest_seconds=descanso,
                notes=sl.note,
                set_intents=training_brain.set_intents_for(sets, sl.is_compound),
            )
            db.add(routine_exercise)
            routine_exercises_by_id.setdefault(sl.exercise_id, []).append(routine_exercise)
            is_compound_by_id[sl.exercise_id] = bool(sl.is_compound)
            total_ex += 1
        nomes.append(nome)

        candidatos: list = []
        if curto:
            candidatos.append(next((sl for sl in reversed(slots) if sl.is_compound), None))
            candidatos.append(next((sl for sl in reversed(slots) if not sl.is_compound), None))
        candidatos += [sl for sl in slots if sl.exercise_id in ids_extras]

        vistos: set[int] = set()
        aplicadas_na_sessao = 0
        for finisher in candidatos:
            if finisher is None or finisher.exercise_id in vistos:
                continue
            vistos.add(finisher.exercise_id)
            if aplicadas_na_sessao >= _MAX_TECNICAS_POR_SESSAO:
                break
            ja_ativa = db.execute(
                select(CoachingTechniqueCue.id).where(
                    CoachingTechniqueCue.user_id == user.id,
                    CoachingTechniqueCue.exercise_id == finisher.exercise_id,
                    CoachingTechniqueCue.reverted_at.is_(None),
                )
            ).scalar_one_or_none()
            if ja_ativa is not None:
                aplicadas_na_sessao += 1  # já tem técnica: ocupa o mesmo orçamento de fadiga
                continue
            # As MESMAS quatro entradas que a análise de platô e o "aplicar
            # técnica" manual usam (suggest_technique): ponto fraco > tempo por
            # sessão > fase do ciclo > composto/isolado. O montador fixava
            # "intensificacao" e não passava o ponto fraco, então dois caminhos
            # do mesmo coach prescreviam técnicas diferentes pro mesmo
            # exercício — e a fase de acumulação (cluster/myo-reps) nunca era
            # alcançada na montagem, apesar de existir na regra.
            # Quem pediu só série normal não ganha finisher com técnica: o
            # treino cresce por exercício e volume, como o resto do motor já faz.
            if not training_brain.advanced_allowed(profile):
                continue
            try:
                eh_ponto_fraco = MuscleGroup(finisher.muscle_group) in wps
            except ValueError:
                eh_ponto_fraco = False
            tech_key, tech_label, cue_text = training_brain.suggest_technique(
                finisher.is_compound,
                training_brain.training_period(weeks_acc),
                session_length=profile.session_length,
                is_weak_point=eh_ponto_fraco,
            )
            db.add(CoachingTechniqueCue(
                user_id=user.id, finding_key=f"densidade:{finisher.exercise_id}",
                exercise_id=finisher.exercise_id, exercise_name=finisher.exercise_name,
                technique=tech_key, technique_label=tech_label, cue_text=cue_text,
            ))
            technique_applied.append(f"{tech_label} no {finisher.exercise_name}")
            aplicadas_na_sessao += 1
    db.flush()

    # --- TETO DE SÉRIES DE TRABALHO EFETIVAS --------------------------------
    # Uma passada sobre TODAS as dicas de técnica ativas da pessoa — não só as
    # que acabaram de ser criadas. Uma técnica que já vale mais de uma série
    # (rest-pause, myo-reps e muscle round contam como 2) tem que descontar do
    # teto de 3: senão o exercício fica com 3 retas + a técnica valendo 2 = 5
    # séries de trabalho, que é o dobro do permitido.
    #
    # A passada é aqui, e não junto da criação da dica, porque a dica sobrevive
    # a remontagens (ela é por usuário+exercício e nunca é revertida ao refazer
    # o treino). Aplicar só na criação deixava justamente o caso comum de fora:
    # quem já tinha a dica de uma montagem anterior recebia rotina nova sem teto.
    for cue in db.execute(
        select(CoachingTechniqueCue).where(
            CoachingTechniqueCue.user_id == user.id,
            CoachingTechniqueCue.reverted_at.is_(None),
        )
    ).scalars():
        cap = volume_landmarks.per_exercise_max_with_technique(cue.technique)
        for routine_exercise in routine_exercises_by_id.get(cue.exercise_id, []):
            if routine_exercise.target_sets > cap:
                routine_exercise.target_sets = cap
                routine_exercise.set_intents = training_brain.set_intents_for(
                    cap, is_compound_by_id.get(cue.exercise_id, False)
                )
    db.commit()

    technique_note = None
    if technique_applied:
        technique_note = (
            "Marquei fragmentação de série (rende volume com descanso curto dentro da própria série) em "
            + "; ".join(technique_applied) + ". Vê na prévia do treino; dá pra remover em 'O que o coach mudou'."
        )

    weak_labels = [training_brain.WEAK_POINT_LABEL[w] for w in weak_values]
    weak_label = ", ".join(weak_labels) if weak_labels else None

    # A priorização precisa ser VISÍVEL. A queixa não era só que o ponto fraco
    # recebia pouco — era que trocar o ponto fraco não parecia mudar nada. Mesmo
    # depois de consertado o volume, uma diferença que a pessoa não consegue ler
    # continua sendo invisível pra ela. Aqui sai o número, dos dois lados da
    # troca: quanto o prioritário ganhou e quem pagou por isso.
    priority_note = None
    if wps:
        def _label(m: MuscleGroup) -> str:
            return training_brain.WEAK_POINT_LABEL.get(m.value, m.value)

        ganhos = ", ".join(
            f"{_label(m)} {plano_semanal[m]} séries/semana" for m in wps if m in plano_semanal
        )
        financiadores = sorted(
            (m for m in musculos if m not in wps),
            key=lambda m: (-slot_count_by_muscle.get(m.value, 0), m.value),
        )[:3]
        if ganhos:
            priority_note = f"Seu ponto fraco puxa o volume da semana: {ganhos}."
            if financiadores:
                # NÃO reusar o nome `nomes` aqui: ele é a lista de nomes das
                # ROTINAS criadas logo acima, e é o que alimenta "days",
                # "routines" e a mensagem final. Sobrescrever com uma string
                # fazia o coach responder "montei 25 treino(s)" — 25 é o
                # comprimento do texto "Costas, Peito, Quadríceps".
                nomes_financiadores = ", ".join(_label(m) for m in financiadores)
                priority_note += (
                    f" Pra isso eu segurei {nomes_financiadores} em {volume_landmarks.BASE_MIN} séries — "
                    "manter um músculo custa muito menos que fazer ele crescer, e a recuperação "
                    "é do corpo inteiro, não de um grupo por vez."
                )
            priority_note += " Nos dias que treinam seu ponto fraco, ele abre o treino, descansado."
    # A sessão cresceu por um motivo específico — dizer qual, senão a pessoa
    # abre o treino e só vê "ficou mais longo".
    extra_note = None
    if exercicios_extras:
        extra_note = (
            f"Pra fechar seu volume semanal acrescentei {len(exercicios_extras)} exercício(s): "
            + ", ".join(exercicios_extras)
            + ". É outro exercício em vez de mais séries no mesmo — passar do teto de séries por "
            "exercício acumula fadiga sem estímulo novo. O treino cresce ao longo do ciclo e alivia no deload."
        )
    if profile.wants_cardio:
        cardio_note = ("Como você quer cardio, inclua 2× de 20–30 min na semana (esteira, bike ou elíptico), "
                       "de preferência longe dos dias pesados de perna.")
    else:
        cardio_note = training_brain.cardio_warning(goal, profile.wants_cardio)
    period_label = training_brain.PERIODIZATION_LABEL.get(
        training_brain.valid_periodization(profile.periodization), "Automática"
    )
    return {
        "method_name": method.name,
        "author": method.author,
        "days": len(nomes),
        "routines": nomes,
        "total_exercises": total_ex,
        "weak_point_label": weak_label,
        "priority_note": priority_note,
        "session_range": training_brain.session_range_text(profile.session_length),
        "cardio_note": cardio_note,
        "technique_note": technique_note,
        "extra_exercises_note": extra_note,
        "periodization_label": period_label,
        # Resultado da revisão global (as 8 perguntas da regra mestra). O treino
        # aprovado sai com is_coherent=true e lista vazia. Se algo sobrou, sai
        # AQUI em vez de sumir num log — um treino entregue com pendência é algo
        # que eu preciso poder ver, não descobrir por reclamação de usuário.
        "is_coherent": not pendencias,
        "coherence_issues": pendencias,
        "message": f"Pronto — montei {len(nomes)} treino(s) pra {days} dia(s) na semana. "
                   "Já estão nas suas rotinas, é só treinar.",
    }
