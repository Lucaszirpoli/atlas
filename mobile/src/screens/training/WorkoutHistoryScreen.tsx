import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  discardWorkoutSession,
  listWorkoutSessions,
  type WorkoutSessionDetail,
} from "../../api/workoutSessions";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useTheme } from "../../theme/ThemeProvider";

/** Histórico de treinos concluídos, com opção de EXCLUIR — pra quando a pessoa
 * salvou um treino errado (iniciou sem querer, registrou no dia errado etc).
 * Excluir aqui apaga a sessão e as séries dela do histórico. */
export function WorkoutHistoryScreen() {
  const { colors, type, spacing } = useTheme();
  const insets = useSafeAreaInsets();

  const [sessions, setSessions] = useState<WorkoutSessionDetail[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<WorkoutSessionDetail | null>(null);

  const load = useCallback(() => {
    listWorkoutSessions()
      .then((all) => setSessions(all.filter((s) => s.completed_at != null)))
      .catch(() => {});
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function confirmDelete() {
    if (!deleteTarget) return;
    try {
      await discardWorkoutSession(deleteTarget.id);
    } catch {
      // segue e recarrega — se falhar, a lista volta como está
    }
    setDeleteTarget(null);
    load();
  }

  function volumeOf(s: WorkoutSessionDetail): number {
    return s.sets.reduce((sum, set) => sum + set.weight_kg * set.reps, 0);
  }

  function durationOf(s: WorkoutSessionDetail): string {
    if (!s.completed_at) return "";
    const min = Math.round((new Date(s.completed_at).getTime() - new Date(s.started_at).getTime()) / 60000);
    const h = Math.floor(min / 60);
    return h > 0 ? `${h}h${String(min % 60).padStart(2, "0")}` : `${min}min`;
  }

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl + insets.bottom }}
      showsVerticalScrollIndicator={false}
    >
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
        Toque na lixeira para excluir um treino salvo por engano.
      </Text>

      {sessions.length === 0 ? (
        <Card>
          <View style={{ alignItems: "center", paddingVertical: spacing.lg }}>
            <Ionicons name="barbell-outline" size={30} color={colors.textSecondary} />
            <Text style={[type.body, { color: colors.textSecondary, marginTop: spacing.sm }]}>
              Nenhum treino concluído ainda.
            </Text>
          </View>
        </Card>
      ) : null}

      {sessions.map((s) => (
        <Card key={s.id} style={{ marginBottom: spacing.sm }}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <View style={{ flex: 1 }}>
              <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>
                {new Date(s.started_at).toLocaleDateString("pt-BR", {
                  day: "2-digit",
                  month: "2-digit",
                  year: "numeric",
                })}
              </Text>
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
                {s.sets.length} séries · {Math.round(volumeOf(s)).toLocaleString("pt-BR")} kg de volume ·{" "}
                {durationOf(s)}
              </Text>
            </View>
            <TouchableOpacity onPress={() => setDeleteTarget(s)} hitSlop={10} style={{ padding: spacing.xs }}>
              <Ionicons name="trash-outline" size={20} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
        </Card>
      ))}

      <ConfirmDialog
        visible={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Excluir treino"
        message={
          deleteTarget
            ? `Excluir o treino de ${new Date(deleteTarget.started_at).toLocaleDateString("pt-BR")}? As séries registradas nele saem do seu histórico e dos seus gráficos.`
            : undefined
        }
        confirmLabel="Excluir"
        destructive
        onConfirm={confirmDelete}
      />
    </ScrollView>
  );
}
