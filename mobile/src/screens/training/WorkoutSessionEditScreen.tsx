import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRoute } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { getWorkoutSession, updateWorkoutSet, type WorkoutSessionDetail, type WorkoutSetLog } from "../../api/workoutSessions";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { useTheme } from "../../theme/ThemeProvider";

/** Tela de um treino JÁ CONCLUÍDO (Histórico de treinos › tocar um treino) —
 * pra corrigir peso/reps digitados errado, inclusive de dias passados. Não é
 * a execução (essa é a WorkoutExecutionScreen, pro treino em andamento). */
export function WorkoutSessionEditScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const route = useRoute<any>();
  const insets = useSafeAreaInsets();
  const { sessionId } = route.params ?? {};

  const [session, setSession] = useState<WorkoutSessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<WorkoutSetLog | null>(null);
  const [editWeight, setEditWeight] = useState("");
  const [editReps, setEditReps] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    getWorkoutSession(sessionId)
      .then(setSession)
      .finally(() => setLoading(false));
  }, [sessionId]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  function openEditor(set: WorkoutSetLog) {
    setEditWeight(String(set.weight_kg).replace(".", ","));
    setEditReps(String(set.reps));
    setEditing(set);
  }

  async function salvarEdicao() {
    if (!editing) return;
    const weight = Number(editWeight.replace(",", "."));
    const reps = Number(editReps);
    if (!Number.isFinite(weight) || weight < 0 || !Number.isInteger(reps) || reps < 0) return;
    setSaving(true);
    try {
      await updateWorkoutSet(editing.id, { weight_kg: weight, reps });
      // Atualização otimista local — evita recarregar a sessão inteira.
      setSession((s) =>
        s
          ? { ...s, sets: s.sets.map((st) => (st.id === editing.id ? { ...st, weight_kg: weight, reps } : st)) }
          : s
      );
      setEditing(null);
    } catch {
      /* silencioso — o modal continua aberto pra tentar de novo */
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  if (!session) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
        <Text style={[type.body, { color: colors.textSecondary }]}>Não consegui carregar esse treino.</Text>
      </View>
    );
  }

  // Agrupa por exercício, na ordem em que foram feitos.
  const grupos: { exerciseId: number; exerciseName: string; sets: WorkoutSetLog[] }[] = [];
  [...session.sets]
    .sort((a, b) => a.exercise_sort_order - b.exercise_sort_order || a.set_number - b.set_number)
    .forEach((s) => {
      let g = grupos.find((x) => x.exerciseId === s.exercise_id);
      if (!g) {
        g = { exerciseId: s.exercise_id, exerciseName: s.exercise.name, sets: [] };
        grupos.push(g);
      }
      g.sets.push(s);
    });

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl + insets.bottom }}
        showsVerticalScrollIndicator={false}
      >
        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>
          Toque numa série pra corrigir o peso ou as reps.
        </Text>

        {grupos.map((g) => (
          <Card key={g.exerciseId} style={{ marginBottom: spacing.md }}>
            <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.sm }]} numberOfLines={2}>
              {g.exerciseName}
            </Text>
            {g.sets.map((s) => (
              <Pressable
                key={s.id}
                onPress={() => openEditor(s)}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  paddingVertical: spacing.sm,
                  borderTopWidth: 1,
                  borderTopColor: colors.border,
                }}
              >
                <View
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 9,
                    backgroundColor: colors.moduleTraining + "18",
                    alignItems: "center",
                    justifyContent: "center",
                    marginRight: spacing.sm,
                  }}
                >
                  <Text style={[type.caption, { color: colors.moduleTraining, fontWeight: "800" }]}>{s.set_number}</Text>
                </View>
                <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600", flex: 1 }]}>
                  {s.weight_kg.toString().replace(".", ",")} kg × {s.reps} reps
                </Text>
                <Ionicons name="create-outline" size={18} color={colors.textSecondary} />
              </Pressable>
            ))}
          </Card>
        ))}
      </ScrollView>

      {editing ? (
        <KeyboardAvoidingView
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 0,
            bottom: 0,
            backgroundColor: "rgba(0,0,0,0.55)",
            alignItems: "center",
            justifyContent: "center",
            padding: spacing.lg,
          }}
        >
          <Card style={{ width: "100%" }}>
            <Text style={[type.h2, { color: colors.textPrimary, marginBottom: 2 }]} numberOfLines={2}>
              {editing.exercise.name}
            </Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>
              Série {editing.set_number}
            </Text>
            <View style={{ flexDirection: "row", gap: spacing.sm }}>
              <View style={{ flex: 1 }}>
                <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>Peso (kg)</Text>
                <TextInput
                  value={editWeight}
                  onChangeText={(v) => setEditWeight(v.replace(/[^0-9.,]/g, ""))}
                  keyboardType="decimal-pad"
                  style={[
                    type.h2,
                    { color: colors.textPrimary, backgroundColor: colors.surfaceAlt, borderRadius: radius.button, height: 52, textAlign: "center" },
                  ]}
                />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>Reps</Text>
                <TextInput
                  value={editReps}
                  onChangeText={(v) => setEditReps(v.replace(/[^0-9]/g, ""))}
                  keyboardType="number-pad"
                  style={[
                    type.h2,
                    { color: colors.textPrimary, backgroundColor: colors.surfaceAlt, borderRadius: radius.button, height: 52, textAlign: "center" },
                  ]}
                />
              </View>
            </View>
            <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg }}>
              <View style={{ flex: 1 }}>
                <Button title="Salvar" compact onPress={salvarEdicao} loading={saving} />
              </View>
              <View style={{ flex: 1 }}>
                <Button title="Cancelar" variant="ghost" compact onPress={() => setEditing(null)} />
              </View>
            </View>
          </Card>
        </KeyboardAvoidingView>
      ) : null}
    </View>
  );
}
