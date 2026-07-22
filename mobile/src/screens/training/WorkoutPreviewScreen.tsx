import { Ionicons } from "@expo/vector-icons";
import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, Text, TouchableOpacity, View } from "react-native";

import { listTechniqueCues, removeTechniqueCue, type TechniqueCue } from "../../api/coaching";
import { getRoutine, type Routine } from "../../api/routines";
import {
  getWorkoutPreview,
  startWorkoutSession,
  type ExercisePrefill,
} from "../../api/workoutSessions";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ExerciseThumb } from "../../components/ExerciseThumb";
import { useActiveWorkout } from "../../context/ActiveWorkoutContext";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

/** Prévia do treino: mostra os exercícios, séries e os pesos/reps da última vez
 * — igual à tela de execução, mas SEM iniciar a sessão. A pessoa vê o que vai
 * pegar e decide começar (aí sim inicia de verdade). */
export function WorkoutPreviewScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { startWorkout } = useActiveWorkout();
  const { routineId } = route.params as { routineId: number };

  const [routine, setRoutine] = useState<Routine | null>(null);
  const [prefill, setPrefill] = useState<ExercisePrefill[]>([]);
  const [cues, setCues] = useState<TechniqueCue[]>([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    Promise.all([getRoutine(routineId), getWorkoutPreview(routineId)])
      .then(([r, p]) => {
        setRoutine(r);
        setPrefill(p);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    // Dicas do coach (técnica no exercício travado) — some silenciosa se falhar.
    listTechniqueCues()
      .then(setCues)
      .catch(() => {});
  }, [routineId]);

  function cueFor(exerciseId: number): TechniqueCue | undefined {
    return cues.find((c) => c.exercise_id === exerciseId);
  }

  async function removerCue(id: number) {
    setCues((cs) => cs.filter((c) => c.id !== id)); // otimista
    try {
      await removeTechniqueCue(id);
    } catch {
      // se falhar, recarrega a lista pra refletir o estado real
      listTechniqueCues().then(setCues).catch(() => {});
    }
  }

  async function handleStart() {
    if (!routine) return;
    setStarting(true);
    try {
      const { session, prefill: pf } = await startWorkoutSession(routine.id);
      startWorkout({
        sessionId: session.id,
        routineId: routine.id,
        routineName: routine.name,
        prefill: pf,
        startedAt: new Date(session.started_at).getTime(),
      });
      navigation.replace("WorkoutExecution", { sessionId: session.id, routineId: routine.id, prefill: pf });
    } catch (err: any) {
      Alert.alert("Não foi possível iniciar", mensagemDeErro(err, "Tente novamente."));
      setStarting(false);
    }
  }

  function prefillFor(exerciseId: number): ExercisePrefill | undefined {
    return prefill.find((p) => p.exercise_id === exerciseId);
  }

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  if (!routine) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: spacing.lg }}>
        <Text style={[type.body, { color: colors.textSecondary }]}>Não consegui carregar o treino.</Text>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}>
        <Text style={[type.h1, { color: colors.textPrimary }]}>{routine.name}</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, marginBottom: spacing.md }]}>
          Prévia · os pesos são os da sua última vez. O treino ainda não começou.
        </Text>

        {routine.exercises.map((ex) => {
          const pf = prefillFor(ex.exercise_id);
          const reps =
            ex.target_reps_max != null ? `${ex.target_reps_min}-${ex.target_reps_max}` : `${ex.target_reps_min}`;
          return (
            <Card key={ex.id} style={{ marginBottom: spacing.md }}>
              <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
                <ExerciseThumb url={ex.exercise.video_url} size={44} />
                <View style={{ flex: 1, marginLeft: spacing.sm }}>
                  <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>{ex.exercise.name}</Text>
                  <Text style={[type.caption, { color: colors.textSecondary }]}>
                    {ex.target_sets} séries × {reps} reps · descanso {ex.rest_seconds}s
                  </Text>
                </View>
              </View>

              {/* Linhas das séries com o peso/reps da última vez (read-only). */}
              {Array.from({ length: ex.target_sets }).map((_, i) => {
                const last = pf?.sets?.[i];
                return (
                  <View
                    key={i}
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      justifyContent: "space-between",
                      paddingVertical: 6,
                      borderTopWidth: i === 0 ? 0 : 1,
                      borderTopColor: colors.border,
                    }}
                  >
                    <Text style={[type.caption, { color: colors.textSecondary }]}>Série {i + 1}</Text>
                    <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600" }]}>
                      {last ? `${last.weight_kg} kg × ${last.reps}` : "—"}
                    </Text>
                  </View>
                );
              })}
              {!pf?.sets?.length ? (
                <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4 }]}>
                  Primeira vez neste exercício — os pesos ficam prontos quando você treinar.
                </Text>
              ) : null}

              {/* Dica do coach: técnica de intensidade pra furar o platô deste
                  exercício. O "remover" é o desfazer, aqui onde ela vive. */}
              {(() => {
                const cue = cueFor(ex.exercise_id);
                if (!cue) return null;
                return (
                  <View
                    style={{
                      marginTop: spacing.sm,
                      backgroundColor: colors.surfaceAlt,
                      borderRadius: radius.card,
                      borderLeftWidth: 3,
                      borderLeftColor: colors.primary,
                      padding: spacing.sm,
                    }}
                  >
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 3 }}>
                      <Ionicons name="flash" size={14} color={colors.primary} />
                      <Text style={[type.caption, { color: colors.primary, fontWeight: "700", flex: 1 }]}>
                        Coach · {cue.technique_label}
                      </Text>
                      <TouchableOpacity onPress={() => removerCue(cue.id)} hitSlop={8}>
                        <Text style={[type.caption, { color: colors.textSecondary }]}>Remover</Text>
                      </TouchableOpacity>
                    </View>
                    <Text style={[type.caption, { color: colors.textSecondary, lineHeight: 18 }]}>{cue.cue_text}</Text>
                  </View>
                );
              })()}
            </Card>
          );
        })}
      </ScrollView>

      <View
        style={{
          padding: spacing.lg,
          paddingTop: spacing.md,
          borderTopWidth: 1,
          borderTopColor: colors.border,
          backgroundColor: colors.bg,
        }}
      >
        <Button title="Treinar agora" onPress={handleStart} loading={starting} />
      </View>
    </View>
  );
}
