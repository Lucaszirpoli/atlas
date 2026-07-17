import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, FlatList, Pressable, Text, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

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
  const insets = useSafeAreaInsets();

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
      startWorkout({
        sessionId: session.id,
        routineId: routine.id,
        routineName: routine.name,
        prefill,
        startedAt: new Date(session.started_at).getTime(),
      });
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
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg, paddingBottom: spacing.lg + insets.bottom }}>
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
        {/* Histórico: onde a pessoa exclui um treino salvo por engano. */}
        <TouchableOpacity
          onPress={() => navigation.navigate("WorkoutHistory")}
          style={{ flexDirection: "row", alignItems: "center", gap: 4, marginLeft: "auto" }}
          hitSlop={8}
        >
          <Ionicons name="time-outline" size={16} color={colors.textSecondary} />
          <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700" }]}>Histórico</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={routines}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={{ paddingBottom: spacing.lg }}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          // Porta de entrada da montagem de treino: dentro tem os 10 métodos
          // consagrados (grátis) e a criação por IA conversacional (Pro).
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={() => navigation.navigate("AiHub")}
            style={{
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: colors.secondary,
              borderRadius: radius.card,
              padding: spacing.md,
              marginBottom: spacing.md,
            }}
          >
            <View
              style={{
                width: 46,
                height: 46,
                borderRadius: 15,
                backgroundColor: "rgba(255,255,255,0.22)",
                alignItems: "center",
                justifyContent: "center",
                marginRight: spacing.md,
              }}
            >
              <Ionicons name="sparkles" size={24} color="#FFFFFF" />
            </View>
            <View style={{ flex: 1 }}>
              <Text style={[type.h2, { color: "#FFFFFF", fontSize: 16 }]}>Monte um treino pro seu perfil</Text>
              <Text style={[type.caption, { color: "rgba(255,255,255,0.9)" }]} numberOfLines={2}>
                Métodos consagrados ou um treino feito pela IA pra você
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={20} color="#FFFFFF" />
          </TouchableOpacity>
        }
        renderItem={({ item }) => {
          const totalSets = item.exercises.reduce((s, e) => s + e.target_sets, 0);
          return (
            <Card accent={colors.moduleTraining} style={{ marginBottom: spacing.md }}>
              {/* Toque no corpo do card abre a PRÉVIA do treino (exercícios,
                  séries e pesos da última vez) sem iniciar. O botão embaixo
                  inicia de verdade. Editar/duplicar/etc ficam no menu "...". */}
              <TouchableOpacity
                onPress={() => navigation.navigate("WorkoutPreview", { routineId: item.id })}
                onLongPress={() => setOptionsRoutine(item)}
                activeOpacity={0.85}
              >
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
              <Button title="Treinar agora" variant="secondary" onPress={() => handleStart(item)} />
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

      {/* Importar fica logo abaixo do "Nova rotina": é aqui que quem chegou de
          outro app procura, e redigitar tudo é o motivo nº1 de desistir de
          trocar. Discreto de propósito — serve uma vez na vida do usuário. */}
      <Pressable
        onPress={() => navigation.navigate("ImportRoutines")}
        style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", paddingTop: spacing.md }}
      >
        <Ionicons name="download-outline" size={17} color={colors.textSecondary} />
        <Text style={[type.bodySmall, { color: colors.textSecondary, marginLeft: 6 }]}>
          Já treina no Hevy ou Strong? Importar treinos
        </Text>
      </Pressable>

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
