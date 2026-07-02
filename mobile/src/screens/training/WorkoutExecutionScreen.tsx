import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import { getRoutine, type Routine } from "../../api/routines";
import {
  completeWorkoutSession,
  logSet,
  type ExercisePrefill,
  type SetType,
} from "../../api/workoutSessions";
import { Button } from "../../components/Button";
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
  eccentric_emphasis: "Excêntrica enfatizada",
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

  function updateSet(setIdx: number, patch: Partial<SetRow>) {
    setSetsByExercise((prev) =>
      prev.map((rows, i) =>
        i === exerciseIndex
          ? rows.map((row, j) => (j === setIdx ? { ...row, ...patch } : row))
          : rows
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

  function goToNextExercise() {
    setExerciseIndex((i) => Math.min(i + 1, routine!.exercises.length - 1));
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
      <ScrollView contentContainerStyle={{ padding: spacing.lg }}>
        <Text style={[type.caption, { color: colors.textSecondary }]}>
          Exercício {exerciseIndex + 1} de {routine.exercises.length}
        </Text>
        <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.sm }]}>
          {routineExercise.exercise.name}
        </Text>
        <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.lg }]}>
          Meta: {routineExercise.target_sets}x {routineExercise.target_reps_min}
          {routineExercise.target_reps_max ? `-${routineExercise.target_reps_max}` : ""} · descanso{" "}
          {routineExercise.rest_seconds}s
        </Text>

        {sets.map((row, idx) => (
          <View
            key={idx}
            style={{
              backgroundColor: colors.surface,
              borderRadius: radius.card,
              borderWidth: 1,
              borderColor: row.completed ? colors.secondary : colors.border,
              padding: spacing.md,
              marginBottom: spacing.sm,
            }}
          >
            <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
              <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
                Série {idx + 1}
                {row.previous ? ` · anterior: ${row.previous.weight_kg}kg x ${row.previous.reps}` : ""}
              </Text>
              <TouchableOpacity onPress={() => updateSet(idx, { showMore: !row.showMore })}>
                <Text style={[type.bodySmall, { color: colors.textSecondary }]}>⋯</Text>
              </TouchableOpacity>
            </View>

            <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.xs }}>
              <SetInput label="kg" value={row.weight} onChangeText={(v) => updateSet(idx, { weight: v })} />
              <SetInput label="reps" value={row.reps} onChangeText={(v) => updateSet(idx, { reps: v })} />
              <TouchableOpacity
                onPress={() => handleConfirmSet(idx)}
                style={{
                  marginLeft: "auto",
                  width: 40,
                  height: 40,
                  borderRadius: 20,
                  alignItems: "center",
                  justifyContent: "center",
                  backgroundColor: row.completed ? colors.secondary : colors.border,
                }}
              >
                <Text style={{ color: row.completed ? "#FFFFFF" : colors.textSecondary }}>✓</Text>
              </TouchableOpacity>
            </View>

            {row.showMore ? (
              <View style={{ marginTop: spacing.sm }}>
                <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>
                  Tipo de série
                </Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                  {SET_TYPE_ORDER.map((st) => (
                    <TouchableOpacity
                      key={st}
                      onPress={() => updateSet(idx, { setType: st })}
                      style={{
                        borderWidth: 1,
                        borderColor: row.setType === st ? colors.primary : colors.border,
                        borderRadius: radius.button,
                        paddingVertical: spacing.xs,
                        paddingHorizontal: spacing.sm,
                        marginRight: spacing.xs,
                      }}
                    >
                      <Text style={[type.caption, { color: row.setType === st ? colors.primary : colors.textSecondary }]}>
                        {SET_TYPE_LABELS[st]}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </ScrollView>
                <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm }}>
                  <SetInput label="RPE" value={row.rpe} onChangeText={(v) => updateSet(idx, { rpe: v })} />
                  <SetInput label="RIR" value={row.rir} onChangeText={(v) => updateSet(idx, { rir: v })} />
                </View>
              </View>
            ) : null}
          </View>
        ))}

        <Button title="+ série" variant="ghost" onPress={handleAddSet} />

        <View style={{ marginTop: spacing.lg }}>
          {isLastExercise ? (
            <Button title="Concluir treino" onPress={handleFinishWorkout} loading={isCompleting} />
          ) : (
            <Button title="Próximo exercício" onPress={goToNextExercise} />
          )}
        </View>
      </ScrollView>

      {restSeconds !== null ? (
        <RestTimerOverlay
          seconds={restSeconds}
          onFinish={() => setRestSeconds(null)}
          onSkip={() => setRestSeconds(null)}
        />
      ) : null}
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
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/[^0-9.]/g, ""))}
        keyboardType="decimal-pad"
        style={[
          type.body,
          {
            color: colors.textPrimary,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.button,
            width: 70,
            height: 40,
            textAlign: "center",
          },
        ]}
      />
    </View>
  );
}
