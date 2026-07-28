import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation, useRoute } from "@react-navigation/native";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, KeyboardAvoidingView, Platform, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { listWorkoutOverlays, type WorkoutOverlay } from "../../api/coaching";
import { CoachOverlayBlock, DeloadBanner } from "../../components/CoachOverlay";
import { getRoutine, type Routine } from "../../api/routines";
import {
  completeWorkoutSession,
  discardWorkoutSession,
  getAvgWorkoutDuration,
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
import { OptionButton } from "../../components/OptionButton";
import { RestTimerOverlay } from "../../components/RestTimerOverlay";
import { useActiveWorkout } from "../../context/ActiveWorkoutContext";
import { useTheme } from "../../theme/ThemeProvider";
import { fmtKg } from "../../utils/format";
import { mensagemDeErro } from "../../utils/errorMessage";
import {
  BLOCK_STATUS_LABEL,
  expandTechnique,
  nextBlockStatus,
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
  const { sessionId, routineId, prefill } = route.params as {
    sessionId: number;
    routineId: number;
    prefill: ExercisePrefill[];
  };

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

      const initial = r.exercises.map((re) => {
        const pre = prefill.find((p) => p.exercise_id === re.exercise_id);
        // Rampa de aquecimento/feeder (calculada da carga real de trabalho)
        // vem ANTES das séries de trabalho — já com peso/reps sugeridos,
        // editáveis como qualquer série.
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
        const workRows: SetRow[] = Array.from({ length: re.target_sets }, (_, i) => {
          const previous = pre?.sets[i];
          // Intenção que o coach definiu ao montar a rotina (até a falha) já
          // vem pré-marcada no badge, com o RIR sugerido pro momento do ciclo
          // — a pessoa não precisa lembrar de marcar na hora. Rotina sem
          // intenção (manual) cai no normal.
          const intent = re.set_intents?.[i];
          const isFailure = intent === "to_failure";
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

        // Técnica avançada prescrita pelo coach: a última série de trabalho
        // vira a estrutura do método (ativação + blocos, ou quedas de carga).
        const tech = prescriptionFor(ovs, re.exercise_id);
        const finais = tech
          ? expandTechnique(workRows, tech, workRows[workRows.length - 1]?.weight ?? "")
          : workRows;
        return [...prepRows, ...finais];
      });
      setSetsByExercise(initial);
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
              },
            ]
          : rows
      )
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
    navigation.navigate("RoutineList");
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
                  <Ionicons name="git-branch" size={13} color={colors.textSecondary} />
                  <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]} numberOfLines={2}>
                    Cargas vindas de{" "}
                    {prefill.find((p) => p.exercise_id === routineExercise.exercise_id)?.inherited_from_name} — você
                    escolheu manter os registros na troca.
                  </Text>
                </View>
              ) : null}

              {/* Overlays do coach neste exercício (técnica / subir carga /
                  troca). Só leitura aqui — desfazer é no Coaching ou na prévia. */}
              {overlaysFor(routineExercise.exercise_id).map((o) => (
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

              {sets.map((row, idx) => {
                const letter = QUICK_TYPE_LETTER[row.setType];
                const emTecnica = row.role === "activation" || row.role === "block" || row.role === "drop";
                // Numeração só conta séries de TRABALHO (sem letra e fora da
                // técnica) — nem a rampa de aquecimento/feeder na frente nem os
                // mini-sets deslocam "Série 1, 2, 3...".
                const workNumber =
                  sets
                    .slice(0, idx)
                    .filter(
                      (r) =>
                        !QUICK_TYPE_LETTER[r.setType] &&
                        r.role !== "block" &&
                        r.role !== "drop"
                    ).length + 1;
                const badgeColor = row.setType === "to_failure" ? colors.danger : letter ? colors.warning : undefined;
                return (
                  <React.Fragment key={idx}>
                  {/* Cabeçalho da técnica prescrita — abre o grupo de linhas
                      que o método gerou, pra ficar claro que dali pra baixo a
                      série mudou de forma. */}
                  {row.groupStart ? (
                    <TechniqueHeader
                      label={
                        prescriptionFor(overlays, routineExercise.exercise_id)?.label ?? "Técnica avançada"
                      }
                      cue={prescriptionFor(overlays, routineExercise.exercise_id)?.cue ?? ""}
                    />
                  ) : null}
                  <Card
                    padded={false}
                    style={{
                      marginBottom: spacing.sm,
                      marginLeft: row.role === "block" || row.role === "drop" ? spacing.md : 0,
                      borderWidth: 1.5,
                      borderColor: row.completed
                        ? colors.secondary
                        : emTecnica
                        ? colors.primary + "3A"
                        : "transparent",
                    }}
                  >
                    <View style={{ padding: spacing.sm }}>
                      <View style={{ flexDirection: "row", alignItems: "center" }}>
                        {/* Badge da série — toque cicla normal → A (aquecimento) →
                            P (preparatória) → F (falha) → normal. Dentro de uma
                            técnica o badge não cicla: o tipo é o do método. */}
                        <TouchableOpacity
                          onPress={() =>
                            emTecnica
                              ? undefined
                              : updateSet(exerciseIndex, idx, { setType: nextQuickType(row.setType) })
                          }
                          disabled={emTecnica}
                          hitSlop={8}
                          style={{
                            width: 30,
                            height: 30,
                            borderRadius: 15,
                            backgroundColor: emTecnica
                              ? colors.primary + "22"
                              : badgeColor
                              ? badgeColor + "26"
                              : colors.surfaceAlt,
                            alignItems: "center",
                            justifyContent: "center",
                          }}
                        >
                          {row.role === "block" || row.role === "drop" ? (
                            <Text style={[type.caption, { color: colors.primary, fontWeight: "800", fontSize: 11 }]}>
                              {row.blockIndex}
                            </Text>
                          ) : (
                            <Text
                              style={[
                                type.caption,
                                { color: emTecnica ? colors.primary : badgeColor ?? colors.textSecondary, fontWeight: "800" },
                              ]}
                            >
                              {letter ?? workNumber}
                            </Text>
                          )}
                        </TouchableOpacity>

                        <View style={{ flex: 1, marginLeft: spacing.sm }}>
                          {/* Numa linha de técnica o rótulo do método vale mais
                              que "o que você fez da última vez". */}
                          {row.blockLabel ? (
                            <Text
                              style={[type.caption, { color: colors.primary, fontWeight: "700" }]}
                              numberOfLines={1}
                            >
                              {row.blockLabel}
                            </Text>
                          ) : row.previous ? (
                            <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
                              {fmtKg(row.previous.weight_kg)}kg × {row.previous.reps}
                            </Text>
                          ) : (
                            <Text style={[type.caption, { color: colors.textSecondary }]}>primeira vez</Text>
                          )}
                        </View>

                        <SetInput compact value={row.weight} onChangeText={(v) => updateSet(exerciseIndex, idx, { weight: v })} />
                        <Text style={[type.body, { color: colors.textSecondary, marginHorizontal: 4 }]}>×</Text>
                        {/* Reps travadas pelo método (myo-reps: 6 na ativação) —
                            mostra o número sem input, porque mudar ali
                            descaracterizaria a técnica. */}
                        {row.repsLocked ? (
                          <View
                            style={{
                              width: 56,
                              height: 44,
                              borderRadius: radius.button,
                              backgroundColor: colors.primary + "18",
                              alignItems: "center",
                              justifyContent: "center",
                            }}
                          >
                            <Text style={[type.body, { color: colors.primary, fontWeight: "800" }]}>{row.reps}</Text>
                          </View>
                        ) : (
                          <SetInput compact value={row.reps} onChangeText={(v) => updateSet(exerciseIndex, idx, { reps: v })} />
                        )}

                        <TouchableOpacity
                          onPress={() => handleConfirmSet(exerciseIndex, idx)}
                          activeOpacity={0.8}
                          hitSlop={6}
                          // Bloqueia o toque enquanto grava e depois de gravada:
                          // é a outra metade da guarda de clique duplo (§8.3).
                          disabled={row.completed || salvando.has(`${exerciseIndex}:${idx}`)}
                          style={{
                            width: 40,
                            height: 40,
                            borderRadius: 20,
                            alignItems: "center",
                            justifyContent: "center",
                            backgroundColor: row.completed ? colors.secondary : colors.surfaceAlt,
                            borderWidth: row.completed ? 0 : 1.5,
                            borderColor: colors.border,
                            marginLeft: spacing.xs,
                          }}
                        >
                          {salvando.has(`${exerciseIndex}:${idx}`) ? (
                            <ActivityIndicator size="small" color={colors.textSecondary} />
                          ) : (
                            <Ionicons name="checkmark" size={22} color={row.completed ? colors.textOnPrimary : colors.textSecondary} />
                          )}
                        </TouchableOpacity>
                      </View>

                      {/* BLOCO — nos mini-sets este campo SUBSTITUI o RIR
                          (spec §7.1). RIR de um bloco de 2 reps não diz nada;
                          o que importa é se o bloco fechou. Um toque resolve. */}
                      {row.role === "block" || row.role === "drop" ? (
                        <View style={{ flexDirection: "row", alignItems: "center", marginTop: spacing.xs, marginLeft: 38, gap: 6 }}>
                          <Text style={[type.caption, { color: colors.textSecondary, marginRight: 2 }]}>BLOCO</Text>
                          {(["completo", "parcial", "nao_concluido"] as BlockStatus[]).map((s) => {
                            const on = row.blockStatus === s;
                            const cor =
                              s === "completo" ? colors.success : s === "parcial" ? colors.warning : colors.danger;
                            return (
                              <TouchableOpacity
                                key={s}
                                onPress={() =>
                                  updateSet(exerciseIndex, idx, { blockStatus: on ? undefined : s })
                                }
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
                                <Ionicons
                                  name={BLOCK_STATUS_ICON[s]}
                                  size={12}
                                  color={on ? cor : colors.textSecondary}
                                />
                                <Text
                                  style={[
                                    type.caption,
                                    { color: on ? cor : colors.textSecondary, fontWeight: "700", fontSize: 10 },
                                  ]}
                                >
                                  {BLOCK_STATUS_LABEL[s]}
                                </Text>
                              </TouchableOpacity>
                            );
                          })}
                        </View>
                      ) : null}

                      {/* RIR — sempre visível, quick-select (espec.: exceção à
                          regra de "esconder atrás de mais opções", decidida
                          com o usuário). Não se aplica a aquecimento/feeder
                          (séries submáximas de preparação) nem a mini-set de
                          técnica (ali quem conta a história é o BLOCO). */}
                      {row.setType !== "warmup" &&
                      row.setType !== "feeder" &&
                      row.role !== "block" &&
                      row.role !== "drop" ? (
                        <View style={{ flexDirection: "row", alignItems: "center", marginTop: spacing.xs, marginLeft: 38 }}>
                          <Text style={[type.caption, { color: colors.textSecondary, marginRight: 6 }]}>RIR</Text>
                          {RIR_OPTIONS.map((n) => {
                            const selected = row.rir === String(n);
                            return (
                              <TouchableOpacity
                                key={n}
                                onPress={() => updateSet(exerciseIndex, idx, { rir: selected ? "" : String(n) })}
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
                  </React.Fragment>
                );
              })}

              <Button title="+ série extra" variant="ghost" onPress={() => handleAddSet(exerciseIndex)} />
            </View>
          );
        })}

        {/* Concluir em destaque (largura cheia) e Descartar embaixo, discreto —
            lado a lado o "Descartar" ficava espremido e quebrava em 2 linhas. */}
        <Button title="Concluir treino" variant="secondary" onPress={handleFinishWorkout} loading={isCompleting} />
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
