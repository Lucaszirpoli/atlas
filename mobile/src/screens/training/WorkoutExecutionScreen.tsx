import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation, useRoute } from "@react-navigation/native";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { listWorkoutOverlays, type WorkoutOverlay } from "../../api/coaching";
import { CoachOverlayBlock, DeloadBanner } from "../../components/CoachOverlay";
import {
  getRoutine,
  swapRoutineExercise,
  type Routine,
  type RoutineExercise,
} from "../../api/routines";
import {
  completeWorkoutSession,
  discardWorkoutSession,
  getAvgWorkoutDuration,
  getWorkoutPreview,
  logSet,
  type BlockStatus,
  type ExercisePrefill,
  type SetType,
} from "../../api/workoutSessions";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { DurationCheckModal } from "../../components/DurationCheckModal";
import { ExerciseThumb } from "../../components/ExerciseThumb";
import { HelpDot } from "../../components/HelpDot";
import { InfoDialog } from "../../components/InfoDialog";
import { OptionButton } from "../../components/OptionButton";
import { RestTimerOverlay } from "../../components/RestTimerOverlay";
import { useActiveWorkout } from "../../context/ActiveWorkoutContext";
import { useTheme } from "../../theme/ThemeProvider";
import { fmtKg } from "../../utils/format";
import { mensagemDeErro } from "../../utils/errorMessage";
import {
  BLOCK_STATUS_LABEL,
  buildDisplayItems,
  expandTechnique,
  prescriptionFor,
  type SetRow,
} from "./techniqueSets";
import { clearDraft, loadDraft, purgeOldDrafts, saveDraft } from "./workoutDraft";

const SET_TYPE_LABELS: Record<SetType, string> = {
  warmup: "Aquecimento",
  straight: "Válida",
  feeder: "Feeder",
  drop_set: "Drop-set",
  rest_pause: "Rest-pause",
  myo_reps: "Myo-reps",
  cluster_set: "Cluster set",
  to_failure: "Até a falha",
  technical_failure: "Falha técnica",
  tempo: "Tempo controlado",
  eccentric_emphasis: "Excêntrica",
  pre_exhaustion: "Pré-exaustão",
  superset: "Superset",
  biset: "Bi-set",
  triset: "Tri-set",
  circuit: "Circuito",
};
const SET_TYPE_ORDER = Object.keys(SET_TYPE_LABELS) as SetType[];

const SET_LETTER_HELP_TEXT =
  "A = Aquecimento: a primeira série, bem leve (25% da carga de trabalho), só pra preparar a articulação e o músculo — não é série de esforço.\n\n" +
  "P = Feeder: a segunda série, um pouco mais pesada (50% da carga de trabalho), pra chegar afiado na primeira série de trabalho — também não conta como esforço.\n\n" +
  "1, 2, 3... = Séries de trabalho: as séries que valem, com o peso e reps que você realmente treina.\n\n" +
  "F = Até a falha: a última série de trabalho, levada até não dar mais pra fazer outra rep com boa forma (RIR 0).";

// Badge da série: toque cicla entre os 4 tipos "rápidos" (normal → A → P → F).
// As demais técnicas (drop-set, superset etc.) continuam só no "mais opções".
const QUICK_TYPE_CYCLE: SetType[] = ["straight", "warmup", "feeder", "to_failure"];
const QUICK_TYPE_LETTER: Partial<Record<SetType, string>> = {
  warmup: "A",
  feeder: "P",
  to_failure: "F",
};
function nextQuickType(current: SetType): SetType {
  const idx = QUICK_TYPE_CYCLE.indexOf(current);
  return QUICK_TYPE_CYCLE[(idx + 1) % QUICK_TYPE_CYCLE.length] ?? "warmup";
}

/** As linhas de série de UM exercício: rampa de preparação (do histórico) +
 * séries de trabalho pré-preenchidas + a estrutura da técnica avançada quando
 * o coach prescreveu uma.
 *
 * Vive fora do componente porque agora tem DOIS chamadores: a montagem inicial
 * da tela e a troca de exercício no meio do treino (que precisa reconstruir só
 * a vaga trocada, com o histórico do exercício que entrou). */
function linhasDoExercicio(
  routineExercise: { target_sets: number; set_intents?: (string | null)[] | null },
  pre: ExercisePrefill | undefined,
  overlays: WorkoutOverlay[],
  exerciseId: number
): SetRow[] {
  const prepRows: SetRow[] = (pre?.warmup_feeder ?? []).map((w) => ({
    weight: w.weight_kg != null ? String(w.weight_kg) : "",
    reps: String(w.reps_max),
    completed: false,
    setType: w.kind,
    rpe: "",
    rir: "",
    showMore: false,
    role: "prep" as const,
  }));
  const workRows: SetRow[] = Array.from({ length: routineExercise.target_sets }, (_, i) => {
    const previous = pre?.sets[i];
    // Intenção que o coach definiu ao montar a rotina (até a falha) já vem
    // pré-marcada no badge, com o RIR sugerido pro momento do ciclo — a pessoa
    // não precisa lembrar de marcar na hora. Rotina sem intenção (manual) cai
    // no normal.
    const isFailure = routineExercise.set_intents?.[i] === "to_failure";
    return {
      // Arredonda pro input não mostrar ruído de float (54.599999… → "54.6").
      weight: previous ? String(Math.round(previous.weight_kg * 10) / 10) : "",
      reps: previous ? String(previous.reps) : "",
      completed: false,
      setType: (isFailure ? "to_failure" : "straight") as SetType,
      rpe: "",
      rir: isFailure ? "0" : String(pre?.suggested_rir ?? 2),
      showMore: false,
      previous,
      role: "work" as const,
    };
  });

  // Técnica avançada prescrita pelo coach: a última série de trabalho vira a
  // estrutura do método (ativação + blocos, ou quedas de carga).
  const tech = prescriptionFor(overlays, exerciseId);
  const finais = tech
    ? expandTechnique(workRows, tech, workRows[workRows.length - 1]?.weight ?? "")
    : workRows;
  return [...prepRows, ...finais];
}

const RIR_OPTIONS = [4, 3, 2, 1, 0];

// Cor de cada status de bloco — verde fechou, âmbar veio pela metade,
// cinza-vermelho não saiu, neutro ainda não foi feito.
const BLOCK_STATUS_ICON: Record<BlockStatus, keyof typeof Ionicons.glyphMap> = {
  completo: "checkmark-circle",
  parcial: "remove-circle",
  nao_concluido: "close-circle",
};

export function WorkoutExecutionScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { active, endWorkout, setOnWorkoutScreen } = useActiveWorkout();
  const insets = useSafeAreaInsets();
  const route = useRoute<any>();

  // Enquanto esta tela está em foco, o indicador flutuante some (a pessoa já
  // está no treino); ao sair (minimizar), ele reaparece nas outras telas.
  useFocusEffect(
    useCallback(() => {
      setOnWorkoutScreen(true);
      return () => setOnWorkoutScreen(false);
    }, [setOnWorkoutScreen])
  );
  const { sessionId, routineId, prefill: prefillInicial } = route.params as {
    sessionId: number;
    routineId: number;
    prefill: ExercisePrefill[];
  };

  // O prefill deixou de ser fixo: trocar um exercício no meio do treino traz
  // o histórico do exercício que ENTROU (cargas, rampa de aquecimento, RIR).
  const [prefill, setPrefill] = useState<ExercisePrefill[]>(prefillInicial);
  const [routine, setRoutine] = useState<Routine | null>(null);
  const [overlays, setOverlays] = useState<WorkoutOverlay[]>([]);
  // Todos os exercícios ficam na tela ao mesmo tempo (rolagem única) — sem
  // "próximo exercício". setsByExercise[i] são as séries do exercício i.
  const [setsByExercise, setSetsByExercise] = useState<SetRow[][]>([]);
  const [restSeconds, setRestSeconds] = useState<number | null>(null);
  const [isCompleting, setIsCompleting] = useState(false);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  // Quando o treino durou muito mais que a média, guarda os minutos medidos pra
  // a pessoa confirmar/corrigir antes de salvar.
  const [durationCheck, setDurationCheck] = useState<number | null>(null);
  // Montagem concluída (rotina + overlays + rascunho). Só depois disso o
  // rascunho passa a ser gravado — senão o estado vazio inicial sobrescreveria
  // o rascunho que acabou de ser lido.
  const [pronto, setPronto] = useState(false);
  const [restaurado, setRestaurado] = useState(false);
  // Séries em gravação, por "exercício:série". Enquanto está aqui, o ✓ ignora
  // novos toques — é o que impede o toque duplo de registrar a série 2 vezes.
  const [salvando, setSalvando] = useState<Set<string>>(new Set());
  // Qual bloco está aberto por grupo de técnica ("exercício:índice-da-ativação"
  // -> índice do bloco aberto). Compacto de propósito (ajuste pós-v36, item 3):
  // em vez de abrir B1, B2 e B3 juntos, só o bloco tocado mostra os campos.
  const [openBlock, setOpenBlock] = useState<Record<string, number | null>>({});
  function toggleBlock(groupKey: string, blockIdx: number) {
    setOpenBlock((prev) => ({ ...prev, [groupKey]: prev[groupKey] === blockIdx ? null : blockIdx }));
  }

  // Troca de exercício DURANTE o treino: qual vaga a pessoa pediu pra trocar
  // (diálogo aberto), qual está trocando agora, e o que o coach respondeu.
  const [trocando, setTrocando] = useState<{ re: RoutineExercise; idx: number } | null>(null);
  const [emTroca, setEmTroca] = useState<number | null>(null);
  const [resultadoTroca, setResultadoTroca] = useState<{ titulo: string; texto: string } | null>(null);

  // Monta a tela: rotina + overlays do coach juntos, porque a TÉCNICA prescrita
  // muda a estrutura das séries — montar primeiro e corrigir depois faria as
  // linhas piscarem. Se houver rascunho desta sessão, ele vence (a pessoa já
  // digitou coisas ali).
  useEffect(() => {
    let cancelado = false;
    (async () => {
      const [r, ovs, draft] = await Promise.all([
        getRoutine(routineId),
        listWorkoutOverlays().catch(() => [] as WorkoutOverlay[]),
        loadDraft(sessionId),
      ]);
      if (cancelado) return;
      setRoutine(r);
      setOverlays(ovs);

      if (draft && draft.setsByExercise.length === r.exercises.length) {
        setSetsByExercise(draft.setsByExercise);
        setRestaurado(true);
        setPronto(true);
        return;
      }

      setSetsByExercise(
        r.exercises.map((re) =>
          linhasDoExercicio(
            re,
            prefill.find((p) => p.exercise_id === re.exercise_id),
            ovs,
            re.exercise_id
          )
        )
      );
      setPronto(true);
    })();
    return () => {
      cancelado = true;
    };
  }, [routineId, sessionId]);

  // Grava o rascunho a CADA alteração. É o que faz sair da aba, minimizar ou
  // bloquear a tela deixarem de custar os números do treino (spec §8.2).
  useEffect(() => {
    if (!pronto || setsByExercise.length === 0) return;
    saveDraft(sessionId, setsByExercise);
  }, [pronto, sessionId, setsByExercise]);

  if (!routine || setsByExercise.length === 0) {
    return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  }

  const deload = overlays.find((o) => o.kind === "deload");
  const overlaysFor = (exerciseId: number) => overlays.filter((o) => o.exercise_id === exerciseId);

  const totalSets = setsByExercise.reduce((sum, rows) => sum + rows.length, 0);
  const totalCompleted = setsByExercise.reduce((sum, rows) => sum + rows.filter((s) => s.completed).length, 0);

  function updateSet(exerciseIndex: number, setIdx: number, patch: Partial<SetRow>) {
    setSetsByExercise((prev) =>
      prev.map((rows, i) =>
        i === exerciseIndex ? rows.map((row, j) => (j === setIdx ? { ...row, ...patch } : row)) : rows
      )
    );
  }

  /** Troca um exercício COM O TREINO EM ANDAMENTO. Quem escolhe o substituto é
   * o servidor (mesmas regras da prévia); aqui só se diz qual vaga sai.
   *
   * A vaga já registrada não pode ser trocada: as séries confirmadas ficaram
   * gravadas no exercício ANTIGO (histórico é append-only), então a partir daí
   * a sessão teria duas metades de exercícios diferentes numa vaga só — e o
   * pré-preenchido da próxima vez sairia do lugar errado. Nesse caso a pessoa
   * é avisada, em vez de a troca falhar em silêncio. */
  async function trocarExercicio(alvo: RoutineExercise, idx: number) {
    setEmTroca(alvo.id);
    try {
      const r = await swapRoutineExercise(routineId, alvo.id);
      const novaRotina = r.routine;
      setRoutine(novaRotina);
      // O histórico é POR EXERCÍCIO: sem recarregar o prefill, a vaga nova
      // mostraria a carga do exercício que acabou de sair.
      const novoPrefill = await getWorkoutPreview(routineId).catch(() => prefill);
      setPrefill(novoPrefill);
      const nova = novaRotina.exercises[idx];
      if (nova) {
        setSetsByExercise((prev) =>
          prev.map((rows, i) =>
            i === idx
              ? linhasDoExercicio(
                  nova,
                  novoPrefill.find((p) => p.exercise_id === nova.exercise_id),
                  overlays,
                  nova.exercise_id
                )
              : rows
          )
        );
      }
      setResultadoTroca({ titulo: `Entrou ${r.exercicio_novo}`, texto: r.motivo });
    } catch (err: any) {
      setResultadoTroca({
        titulo: "Não deu pra trocar",
        texto: mensagemDeErro(err, "Tente de novo daqui a pouco."),
      });
    } finally {
      setEmTroca(null);
    }
  }

  // Rest-pause (técnica "singles"): a carga é UMA só pra todas as repetições
  // avulsas — só existe um campo "Carga" na tela, então digitar nele precisa
  // preencher o peso de toda a fileira de una vez (senão confirmar R2 em
  // diante travava por peso vazio).
  function updateWeightAcrossGroup(exerciseIndex: number, indices: number[], weight: string) {
    setSetsByExercise((prev) =>
      prev.map((rows, i) =>
        i === exerciseIndex ? rows.map((row, j) => (indices.includes(j) ? { ...row, weight } : row)) : rows
      )
    );
  }

  async function handleConfirmSet(exerciseIndex: number, setIdx: number) {
    const chave = `${exerciseIndex}:${setIdx}`;
    const row = setsByExercise[exerciseIndex][setIdx];
    // UM toque = UMA ação (spec §8.3). Sem esta guarda, dois toques rápidos
    // disparavam duas chamadas antes da primeira responder e a série entrava
    // DUPLICADA no histórico. Já confirmada também não repete.
    if (row.completed || salvando.has(chave)) return;

    const routineExercise = routine!.exercises[exerciseIndex];
    const weightNum = Number(row.weight);
    const repsNum = Number(row.reps);
    if (!row.weight || !row.reps || Number.isNaN(weightNum) || Number.isNaN(repsNum)) {
      Alert.alert("Preencha peso e repetições");
      return;
    }
    // Um mini-set precisa do status antes de valer — é o campo que substitui o
    // RIR nos blocos, e sem ele o registro não diz nada.
    if (row.role === "block" && !row.blockStatus) {
      Alert.alert("Como foi esse bloco?", "Toque em Completo, Parcial ou Não saiu antes de confirmar.");
      return;
    }

    setSalvando((s) => new Set(s).add(chave));
    try {
      await logSet(sessionId, {
        exercise_id: routineExercise.exercise_id,
        exercise_sort_order: exerciseIndex,
        set_number: setIdx + 1,
        weight_kg: weightNum,
        reps: repsNum,
        set_type: row.setType,
        rpe: row.rpe ? Number(row.rpe) : null,
        // Nos blocos o RIR não se aplica: quem conta a história é o status.
        rir: row.role === "block" ? null : row.rir ? Number(row.rir) : null,
        block_index: row.blockIndex ?? null,
        block_status: row.blockStatus ?? null,
      });
      updateSet(exerciseIndex, setIdx, { completed: true });
      // Dentro de uma técnica o descanso é o CURTO do método (15-40s), não o
      // descanso normal entre séries — é isso que faz a técnica ser a técnica.
      setRestSeconds(row.restAfterS ?? routineExercise.rest_seconds);
    } catch (err: any) {
      Alert.alert("Não foi possível registrar a série", mensagemDeErro(err, "Tente novamente."));
    } finally {
      setSalvando((s) => {
        const n = new Set(s);
        n.delete(chave);
        return n;
      });
    }
  }

  function handleAddSet(exerciseIndex: number) {
    setSetsByExercise((prev) =>
      prev.map((rows, i) =>
        i === exerciseIndex
          ? [
              ...rows,
              {
                weight: "",
                reps: "",
                completed: false,
                setType: "straight" as SetType,
                rpe: "",
                rir: "",
                showMore: false,
                role: "work" as const,
                // Marca de onde veio — só uma série ADICIONADA aqui (não
                // prescrita pela rotina/coach) pode ser removida depois. Tirar
                // uma série que o coach mandou mudaria o treino sem passar por
                // "Alterar respostas", que é onde essa decisão mora de verdade.
                manuallyAdded: true,
              },
            ]
          : rows
      )
    );
  }

  // Só desfaz uma série que a PRÓPRIA pessoa acrescentou e que ainda não foi
  // registrada — depois de confirmada ela virou histórico (regra 4: histórico
  // é append-only, não existe endpoint pra apagar um log). Antes de confirmar
  // é só um rascunho na tela, então tirar da lista é seguro.
  function handleRemoveSet(exerciseIndex: number, setIdx: number) {
    setSetsByExercise((prev) =>
      prev.map((rows, i) => (i === exerciseIndex ? rows.filter((_, j) => j !== setIdx) : rows))
    );
  }

  // Ao concluir: se o treino durou +30% acima da média normal da pessoa (ex:
  // deixou minimizado e esqueceu), abre a checagem pra confirmar/corrigir o
  // tempo antes de salvar. Senão, salva direto.
  async function handleFinishWorkout() {
    const startedAt = active?.startedAt;
    if (startedAt) {
      const elapsedMin = (Date.now() - startedAt) / 60000;
      try {
        const { avg_minutes } = await getAvgWorkoutDuration();
        if (avg_minutes != null && elapsedMin > avg_minutes * 1.3) {
          setDurationCheck(Math.round(elapsedMin));
          return;
        }
      } catch {
        // sem média disponível — segue e salva normal
      }
    }
    await finishWith(undefined);
  }

  async function finishWith(durationMinutes?: number) {
    setIsCompleting(true);
    try {
      const summary = await completeWorkoutSession(sessionId, durationMinutes);
      // Treino concluído: agora sim o rascunho pode ir embora.
      await clearDraft(sessionId);
      purgeOldDrafts();
      endWorkout(); // não está mais "em andamento" — some o indicador flutuante
      setDurationCheck(null);
      navigation.replace("WorkoutSummary", { summary });
    } finally {
      setIsCompleting(false);
    }
  }

  async function handleDiscard() {
    setConfirmDiscard(false);
    try {
      await discardWorkoutSession(sessionId);
    } catch {
      // mesmo se falhar no servidor, tira o treino da tela
    }
    // Descarte é explícito e confirmado — é o outro caso em que o rascunho sai.
    await clearDraft(sessionId);
    endWorkout();
    // reset, e não navigate: quando o treino foi aberto de fora da lista (do
    // dashboard, de um atalho), "RoutineList" não está abaixo na pilha — o
    // navigate EMPURRAVA uma lista nova por cima e a tela do treino descartado
    // continuava atrás dela. A seta de voltar devolvia a pessoa pro treino que
    // ela acabou de descartar, como se nada tivesse acontecido. O reset apaga
    // a pilha: o treino descartado deixa de existir pra navegação.
    navigation.reset({ index: 0, routes: [{ name: "RoutineList" }] });
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 340 + insets.bottom }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="interactive"
      >
        <Text style={[type.h1, { color: colors.textPrimary }]}>{routine.name}</Text>
        <View style={{ flexDirection: "row", alignItems: "center", marginTop: spacing.xs, marginBottom: spacing.md }}>
          <View style={{ flex: 1, height: 6, borderRadius: 3, backgroundColor: colors.border, overflow: "hidden" }}>
            <View
              style={{
                width: totalSets > 0 ? `${(totalCompleted / totalSets) * 100}%` : "0%",
                height: "100%",
                backgroundColor: colors.secondary,
              }}
            />
          </View>
          <Text style={[type.caption, { color: colors.textSecondary, marginLeft: spacing.sm }]}>
            {totalCompleted}/{totalSets} séries
          </Text>
        </View>

        {/* Voltou pro treino e estava tudo lá — vale dizer, porque a pessoa
            saiu esperando ter perdido (era o que acontecia antes). */}
        {restaurado ? (
          <TouchableOpacity
            activeOpacity={0.8}
            onPress={() => setRestaurado(false)}
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 8,
              backgroundColor: colors.success + "16",
              borderRadius: radius.card,
              padding: spacing.sm,
              marginBottom: spacing.md,
            }}
          >
            <Ionicons name="save" size={15} color={colors.success} />
            <Text style={[type.caption, { color: colors.textSecondary, flex: 1, lineHeight: 17 }]}>
              Continuei de onde você parou — cargas, reps e séries feitas estão como você deixou.
            </Text>
            <Ionicons name="close" size={14} color={colors.textSecondary} />
          </TouchableOpacity>
        ) : null}

        {deload ? <DeloadBanner overlay={deload} /> : null}

        {routine.exercises.map((routineExercise, exerciseIndex) => {
          const sets = setsByExercise[exerciseIndex];
          const completedCount = sets.filter((s) => s.completed).length;
          return (
            <View key={routineExercise.id} style={{ marginBottom: spacing.xl }}>
              <Text style={[type.caption, { color: colors.secondary, fontWeight: "700", letterSpacing: 1 }]}>
                EXERCÍCIO {exerciseIndex + 1} DE {routine.exercises.length}
              </Text>
              {/* Foto pequena (tipo ícone) ao lado do nome; toque amplia. */}
              <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: 4 }}>
                <ExerciseThumb
                  url={routineExercise.exercise.video_url}
                  name={routineExercise.exercise.name}
                  muscleGroup={routineExercise.exercise.primary_muscle_group}
                  equipment={routineExercise.exercise.equipment}
                />
                <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>{routineExercise.exercise.name}</Text>

                {/* TROCAR EXERCÍCIO — a mesma setinha da prévia, agora também
                    com o treino em andamento: a máquina pode estar ocupada, o
                    ombro pode reclamar na primeira série, e nada disso é hora
                    de sair do treino pra editar a rotina. Some depois que a
                    primeira série da vaga é registrada (ver trocarExercicio). */}
                {completedCount > 0 ? null : emTroca === routineExercise.id ? (
                  <View style={{ width: 38, height: 38, alignItems: "center", justifyContent: "center" }}>
                    <ActivityIndicator color={colors.primary} />
                  </View>
                ) : (
                  <TouchableOpacity
                    onPress={() => setTrocando({ re: routineExercise, idx: exerciseIndex })}
                    disabled={emTroca !== null}
                    activeOpacity={0.7}
                    accessibilityRole="button"
                    accessibilityLabel={`Trocar ${routineExercise.exercise.name} por outro exercício`}
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    style={{
                      width: 38,
                      height: 38,
                      borderRadius: radius.pill,
                      alignItems: "center",
                      justifyContent: "center",
                      backgroundColor: colors.surfaceAlt,
                      opacity: emTroca !== null ? 0.4 : 1,
                    }}
                  >
                    <Ionicons name="swap-horizontal-outline" size={19} color={colors.textSecondary} />
                  </TouchableOpacity>
                )}
              </View>
              <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.sm, marginBottom: spacing.sm }}>
                <Meta icon="repeat" text={`${routineExercise.target_sets}x ${routineExercise.target_reps_min}${routineExercise.target_reps_max ? `-${routineExercise.target_reps_max}` : ""} reps`} />
                <Meta icon="timer-outline" text={`${routineExercise.rest_seconds}s descanso`} />
                <Meta icon="checkmark-done" text={`${completedCount}/${sets.length} feitas`} />
              </View>

              {/* Carga herdada de uma troca de exercício com "manter registros"
                  (spec §8.1) — a origem aparece com clareza, senão os números
                  pré-preenchidos parecem ter saído do nada. */}
              {prefill.find((p) => p.exercise_id === routineExercise.exercise_id)?.inherited_from_name ? (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: spacing.sm }}>
                  <Ionicons name="git-branch-outline" size={13} color={colors.textSecondary} />
                  <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]} numberOfLines={2}>
                    Cargas vindas de{" "}
                    {prefill.find((p) => p.exercise_id === routineExercise.exercise_id)?.inherited_from_name} — você
                    escolheu manter os registros na troca.
                  </Text>
                </View>
              ) : null}

              {/* Progressão aplicada pelo coach (ajuste pós-v36, item 9): o peso
                  abaixo já É o novo, sugerido — não é só um lembrete. Assim que
                  esta série for registrada de verdade, vira o novo "anterior". */}
              {prefill.find((p) => p.exercise_id === routineExercise.exercise_id)?.suggested_by_coach ? (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: spacing.sm }}>
                  <Ionicons name="trending-up-outline" size={13} color={colors.primary} />
                  <Text style={[type.caption, { color: colors.primary, fontWeight: "700", flex: 1 }]} numberOfLines={2}>
                    Carga já ajustada pelo coach — pré-preenchida abaixo.
                  </Text>
                </View>
              ) : null}

              {/* Overlays do coach neste exercício (técnica / subir carga /
                  troca). Só leitura aqui — desfazer é no Coaching ou na prévia.
                  Técnica com estrutura própria (rest-pause, myo-reps, muscle
                  round, cluster, drop-set) já ganha o cabeçalho dela mais
                  embaixo (TechniqueHeader), junto das séries que ela gerou —
                  repetir o card aqui em cima duplicava o mesmo aviso. Só as
                  técnicas "cue only" (ex.: superset, que não muda a série
                  deste exercício) continuam aparecendo só aqui. */}
              {overlaysFor(routineExercise.exercise_id)
                .filter((o) => !(o.kind === "technique" && prescriptionFor(overlays, routineExercise.exercise_id)))
                .map((o) => (
                  <CoachOverlayBlock key={`${o.source}:${o.id}`} overlay={o} />
                ))}

              {/* Cabeçalho da tabela — Série / Anterior / kg / Reps / ✓ */}
              <View style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: spacing.sm, marginBottom: spacing.xs }}>
                {/* Sem largura fixa aqui: "Série" + o ponto de interrogação juntos
                    passavam dos 34px da coluna do badge embaixo e ficavam
                    sobrepostos na letra (A/P/F) da série. */}
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <Text style={[type.caption, { color: colors.textSecondary }]}>Série</Text>
                  <HelpDot title="Tipos de série" text={SET_LETTER_HELP_TEXT} />
                </View>
                <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]}>Anterior</Text>
                <Text style={[type.caption, { color: colors.textSecondary, width: 56, textAlign: "center" }]}>kg</Text>
                <Text style={[type.caption, { color: colors.textSecondary, width: 56, textAlign: "center", marginLeft: 6 }]}>Reps</Text>
                <View style={{ width: 44, marginLeft: spacing.xs }} />
              </View>

              {buildDisplayItems(sets).map((item) => {
                if (item.kind === "single") {
                  const { idx, row } = item;
                  const letter = QUICK_TYPE_LETTER[row.setType];
                  // Numeração só conta séries de TRABALHO (sem letra) — a
                  // rampa de aquecimento/feeder na frente não desloca "1, 2, 3...".
                  const workNumber =
                    sets.slice(0, idx).filter((r) => !QUICK_TYPE_LETTER[r.setType] && r.role === "work").length + 1;
                  const badgeColor = row.setType === "to_failure" ? colors.danger : letter ? colors.warning : undefined;
                  const chave = `${exerciseIndex}:${idx}`;
                  return (
                    <Card
                      key={idx}
                      padded={false}
                      style={{
                        marginBottom: spacing.sm,
                        borderWidth: 1.5,
                        borderColor: row.completed ? colors.secondary : "transparent",
                      }}
                    >
                      <View style={{ padding: spacing.sm }}>
                        <View style={{ flexDirection: "row", alignItems: "center" }}>
                          {/* Badge da série — toque cicla normal → A (aquecimento) →
                              P (preparatória) → F (falha) → normal. */}
                          <TouchableOpacity
                            onPress={() => updateSet(exerciseIndex, idx, { setType: nextQuickType(row.setType) })}
                            hitSlop={8}
                            style={{
                              width: 30,
                              height: 30,
                              borderRadius: 15,
                              backgroundColor: badgeColor ? badgeColor + "26" : colors.surfaceAlt,
                              alignItems: "center",
                              justifyContent: "center",
                            }}
                          >
                            <Text style={[type.caption, { color: badgeColor ?? colors.textSecondary, fontWeight: "800" }]}>
                              {letter ?? workNumber}
                            </Text>
                          </TouchableOpacity>

                          <View style={{ flex: 1, marginLeft: spacing.sm }}>
                            {row.previous ? (
                              <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
                                {fmtKg(row.previous.weight_kg)}kg × {row.previous.reps}
                              </Text>
                            ) : (
                              <Text style={[type.caption, { color: colors.textSecondary }]}>primeira vez</Text>
                            )}
                          </View>

                          <SetInput compact value={row.weight} onChangeText={(v) => updateSet(exerciseIndex, idx, { weight: v })} />
                          <Text style={[type.body, { color: colors.textSecondary, marginHorizontal: 4 }]}>×</Text>
                          <SetInput compact value={row.reps} onChangeText={(v) => updateSet(exerciseIndex, idx, { reps: v })} />
                          <ConfirmCheck
                            completed={row.completed}
                            saving={salvando.has(chave)}
                            onPress={() => handleConfirmSet(exerciseIndex, idx)}
                          />
                          {/* Só a série ADICIONADA aqui ("+ série extra") e
                              ainda não registrada pode ser removida — é o
                              desfazer de "toquei demais no botão". */}
                          {row.manuallyAdded && !row.completed ? (
                            <TouchableOpacity
                              onPress={() => handleRemoveSet(exerciseIndex, idx)}
                              hitSlop={8}
                              style={{ marginLeft: spacing.xs, padding: 4 }}
                            >
                              <Ionicons name="trash-outline" size={18} color={colors.textSecondary} />
                            </TouchableOpacity>
                          ) : null}
                        </View>

                        {/* RIR — sempre visível, quick-select. Não se aplica a
                            aquecimento/feeder (séries submáximas de preparação). */}
                        {row.setType !== "warmup" && row.setType !== "feeder" ? (
                          <RirRow value={row.rir} onSelect={(v) => updateSet(exerciseIndex, idx, { rir: v })} />
                        ) : null}

                        <TouchableOpacity
                          onPress={() => updateSet(exerciseIndex, idx, { showMore: !row.showMore })}
                          style={{ flexDirection: "row", alignItems: "center", marginTop: spacing.xs, marginLeft: 38 }}
                        >
                          <Text style={[type.caption, { color: colors.primary, fontWeight: "600" }]}>
                            {row.showMore ? "Menos opções" : "Mais opções"}
                          </Text>
                          <Ionicons
                            name={row.showMore ? "chevron-up" : "chevron-down"}
                            size={13}
                            color={colors.primary}
                            style={{ marginLeft: 3 }}
                          />
                        </TouchableOpacity>

                        {row.showMore ? (
                          <View style={{ marginTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.sm }}>
                            <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
                              <Text style={[type.caption, { color: colors.textSecondary }]}>Técnica avançada</Text>
                              <HelpDot
                                title="Técnica avançada"
                                text={
                                  "Deixe em 'Válida' se for uma série normal. As demais são técnicas avançadas: " +
                                  "Drop-set (reduzir o peso e continuar sem descanso), Rest-pause (pausas curtas dentro da série), " +
                                  "Myo-reps, Superset, etc. Não é obrigatório marcar nada — o tipo básico (normal/aquecimento/" +
                                  "preparatória/falha) já fica no número da série, ali em cima."
                                }
                              />
                            </View>
                            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                              <View style={{ flexDirection: "row", gap: spacing.xs }}>
                                {SET_TYPE_ORDER.map((st) => (
                                  <OptionButton
                                    key={st}
                                    compact
                                    label={SET_TYPE_LABELS[st]}
                                    selected={row.setType === st}
                                    onPress={() => updateSet(exerciseIndex, idx, { setType: st })}
                                  />
                                ))}
                              </View>
                            </ScrollView>
                            <View style={{ flexDirection: "row", alignItems: "center", marginTop: spacing.sm }}>
                              <Text style={[type.caption, { color: colors.textSecondary }]}>RPE (opcional)</Text>
                              <HelpDot
                                title="RPE"
                                text="Quão pesada a série foi, de 0 a 10 (10 = esforço máximo). É outra forma de medir o esforço, além do RIR — preencha só se quiser acompanhar isso."
                              />
                            </View>
                            <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.xs }}>
                              <SetInput label="RPE" value={row.rpe} onChangeText={(v) => updateSet(exerciseIndex, idx, { rpe: v })} />
                            </View>
                          </View>
                        ) : null}
                      </View>
                    </Card>
                  );
                }

                // Técnica avançada: ativação + blocos/quedas viram UM cartão
                // compacto (ajuste pós-v36, item 3). Sem "Mais opções" — a
                // técnica já foi prescrita pelo coach, não há o que escolher.
                const { activationIdx, activation, blocks } = item;
                const groupKey = `${exerciseIndex}:${activationIdx}`;
                const abertoIdx = openBlock[groupKey] ?? null;
                const aberto = blocks.find((b) => b.idx === abertoIdx) ?? null;
                const prescricao = prescriptionFor(overlays, routineExercise.exercise_id);
                const chaveAtivacao = `${exerciseIndex}:${activationIdx}`;

                // Rest-pause: N repetições AVULSAS da MESMA carga, uma de cada
                // vez — não tem "bloco" (não faz sentido perguntar se uma
                // repetição saiu "completa/parcial"), então não usa o cartão
                // de Ativação+RIR+BLOCOS genérico abaixo. Só existe UM campo de
                // carga (a técnica não muda o peso entre repetições) e uma
                // fileira de toques — tocar em Rn já é confirmar aquela rep.
                if (prescricao?.form === "singles") {
                  const todas = [{ idx: activationIdx, row: activation }, ...blocks];
                  const feitas = todas.filter((r) => r.row.completed).length;
                  const indicesDoGrupo = todas.map((r) => r.idx);
                  return (
                    <React.Fragment key={`tec-${activationIdx}`}>
                      <TechniqueHeader label={prescricao.label} cue={prescricao.cue} />
                      <Card
                        padded={false}
                        style={{ marginBottom: spacing.sm, borderWidth: 1.5, borderColor: colors.primary + "3A" }}
                      >
                        <View style={{ padding: spacing.sm }}>
                          <View style={{ flexDirection: "row", alignItems: "center" }}>
                            <View
                              style={{
                                width: 30, height: 30, borderRadius: 15,
                                backgroundColor: colors.primary + "22",
                                alignItems: "center", justifyContent: "center",
                              }}
                            >
                              <Ionicons name="flash" size={15} color={colors.primary} />
                            </View>
                            <Text style={[type.caption, { color: colors.primary, fontWeight: "700", flex: 1, marginLeft: spacing.sm }]}>
                              Carga · {feitas}/{todas.length} repetições
                            </Text>
                            <SetInput
                              compact
                              value={activation.weight}
                              onChangeText={(v) => updateWeightAcrossGroup(exerciseIndex, indicesDoGrupo, v)}
                            />
                          </View>

                          <View style={{ flexDirection: "row", alignItems: "center", flexWrap: "wrap", marginTop: spacing.sm, gap: 6 }}>
                            {todas.map(({ idx, row }, i) => (
                              <RepChip
                                key={idx}
                                number={i + 1}
                                completed={row.completed}
                                saving={salvando.has(`${exerciseIndex}:${idx}`)}
                                disabled={!row.weight}
                                onPress={() => handleConfirmSet(exerciseIndex, idx)}
                              />
                            ))}
                          </View>
                        </View>
                      </Card>
                    </React.Fragment>
                  );
                }

                return (
                  <React.Fragment key={`tec-${activationIdx}`}>
                    <TechniqueHeader label={prescricao?.label ?? "Técnica avançada"} cue={prescricao?.cue ?? ""} />
                    <Card
                      padded={false}
                      style={{ marginBottom: spacing.sm, borderWidth: 1.5, borderColor: colors.primary + "3A" }}
                    >
                      <View style={{ padding: spacing.sm }}>
                        {/* Ativação / série principal */}
                        <View style={{ flexDirection: "row", alignItems: "center" }}>
                          <View
                            style={{
                              width: 30, height: 30, borderRadius: 15,
                              backgroundColor: colors.primary + "22",
                              alignItems: "center", justifyContent: "center",
                            }}
                          >
                            <Ionicons name="flash" size={15} color={colors.primary} />
                          </View>
                          <View style={{ flex: 1, marginLeft: spacing.sm }}>
                            <Text style={[type.caption, { color: colors.primary, fontWeight: "700" }]} numberOfLines={1}>
                              {activation.blockLabel}
                            </Text>
                          </View>
                          <SetInput
                            compact
                            value={activation.weight}
                            onChangeText={(v) => updateSet(exerciseIndex, activationIdx, { weight: v })}
                          />
                          <Text style={[type.body, { color: colors.textSecondary, marginHorizontal: 4 }]}>×</Text>
                          {activation.repsLocked ? (
                            <View
                              style={{
                                width: 56, height: 44, borderRadius: radius.button,
                                backgroundColor: colors.primary + "18",
                                alignItems: "center", justifyContent: "center",
                              }}
                            >
                              <Text style={[type.body, { color: colors.primary, fontWeight: "800" }]}>{activation.reps}</Text>
                            </View>
                          ) : (
                            <SetInput
                              compact
                              value={activation.reps}
                              onChangeText={(v) => updateSet(exerciseIndex, activationIdx, { reps: v })}
                            />
                          )}
                          <ConfirmCheck
                            completed={activation.completed}
                            saving={salvando.has(chaveAtivacao)}
                            onPress={() => handleConfirmSet(exerciseIndex, activationIdx)}
                          />
                        </View>

                        <RirRow
                          value={activation.rir}
                          onSelect={(v) => updateSet(exerciseIndex, activationIdx, { rir: v })}
                        />

                        {/* BLOCOS — chips compactos no lugar de "Mais opções":
                            um toque abre só a configuração daquele bloco. */}
                        {blocks.length > 0 ? (
                          <View style={{ flexDirection: "row", alignItems: "center", flexWrap: "wrap", marginTop: spacing.sm, gap: 6 }}>
                            <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700", marginRight: 2 }]}>
                              BLOCOS
                            </Text>
                            {blocks.map((b) => (
                              <BlockChip
                                key={b.idx}
                                number={b.row.blockIndex ?? 0}
                                status={b.row.blockStatus}
                                completed={b.row.completed}
                                selected={abertoIdx === b.idx}
                                onPress={() => toggleBlock(groupKey, b.idx)}
                              />
                            ))}
                          </View>
                        ) : null}

                        {/* Configuração do bloco tocado — peso, reps e status,
                            só ele por vez (não os três juntos). */}
                        {aberto ? (
                          <View style={{ marginTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.sm }}>
                            <View style={{ flexDirection: "row", alignItems: "center" }}>
                              <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]} numberOfLines={1}>
                                {aberto.row.blockLabel}
                              </Text>
                              <SetInput
                                compact
                                value={aberto.row.weight}
                                onChangeText={(v) => updateSet(exerciseIndex, aberto.idx, { weight: v })}
                              />
                              <Text style={[type.body, { color: colors.textSecondary, marginHorizontal: 4 }]}>×</Text>
                              <SetInput
                                compact
                                value={aberto.row.reps}
                                onChangeText={(v) => updateSet(exerciseIndex, aberto.idx, { reps: v })}
                              />
                              <ConfirmCheck
                                completed={aberto.row.completed}
                                saving={salvando.has(`${exerciseIndex}:${aberto.idx}`)}
                                onPress={() => handleConfirmSet(exerciseIndex, aberto.idx)}
                              />
                            </View>
                            {/* BLOCO — nos mini-sets este campo SUBSTITUI o RIR
                                (spec §7.1): o que importa é se o bloco fechou. */}
                            <BlockStatusRow
                              value={aberto.row.blockStatus}
                              onSelect={(v) => updateSet(exerciseIndex, aberto.idx, { blockStatus: v })}
                            />
                          </View>
                        ) : null}
                      </View>
                    </Card>
                  </React.Fragment>
                );
              })}

              <Button title="+ série extra" variant="ghost" onPress={() => handleAddSet(exerciseIndex)} />
            </View>
          );
        })}

        {/* Concluir em destaque (largura cheia) e Descartar embaixo, discreto —
            lado a lado o "Descartar" ficava espremido e quebrava em 2 linhas. */}
        <Button title="Concluir treino" onPress={handleFinishWorkout} loading={isCompleting} />
        <TouchableOpacity
          onPress={() => setConfirmDiscard(true)}
          disabled={isCompleting}
          style={{ alignItems: "center", paddingVertical: spacing.md, marginTop: spacing.xs }}
        >
          <Text style={[type.bodySmall, { color: colors.textSecondary, fontWeight: "700" }]}>Descartar treino</Text>
        </TouchableOpacity>
      </ScrollView>

      {restSeconds !== null ? (
        <RestTimerOverlay seconds={restSeconds} onFinish={() => setRestSeconds(null)} onSkip={() => setRestSeconds(null)} />
      ) : null}

      <ConfirmDialog
        visible={confirmDiscard}
        onClose={() => setConfirmDiscard(false)}
        title="Descartar treino"
        message="Isso apaga este treino e o que você registrou nele. Não vira histórico. Tem certeza?"
        confirmLabel="Descartar"
        destructive
        onConfirm={handleDiscard}
      />

      <DurationCheckModal
        visible={durationCheck !== null}
        measuredMinutes={durationCheck ?? 0}
        onConfirm={(minutes) => finishWith(minutes)}
        onKeepMeasured={() => finishWith(durationCheck ?? undefined)}
        saving={isCompleting}
      />

      <ConfirmDialog
        visible={trocando !== null}
        onClose={() => setTrocando(null)}
        title="Trocar este exercício agora?"
        message={
          trocando
            ? `Quem escolhe o substituto de ${trocando.re.exercise.name} é o coach — vem outro exercício ` +
              "para o mesmo músculo, com o mesmo papel no treino e respeitando suas preferências. " +
              "As séries e reps continuam iguais, e a troca vale também para as próximas vezes."
            : undefined
        }
        confirmLabel="Trocar"
        onConfirm={() => {
          if (trocando) trocarExercicio(trocando.re, trocando.idx);
        }}
      />

      <InfoDialog
        visible={resultadoTroca !== null}
        onClose={() => setResultadoTroca(null)}
        title={resultadoTroca?.titulo ?? ""}
        message={resultadoTroca?.texto}
      />
    </KeyboardAvoidingView>
  );
}

/** Abre o grupo de séries que uma técnica prescrita gerou. Sem isto a pessoa
 * veria linhas estranhas aparecendo no meio do exercício sem entender de onde
 * vieram — a técnica precisa se apresentar. */
function TechniqueHeader({ label, cue }: { label: string; cue: string }) {
  const { colors, type, spacing, radius } = useTheme();
  const [aberto, setAberto] = useState(false);
  return (
    <TouchableOpacity
      activeOpacity={0.8}
      onPress={() => setAberto((v) => !v)}
      style={{
        flexDirection: "row",
        alignItems: "flex-start",
        gap: 8,
        backgroundColor: colors.primary + "12",
        borderWidth: 1,
        borderColor: colors.primary + "33",
        borderRadius: radius.card,
        padding: spacing.sm,
        marginBottom: spacing.sm,
      }}
    >
      <Ionicons name="flash" size={15} color={colors.primary} style={{ marginTop: 1 }} />
      <View style={{ flex: 1 }}>
        <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "800" }]}>{label}</Text>
        <Text
          style={[type.caption, { color: colors.textSecondary, marginTop: 2, lineHeight: 17 }]}
          numberOfLines={aberto ? undefined : 2}
        >
          {cue}
        </Text>
      </View>
      <Ionicons name={aberto ? "chevron-up" : "chevron-down"} size={15} color={colors.textSecondary} />
    </TouchableOpacity>
  );
}

/** Botão ✓ de confirmar série — o mesmo círculo em qualquer linha (normal,
 * ativação ou bloco), só muda quem ele confirma. */
function ConfirmCheck({
  completed,
  saving,
  onPress,
}: {
  completed: boolean;
  saving: boolean;
  onPress: () => void;
}) {
  const { colors, spacing } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.8}
      hitSlop={6}
      // Bloqueia o toque enquanto grava e depois de gravada: é a outra
      // metade da guarda de clique duplo (§8.3).
      disabled={completed || saving}
      style={{
        width: 40,
        height: 40,
        borderRadius: 20,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: completed ? colors.secondary : colors.surfaceAlt,
        borderWidth: completed ? 0 : 1.5,
        borderColor: colors.border,
        marginLeft: spacing.xs,
      }}
    >
      {saving ? (
        <ActivityIndicator size="small" color={colors.textSecondary} />
      ) : (
        <Ionicons name="checkmark" size={22} color={completed ? colors.textOnPrimary : colors.textSecondary} />
      )}
    </TouchableOpacity>
  );
}

/** Chip "R1"/"R2"... do rest-pause — uma repetição avulsa. Diferente do
 * BlockChip (que abre um painel pra escolher completo/parcial/não saiu), aqui
 * o toque JÁ confirma: uma repetição não tem "quanto fechou", só feita ou não. */
function RepChip({
  number,
  completed,
  saving,
  disabled,
  onPress,
}: {
  number: number;
  completed: boolean;
  saving: boolean;
  disabled: boolean;
  onPress: () => void;
}) {
  const { colors, type } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={completed || saving || disabled}
      hitSlop={4}
      style={{
        width: 34,
        height: 34,
        borderRadius: 12,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: completed ? colors.secondary : colors.surfaceAlt,
        borderWidth: 1.5,
        borderColor: completed ? colors.secondary : colors.border,
        opacity: disabled && !completed ? 0.5 : 1,
      }}
    >
      {saving ? (
        <ActivityIndicator size="small" color={colors.textSecondary} />
      ) : completed ? (
        <Ionicons name="checkmark" size={16} color={colors.textOnPrimary} />
      ) : (
        <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "800" }]}>R{number}</Text>
      )}
    </TouchableOpacity>
  );
}

/** Fileira de RIR quick-select — sempre visível (exceção à regra de esconder
 * atrás de "mais opções", decidida com o usuário). */
function RirRow({ value, onSelect }: { value: string; onSelect: (v: string) => void }) {
  const { colors, type } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", marginTop: 6, marginLeft: 38 }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginRight: 6 }]}>RIR</Text>
      {RIR_OPTIONS.map((n) => {
        const selected = value === String(n);
        return (
          <TouchableOpacity
            key={n}
            onPress={() => onSelect(selected ? "" : String(n))}
            hitSlop={4}
            style={{
              width: 32,
              height: 32,
              borderRadius: 16,
              marginRight: 8,
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: selected ? colors.primary : colors.surfaceAlt,
            }}
          >
            <Text style={[type.caption, { color: selected ? colors.textOnPrimary : colors.textSecondary, fontWeight: "700", fontSize: 11 }]}>
              {n}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

/** Chip compacto "B1"/"B2"/"B3" (ajuste pós-v36, item 3): no lugar de um
 * cartão cheio por bloco, um toque abre só a configuração daquele bloco. */
function BlockChip({
  number,
  status,
  completed,
  selected,
  onPress,
}: {
  number: number;
  status: BlockStatus | undefined;
  completed: boolean;
  selected: boolean;
  onPress: () => void;
}) {
  const { colors, type } = useTheme();
  const cor =
    status === "completo" ? colors.success : status === "parcial" ? colors.warning : status === "nao_concluido" ? colors.danger : colors.textSecondary;
  return (
    <TouchableOpacity
      onPress={onPress}
      hitSlop={6}
      style={{
        width: 34,
        height: 34,
        borderRadius: 12,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: selected ? colors.primary + "22" : status ? cor + "1F" : colors.surfaceAlt,
        borderWidth: 1.5,
        borderColor: selected ? colors.primary : status ? cor : colors.border,
      }}
    >
      {completed ? (
        <Ionicons name="checkmark" size={16} color={cor} />
      ) : (
        <Text style={[type.caption, { color: status ? cor : colors.textSecondary, fontWeight: "800" }]}>B{number}</Text>
      )}
    </TouchableOpacity>
  );
}

/** BLOCO — nos mini-sets este campo SUBSTITUI o RIR (spec §7.1): RIR de um
 * bloco de 2 reps não diz nada; o que importa é se o bloco fechou. */
function BlockStatusRow({
  value,
  onSelect,
}: {
  value: BlockStatus | undefined;
  onSelect: (v: BlockStatus | undefined) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", flexWrap: "wrap", marginTop: spacing.xs, gap: 6 }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginRight: 2 }]}>BLOCO</Text>
      {(["completo", "parcial", "nao_concluido"] as BlockStatus[]).map((s) => {
        const on = value === s;
        const cor = s === "completo" ? colors.success : s === "parcial" ? colors.warning : colors.danger;
        return (
          <TouchableOpacity
            key={s}
            onPress={() => onSelect(on ? undefined : s)}
            hitSlop={4}
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 4,
              borderRadius: radius.pill,
              paddingVertical: 5,
              paddingHorizontal: 9,
              backgroundColor: on ? cor + "24" : colors.surfaceAlt,
              borderWidth: 1,
              borderColor: on ? cor : "transparent",
            }}
          >
            <Ionicons name={BLOCK_STATUS_ICON[s]} size={12} color={on ? cor : colors.textSecondary} />
            <Text style={[type.caption, { color: on ? cor : colors.textSecondary, fontWeight: "700", fontSize: 10 }]}>
              {BLOCK_STATUS_LABEL[s]}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

function Meta({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  const { colors, type } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
      <Ionicons name={icon} size={14} color={colors.textSecondary} />
      <Text style={[type.caption, { color: colors.textSecondary }]}>{text}</Text>
    </View>
  );
}

function SetInput({
  label,
  value,
  onChangeText,
  compact = false,
}: {
  label?: string;
  value: string;
  onChangeText: (v: string) => void;
  compact?: boolean;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View>
      {label ? (
        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: 4, textAlign: "center" }]}>{label}</Text>
      ) : null}
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/,/g, ".").replace(/[^0-9.]/g, ""))}
        keyboardType="decimal-pad"
        style={[
          compact ? type.body : type.h2,
          {
            color: colors.textPrimary,
            backgroundColor: colors.surfaceAlt,
            borderRadius: radius.button,
            width: compact ? 56 : 78,
            height: compact ? 44 : 52,
            textAlign: "center",
          },
        ]}
      />
    </View>
  );
}
