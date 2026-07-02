import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, FlatList, Text, TouchableOpacity, View } from "react-native";

import {
  archiveRoutine,
  deleteRoutine,
  duplicateRoutine,
  listRoutines,
  type Routine,
} from "../../api/routines";
import { startWorkoutSession } from "../../api/workoutSessions";
import { Button } from "../../components/Button";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

const ROUTINE_LIMIT = { free: 3, pro: 7 };

export function RoutineListScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();

  const [routines, setRoutines] = useState<Routine[]>([]);

  useFocusEffect(
    useCallback(() => {
      listRoutines().then(setRoutines);
    }, [])
  );

  async function handleStart(routine: Routine) {
    try {
      const { session, prefill } = await startWorkoutSession(routine.id);
      navigation.navigate("WorkoutExecution", {
        sessionId: session.id,
        routineId: routine.id,
        prefill,
      });
    } catch (err: any) {
      Alert.alert("Não foi possível iniciar", err?.response?.data?.detail ?? "Tente novamente.");
    }
  }

  function handleOptions(routine: Routine) {
    Alert.alert(routine.name, undefined, [
      { text: "Editar", onPress: () => navigation.navigate("RoutineBuilder", { routineId: routine.id }) },
      {
        text: "Duplicar",
        onPress: async () => {
          try {
            await duplicateRoutine(routine.id);
            listRoutines().then(setRoutines);
          } catch (err: any) {
            Alert.alert("Não foi possível duplicar", err?.response?.data?.detail ?? "Tente novamente.");
          }
        },
      },
      {
        text: "Arquivar",
        onPress: async () => {
          await archiveRoutine(routine.id);
          listRoutines().then(setRoutines);
        },
      },
      {
        text: "Excluir",
        style: "destructive",
        onPress: async () => {
          await deleteRoutine(routine.id);
          listRoutines().then(setRoutines);
        },
      },
      { text: "Cancelar", style: "cancel" },
    ]);
  }

  const limit = user?.plan === "pro" ? ROUTINE_LIMIT.pro : ROUTINE_LIMIT.free;

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.md }}>
        <Text style={[type.h1, { color: colors.textPrimary }]}>Rotinas</Text>
        <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.md }}>
          <TouchableOpacity
            onPress={() => {
              if (user?.plan !== "pro") {
                Alert.alert(
                  "Exclusivo do Pro",
                  "Detecção de platô e sugestão de deload fazem parte do Pro."
                );
                return;
              }
              navigation.navigate("WorkoutInsights");
            }}
          >
            <Text style={[type.caption, { color: colors.primary }]}>Reavaliação</Text>
          </TouchableOpacity>
          <Text style={[type.caption, { color: colors.textSecondary }]}>
            {routines.length}/{limit}
          </Text>
        </View>
      </View>

      <FlatList
        data={routines}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={{ paddingBottom: spacing.lg }}
        renderItem={({ item }) => (
          <View
            style={{
              backgroundColor: colors.surface,
              borderRadius: radius.card,
              borderWidth: 1,
              borderColor: colors.border,
              padding: spacing.md,
              marginBottom: spacing.md,
            }}
          >
            <TouchableOpacity onLongPress={() => handleOptions(item)}>
              <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
                {item.name}
              </Text>
              <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
                {item.exercises.length} exercícios
              </Text>
            </TouchableOpacity>
            <View style={{ flexDirection: "row", gap: spacing.sm }}>
              <View style={{ flex: 1 }}>
                <Button title="Treinar agora" variant="secondary" onPress={() => handleStart(item)} />
              </View>
              <View style={{ flex: 1 }}>
                <Button title="Mais opções" variant="ghost" onPress={() => handleOptions(item)} />
              </View>
            </View>
          </View>
        )}
        ListEmptyComponent={
          <Text style={[type.body, { color: colors.textSecondary }]}>
            Você ainda não tem rotinas. Crie a primeira abaixo.
          </Text>
        }
      />

      <Button
        title={routines.length >= limit ? `Limite de ${limit} rotinas atingido` : "Nova rotina"}
        onPress={() => navigation.navigate("RoutineBuilder", {})}
        disabled={routines.length >= limit}
      />
    </View>
  );
}
