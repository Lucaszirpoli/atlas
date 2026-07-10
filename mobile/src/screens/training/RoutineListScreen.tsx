import { Ionicons } from "@expo/vector-icons";
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
import { ActionSheet, type ActionSheetOption } from "../../components/ActionSheet";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useActiveWorkout } from "../../context/ActiveWorkoutContext";
import { useTheme } from "../../theme/ThemeProvider";

export function RoutineListScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { startWorkout } = useActiveWorkout();

  const [routines, setRoutines] = useState<Routine[]>([]);
  const [optionsRoutine, setOptionsRoutine] = useState<Routine | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Routine | null>(null);

  useFocusEffect(
    useCallback(() => {
      listRoutines().then(setRoutines);
    }, [])
  );

  async function handleStart(routine: Routine) {
    try {
      const { session, prefill } = await startWorkoutSession(routine.id);
      startWorkout({ sessionId: session.id, routineId: routine.id, routineName: routine.name, prefill });
      navigation.navigate("WorkoutExecution", {
        sessionId: session.id,
        routineId: routine.id,
        prefill,
      });
    } catch (err: any) {
      Alert.alert("Não foi possível iniciar", err?.response?.data?.detail ?? "Tente novamente.");
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    await deleteRoutine(deleteTarget.id);
    setDeleteTarget(null);
    listRoutines().then(setRoutines);
  }

  // Opções da rotina — ActionSheet (Modal) em vez de Alert.alert com vários
  // botões, que é um no-op silencioso no React Native Web (por isso os "..."
  // não faziam nada quando testado no navegador). A confirmação de exclusão
  // também usa Modal (ConfirmDialog) pelo mesmo motivo — Alert.alert de
  // confirmação não funciona no navegador nem com só 2 botões.
  const routineOptions: ActionSheetOption[] = optionsRoutine
    ? [
        { label: "Editar", onPress: () => navigation.navigate("RoutineBuilder", { routineId: optionsRoutine.id }) },
        {
          label: "Duplicar",
          onPress: async () => {
            try {
              await duplicateRoutine(optionsRoutine.id);
              listRoutines().then(setRoutines);
            } catch (err: any) {
              Alert.alert("Não foi possível duplicar", err?.response?.data?.detail ?? "Tente novamente.");
            }
          },
        },
        {
          label: "Arquivar",
          onPress: async () => {
            await archiveRoutine(optionsRoutine.id);
            listRoutines().then(setRoutines);
          },
        },
        { label: "Excluir", destructive: true, onPress: () => setDeleteTarget(optionsRoutine) },
      ]
    : [];

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
      {/* Header interno */}
      <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}>
        <View
          style={{
            backgroundColor: colors.surfaceAlt,
            borderRadius: radius.pill,
            paddingVertical: 4,
            paddingHorizontal: 12,
          }}
        >
          <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700" }]}>
            {routines.length} {routines.length === 1 ? "rotina" : "rotinas"}
          </Text>
        </View>
      </View>

      <FlatList
        data={routines}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={{ paddingBottom: spacing.lg }}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          // Entrada compacta pro gerador por metodologia (não é IA — é montagem
          // fiel ao método consagrado, por isso o texto não fala em "IA").
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={() => navigation.navigate("AiHub")}
            style={{
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: colors.surface,
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: radius.card,
              paddingVertical: spacing.sm,
              paddingHorizontal: spacing.md,
              marginBottom: spacing.md,
            }}
          >
            <Ionicons name="book-outline" size={18} color={colors.secondary} />
            <View style={{ flex: 1, marginLeft: spacing.sm }}>
              <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]}>
                Montar treino por metodologia
              </Text>
              <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
                Mentzer, FST-7, 5/3/1… fiel ao método
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        }
        renderItem={({ item }) => {
          const totalSets = item.exercises.reduce((s, e) => s + e.target_sets, 0);
          return (
            <Card accent={colors.moduleTraining} style={{ marginBottom: spacing.md }}>
              <TouchableOpacity onLongPress={() => setOptionsRoutine(item)} activeOpacity={0.85}>
                <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
                  <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>{item.name}</Text>
                  <TouchableOpacity onPress={() => setOptionsRoutine(item)} hitSlop={10}>
                    <Ionicons name="ellipsis-horizontal" size={20} color={colors.textSecondary} />
                  </TouchableOpacity>
                </View>
                <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.md }}>
                  <MetaInfo icon="list" text={`${item.exercises.length} exercícios`} />
                  <MetaInfo icon="repeat" text={`${totalSets} séries`} />
                </View>
              </TouchableOpacity>
              <Button title="Treinar agora" variant="secondary" icon="🏋️" onPress={() => handleStart(item)} />
            </Card>
          );
        }}
        ListEmptyComponent={
          <Card>
            <View style={{ alignItems: "center", paddingVertical: spacing.lg }}>
              <View
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: 22,
                  backgroundColor: colors.secondarySoft,
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: spacing.md,
                }}
              >
                <Ionicons name="barbell" size={30} color={colors.secondary} />
              </View>
              <Text style={[type.h2, { color: colors.textPrimary, marginBottom: 4 }]}>Nenhuma rotina ainda</Text>
              <Text style={[type.bodySmall, { color: colors.textSecondary, textAlign: "center" }]}>
                Crie sua primeira rotina de treino{"\n"}e comece a registrar sua evolução.
              </Text>
            </View>
          </Card>
        }
      />

      <Button title="Nova rotina" icon="+" onPress={() => navigation.navigate("RoutineBuilder", {})} />

      <ActionSheet
        visible={optionsRoutine != null}
        onClose={() => setOptionsRoutine(null)}
        title={optionsRoutine?.name}
        options={routineOptions}
      />
      <ConfirmDialog
        visible={deleteTarget != null}
        onClose={() => setDeleteTarget(null)}
        title="Excluir rotina"
        message={`Tem certeza que quer excluir "${deleteTarget?.name}"? Isso não afeta seu histórico de treinos já registrados.`}
        confirmLabel="Excluir"
        destructive
        onConfirm={confirmDelete}
      />
    </View>
  );
}

function MetaInfo({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  const { colors, type } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
      <Ionicons name={icon} size={14} color={colors.textSecondary} />
      <Text style={[type.caption, { color: colors.textSecondary }]}>{text}</Text>
    </View>
  );
}
