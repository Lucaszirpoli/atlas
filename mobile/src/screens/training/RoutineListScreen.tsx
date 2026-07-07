import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, FlatList, Text, TouchableOpacity, View } from "react-native";

import { getVolumeEvolution, type VolumePoint } from "../../api/evolution";
import {
  archiveRoutine,
  deleteRoutine,
  duplicateRoutine,
  listRoutines,
  type Routine,
} from "../../api/routines";
import { startWorkoutSession } from "../../api/workoutSessions";
import { AiEntryCard } from "../../components/AiEntryCard";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { HelpDot } from "../../components/HelpDot";
import { LineChart, type ChartPoint } from "../../components/LineChart";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

const ROUTINE_LIMIT = { free: 3, pro: 7 };

function startOfWeekIso(): string {
  const d = new Date();
  d.setDate(d.getDate() - d.getDay());
  d.setHours(0, 0, 0, 0);
  return d.toISOString();
}

export function RoutineListScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();

  const [routines, setRoutines] = useState<Routine[]>([]);
  const [volume, setVolume] = useState<VolumePoint[]>([]);

  useFocusEffect(
    useCallback(() => {
      listRoutines().then(setRoutines);
      getVolumeEvolution().then(setVolume).catch(() => {});
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
  const atLimit = routines.length >= limit;

  const weekStart = startOfWeekIso();
  const workoutsThisWeek = volume.filter((v) => v.date >= weekStart).length;
  const volumeSeries: ChartPoint[] = volume.map((p) => ({ x: new Date(p.date).getTime(), y: p.volume_kg }));

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
      {/* Header interno */}
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.md }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
          <View
            style={{
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.pill,
              paddingVertical: 4,
              paddingHorizontal: 12,
            }}
          >
            <Text style={[type.caption, { color: atLimit ? colors.secondary : colors.textSecondary, fontWeight: "700" }]}>
              {routines.length}/{limit} rotinas
            </Text>
          </View>
        </View>
        <TouchableOpacity
          onPress={() => {
            if (user?.plan !== "pro") {
              Alert.alert("Exclusivo do Pro", "Detecção de platô e sugestão de deload fazem parte do Pro.");
              return;
            }
            navigation.navigate("WorkoutInsights");
          }}
          style={{ flexDirection: "row", alignItems: "center", gap: 4 }}
        >
          <Ionicons name="pulse" size={16} color={colors.secondary} />
          <Text style={[type.caption, { color: colors.secondary, fontWeight: "700" }]}>Reavaliação</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={routines}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={{ paddingBottom: spacing.lg }}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={
          <>
            {/* Entrada da IA — o recurso mais poderoso do módulo, em 1 toque */}
            <AiEntryCard
              title="Monte seu treino com IA personalizada"
              subtitle="Diz seu objetivo, dias disponíveis e equipamento — a IA monta pra você"
              prompt="Monte um treino personalizado pra mim, considerando meu objetivo, meus dias disponíveis e o equipamento que tenho acesso."
            />
            {volume.length >= 2 ? (
              <TouchableOpacity activeOpacity={0.85} onPress={() => navigation.navigate("Evolution")}>
                <Card style={{ marginBottom: spacing.md }}>
                  <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
                    <Ionicons name="stats-chart" size={18} color={colors.secondary} />
                    <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8, flex: 1, fontSize: 17 }]}>
                      Volume por treino
                    </Text>
                    <Text style={[type.caption, { color: colors.secondary, fontWeight: "700" }]}>
                      {workoutsThisWeek} esta semana
                    </Text>
                    <HelpDot
                      title="Volume"
                      text="Peso × repetições somado em cada treino. Ver a linha subir ao longo das semanas é sinal de progresso. Toque para a evolução completa."
                    />
                  </View>
                  <LineChart
                    series={[{ data: volumeSeries, color: colors.secondary, showDots: true }]}
                    height={130}
                    formatY={(v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}t` : `${Math.round(v)}`)}
                  />
                </Card>
              </TouchableOpacity>
            ) : null}
          </>
        }
        renderItem={({ item }) => {
          const totalSets = item.exercises.reduce((s, e) => s + e.target_sets, 0);
          return (
            <Card accent={colors.moduleTraining} style={{ marginBottom: spacing.md }}>
              <TouchableOpacity onLongPress={() => handleOptions(item)} activeOpacity={0.85}>
                <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
                  <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>{item.name}</Text>
                  <TouchableOpacity onPress={() => handleOptions(item)} hitSlop={10}>
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

      <Button
        title={atLimit ? `Limite de ${limit} rotinas atingido` : "Nova rotina"}
        icon={atLimit ? undefined : "+"}
        onPress={() => navigation.navigate("RoutineBuilder", {})}
        disabled={atLimit}
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
