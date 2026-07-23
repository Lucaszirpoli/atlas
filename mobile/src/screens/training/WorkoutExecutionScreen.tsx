import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation, useRoute } from "@react-navigation/native";
import React, { useCallback, useEffect, useState } from "react";
import { Alert, KeyboardAvoidingView, Platform, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { listWorkoutOverlays, type WorkoutOverlay } from "../../api/coaching";
import { CoachOverlayBlock, DeloadBanner } from "../../components/CoachOverlay";
import { getRoutine, type Routine } from "../../api/routines";
import {
  completeWorkoutSession,
  discardWorkoutSession,
  getAvgWorkoutDuration,
  logSet,
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

type SetRow = {
  weight: string;
  reps: string;
  completed: boolean;
  setType: SetType;
  rpe: string;
  rir: string;
  showMore: boolean;
  previous?: { weight_kg: number; reps: number };
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

  useEffect(() => {
    getRoutine(routineId).then((r) => {
      setRoutine(r);
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
          };
        });
        return [...prepRows, ...workRows];
      });
      setSetsByExercise(initial);
    });
  }, [routineId]);

  // Overlays do coach (técnica / subir carga / troca / deload) — some silencioso.
  // Só leitura aqui; remover/desfazer é no Coaching ou na prévia.
  useEffect(() => {
    listWorkoutOverlays().then(setOverlays).catch(() => {});
  }, []);

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
    const routineExercise = routine!.exercises[exerciseIndex];
    const row = setsByExercise[exerciseIndex][setIdx];
    const weightNum = Number(row.weight);
    const repsNum = Number(row.reps);
    if (!row.weight || !row.reps || Number.isNaN(weightNum) || Number.isNaN(repsNum)) {
      Alert.alert("Preencha peso e repetições");
      return;
    }
    try {
      await logSet(sessionId, {
        exercise_id: routineExercise.exercise_id,
        exercise_sort_order: exerciseIndex,
        set_number: setIdx + 1,
        weight_kg: weightNum,
        reps: repsNum,
        set_type: row.setType,
        rpe: row.rpe ? Number(row.rpe) : null,
        rir: row.rir ? Number(row.rir) : null,
      });
      updateSet(exerciseIndex, setIdx, { completed: true });
      setRestSeconds(routineExercise.rest_seconds);
    } catch (err: any) {
      Alert.alert("Não foi possível registrar a série", mensagemDeErro(err, "Tente novamente."));
    }
  }

  function handleAddSet(exerciseIndex: number) {
    setSetsByExercise((prev) =>
      prev.map((rows, i) =>
        i === exerciseIndex
          ? [...rows, { weight: "", reps: "", completed: false, setType: "straight", rpe: "", rir: "", showMore: false }]
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
                // Numeração só conta séries de TRABALHO (sem letra) — a rampa
                // de aquecimento/feeder na frente não desloca "Série 1, 2, 3...".
                const workNumber = sets.slice(0, idx).filter((r) => !QUICK_TYPE_LETTER[r.setType]).length + 1;
                const badgeColor = row.setType === "to_failure" ? colors.danger : letter ? colors.warning : undefined;
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

                        <TouchableOpacity
                          onPress={() => handleConfirmSet(exerciseIndex, idx)}
                          activeOpacity={0.8}
                          hitSlop={6}
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
                          <Ionicons name="checkmark" size={22} color={row.completed ? colors.textOnPrimary : colors.textSecondary} />
                        </TouchableOpacity>
                      </View>

                      {/* RIR — sempre visível, quick-select (espec.: exceção à
                          regra de "esconder atrás de mais opções", decidida
                          com o usuário). Não se aplica a aquecimento/feeder —
                          são séries submáximas de preparação, não de esforço. */}
                      {row.setType !== "warmup" && row.setType !== "feeder" ? (
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
