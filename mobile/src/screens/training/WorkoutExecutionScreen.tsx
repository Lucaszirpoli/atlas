import { Ionicons } from "@expo/vector-icons";
import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { Alert, Image, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import { getRoutine, type Routine } from "../../api/routines";
import {
  completeWorkoutSession,
  logSet,
  type ExercisePrefill,
  type SetType,
} from "../../api/workoutSessions";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { HelpDot } from "../../components/HelpDot";
import { OptionButton } from "../../components/OptionButton";
import { RestTimerOverlay } from "../../components/RestTimerOverlay";
import { useTheme } from "../../theme/ThemeProvider";

const SET_TYPE_LABELS: Record<SetType, string> = {
  warmup: "Aquecimento",
  straight: "Válida",
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
  const route = useRoute<any>();
  const { sessionId, routineId, prefill } = route.params as {
    sessionId: number;
    routineId: number;
    prefill: ExercisePrefill[];
  };

  const [routine, setRoutine] = useState<Routine | null>(null);
  const [exerciseIndex, setExerciseIndex] = useState(0);
  const [setsByExercise, setSetsByExercise] = useState<SetRow[][]>([]);
  const [restSeconds, setRestSeconds] = useState<number | null>(null);
  const [isCompleting, setIsCompleting] = useState(false);

  useEffect(() => {
    getRoutine(routineId).then((r) => {
      setRoutine(r);
      const initial = r.exercises.map((re) => {
        const pre = prefill.find((p) => p.exercise_id === re.exercise_id);
        return Array.from({ length: re.target_sets }, (_, i) => {
          const previous = pre?.sets[i];
          return {
            weight: previous ? String(previous.weight_kg) : "",
            reps: previous ? String(previous.reps) : "",
            completed: false,
            setType: "straight" as SetType,
            rpe: "",
            rir: "",
            showMore: false,
            previous,
          };
        });
      });
      setSetsByExercise(initial);
    });
  }, [routineId]);

  if (!routine || setsByExercise.length === 0) {
    return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  }

  const routineExercise = routine.exercises[exerciseIndex];
  const sets = setsByExercise[exerciseIndex];
  const isLastExercise = exerciseIndex === routine.exercises.length - 1;
  const completedCount = sets.filter((s) => s.completed).length;

  function updateSet(setIdx: number, patch: Partial<SetRow>) {
    setSetsByExercise((prev) =>
      prev.map((rows, i) =>
        i === exerciseIndex ? rows.map((row, j) => (j === setIdx ? { ...row, ...patch } : row)) : rows
      )
    );
  }

  async function handleConfirmSet(setIdx: number) {
    const row = sets[setIdx];
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
      updateSet(setIdx, { completed: true });
      setRestSeconds(routineExercise.rest_seconds);
    } catch (err: any) {
      Alert.alert("Não foi possível registrar a série", err?.response?.data?.detail ?? "Tente novamente.");
    }
  }

  function handleAddSet() {
    setSetsByExercise((prev) =>
      prev.map((rows, i) =>
        i === exerciseIndex
          ? [...rows, { weight: "", reps: "", completed: false, setType: "straight", rpe: "", rir: "", showMore: false }]
          : rows
      )
    );
  }

  async function handleFinishWorkout() {
    setIsCompleting(true);
    try {
      const summary = await completeWorkoutSession(sessionId);
      navigation.replace("WorkoutSummary", { summary });
    } finally {
      setIsCompleting(false);
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }} showsVerticalScrollIndicator={false}>
        {/* Progresso de exercícios */}
        <View style={{ flexDirection: "row", gap: 6, marginBottom: spacing.md }}>
          {routine.exercises.map((_, i) => (
            <View
              key={i}
              style={{
                flex: 1,
                height: 5,
                borderRadius: 3,
                backgroundColor: i < exerciseIndex ? colors.secondary : i === exerciseIndex ? colors.secondary + "88" : colors.border,
              }}
            />
          ))}
        </View>

        <Text style={[type.caption, { color: colors.secondary, fontWeight: "700", letterSpacing: 1 }]}>
          EXERCÍCIO {exerciseIndex + 1} DE {routine.exercises.length}
        </Text>
        <Text style={[type.h1, { color: colors.textPrimary, marginTop: 2 }]}>
          {routineExercise.exercise.name}
        </Text>
        {routineExercise.exercise.video_url ? (
          <Image
            source={{ uri: routineExercise.exercise.video_url }}
            resizeMode="cover"
            style={{
              width: "100%",
              height: 190,
              borderRadius: radius.card,
              marginTop: spacing.sm,
              backgroundColor: colors.surfaceAlt,
            }}
          />
        ) : null}
        <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.xs, marginBottom: spacing.lg }}>
          <Meta icon="repeat" text={`${routineExercise.target_sets}x ${routineExercise.target_reps_min}${routineExercise.target_reps_max ? `-${routineExercise.target_reps_max}` : ""} reps`} />
          <Meta icon="timer-outline" text={`${routineExercise.rest_seconds}s descanso`} />
          <Meta icon="checkmark-done" text={`${completedCount}/${sets.length} feitas`} />
        </View>

        {sets.map((row, idx) => (
          <Card
            key={idx}
            padded={false}
            style={{
              marginBottom: spacing.sm,
              borderWidth: 1.5,
              borderColor: row.completed ? colors.secondary : "transparent",
            }}
          >
            <View style={{ padding: spacing.md }}>
              <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.sm }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
                  <View
                    style={{
                      width: 26,
                      height: 26,
                      borderRadius: 13,
                      backgroundColor: row.completed ? colors.secondary : colors.surfaceAlt,
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Text style={[type.caption, { color: row.completed ? colors.textOnPrimary : colors.textSecondary, fontWeight: "800" }]}>
                      {idx + 1}
                    </Text>
                  </View>
                  {row.previous ? (
                    <Text style={[type.caption, { color: colors.textSecondary }]}>
                      anterior: {row.previous.weight_kg}kg × {row.previous.reps}
                    </Text>
                  ) : (
                    <Text style={[type.caption, { color: colors.textSecondary }]}>primeira vez</Text>
                  )}
                </View>
                <TouchableOpacity onPress={() => updateSet(idx, { showMore: !row.showMore })} hitSlop={10}>
                  <Ionicons name="ellipsis-horizontal" size={20} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>

              <View style={{ flexDirection: "row", alignItems: "flex-end", gap: spacing.sm }}>
                <SetInput label="kg" value={row.weight} onChangeText={(v) => updateSet(idx, { weight: v })} />
                <Text style={[type.h2, { color: colors.textSecondary, marginBottom: 12 }]}>×</Text>
                <SetInput label="reps" value={row.reps} onChangeText={(v) => updateSet(idx, { reps: v })} />
                <View style={{ flex: 1 }} />
                <TouchableOpacity
                  onPress={() => handleConfirmSet(idx)}
                  activeOpacity={0.8}
                  style={{
                    width: 52,
                    height: 52,
                    borderRadius: 26,
                    alignItems: "center",
                    justifyContent: "center",
                    backgroundColor: row.completed ? colors.secondary : colors.surfaceAlt,
                    borderWidth: row.completed ? 0 : 1.5,
                    borderColor: colors.border,
                  }}
                >
                  <Ionicons name="checkmark" size={26} color={row.completed ? colors.textOnPrimary : colors.textSecondary} />
                </TouchableOpacity>
              </View>

              {row.showMore ? (
                <View style={{ marginTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.md }}>
                  <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
                    <Text style={[type.caption, { color: colors.textSecondary }]}>Tipo de série</Text>
                    <HelpDot
                      title="Tipo de série"
                      text={
                        "Deixe em 'Válida' se for uma série normal. Os outros tipos são técnicas avançadas: " +
                        "Drop-set (reduzir o peso e continuar sem descanso), Rest-pause (pausas curtas dentro da série), " +
                        "Até a falha (ir até não conseguir mais uma repetição), Aquecimento (série leve de preparação), etc. " +
                        "Não é obrigatório marcar nada."
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
                          onPress={() => updateSet(idx, { setType: st })}
                        />
                      ))}
                    </View>
                  </ScrollView>
                  <View style={{ flexDirection: "row", alignItems: "center", marginTop: spacing.sm }}>
                    <Text style={[type.caption, { color: colors.textSecondary }]}>Intensidade (opcional)</Text>
                    <HelpDot
                      title="RPE e RIR"
                      text={
                        "RPE = quão pesada a série foi, de 0 a 10 (10 = esforço máximo). " +
                        "RIR = quantas repetições você ainda conseguiria fazer antes de falhar (0 = falhou). " +
                        "São formas de medir o esforço — preencha só se quiser acompanhar isso."
                      }
                    />
                  </View>
                  <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.xs }}>
                    <SetInput label="RPE" value={row.rpe} onChangeText={(v) => updateSet(idx, { rpe: v })} />
                    <SetInput label="RIR" value={row.rir} onChangeText={(v) => updateSet(idx, { rir: v })} />
                  </View>
                </View>
              ) : null}
            </View>
          </Card>
        ))}

        <Button title="+ série extra" variant="ghost" onPress={handleAddSet} />

        <View style={{ marginTop: spacing.md }}>
          {isLastExercise ? (
            <Button title="Concluir treino" variant="secondary" onPress={handleFinishWorkout} loading={isCompleting} />
          ) : (
            <Button title="Próximo exercício →" variant="secondary" onPress={() => setExerciseIndex((i) => Math.min(i + 1, routine!.exercises.length - 1))} />
          )}
        </View>
        {exerciseIndex > 0 ? (
          <View style={{ marginTop: spacing.sm }}>
            <Button title="← Exercício anterior" variant="ghost" onPress={() => setExerciseIndex((i) => Math.max(i - 1, 0))} />
          </View>
        ) : null}
      </ScrollView>

      {restSeconds !== null ? (
        <RestTimerOverlay seconds={restSeconds} onFinish={() => setRestSeconds(null)} onSkip={() => setRestSeconds(null)} />
      ) : null}
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
}: {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: 4, textAlign: "center" }]}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/[^0-9.]/g, ""))}
        keyboardType="decimal-pad"
        style={[
          type.h2,
          {
            color: colors.textPrimary,
            backgroundColor: colors.surfaceAlt,
            borderRadius: radius.button,
            width: 78,
            height: 52,
            textAlign: "center",
          },
        ]}
      />
    </View>
  );
}
