import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, FlatList, Pressable, RefreshControl, Text, TouchableOpacity, View } from "react-native";
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
import { mensagemDeErro } from "../../utils/errorMessage";
import { TrainingCoachHeader } from "../coaching/CoachModuleHeader";

export function RoutineListScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { active, startWorkout } = useActiveWorkout();
  const insets = useSafeAreaInsets();

  const [routines, setRoutines] = useState<Routine[]>([]);
  const [optionsRoutine, setOptionsRoutine] = useState<Routine | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Routine | null>(null);
  // Antes: listRoutines().then(setRoutines) SEM catch. Se essa chamada falhava
  // (timeout/rede), a aba ficava vazia em silêncio — a rotina existia (aparecia
  // no Coaching, que faz outra chamada) mas "sumia" aqui. Agora o erro é
  // visível e recarregável.
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await listRoutines();
      setRoutines(data);
      setLoadError(false);
    } catch {
      setLoadError(true);
    } finally {
      setLoaded(true);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
  }

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
      Alert.alert("Não foi possível iniciar", mensagemDeErro(err, "Tente novamente."));
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
              load();
            } catch (err: any) {
              Alert.alert("Não foi possível duplicar", mensagemDeErro(err, "Tente novamente."));
            }
          },
        },
        {
          label: "Arquivar",
          onPress: async () => {
            await archiveRoutine(optionsRoutine.id);
            load();
          },
        },
        { label: "Excluir", destructive: true, onPress: () => setDeleteTarget(optionsRoutine) },
      ]
    : [];

  return (
    <View
      style={{
        flex: 1,
        backgroundColor: colors.bg,
        padding: spacing.lg,
        // Com treino em andamento, o indicador flutuante fica no canto inferior
        // esquerdo da tela — e cobria a primeira ação da barra fixa. Reservar a
        // altura dele empurra a barra pra cima e deixa os dois clicáveis.
        paddingBottom: spacing.lg + insets.bottom + (active ? 60 : 0),
      }}
    >
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
        style={{ flex: 1 }}
        data={routines}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={{ paddingBottom: spacing.lg }}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />}
        ListHeaderComponent={
          // Cabeçalho do coach (Pro): como o coach monta seu treino + seu
          // treino atual. Some no Free — que vê só as rotinas manuais.
          <TrainingCoachHeader />
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
          loadError ? (
            <Card>
              <View style={{ alignItems: "center", paddingVertical: spacing.lg }}>
                <View
                  style={{
                    width: 64,
                    height: 64,
                    borderRadius: 22,
                    backgroundColor: colors.warning + "22",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: spacing.md,
                  }}
                >
                  <Ionicons name="cloud-offline" size={30} color={colors.warning} />
                </View>
                <Text style={[type.h2, { color: colors.textPrimary, marginBottom: 4 }]}>Não consegui carregar</Text>
                <Text style={[type.bodySmall, { color: colors.textSecondary, textAlign: "center", marginBottom: spacing.md }]}>
                  Suas rotinas estão salvas — foi só a conexão.{"\n"}Puxe pra baixo ou toque pra tentar de novo.
                </Text>
                <Button title="Tentar de novo" variant="secondary" onPress={load} />
              </View>
            </Card>
          ) : !loaded ? null : (
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
          )
        }
      />

      {/* BARRA FIXA das três ações (spec §5.2). Não rola junto com as rotinas:
          a FlatList acima tem flex:1 e é a única área que rola; isto é um irmão
          dela, sempre visível no rodapé.

          Compacta de propósito — as três ações empilhadas em cards grandes
          comiam ~180px de tela e cobriam a lista em celular pequeno. O respiro
          de baixo vem do insets.bottom do container, então a barra encosta na
          área segura sem saltar quando um modal ou menu abre. */}
      <View
        style={{
          paddingTop: spacing.md,
          borderTopWidth: 1,
          borderTopColor: colors.border,
          gap: spacing.sm,
        }}
      >
        <Button title="Nova rotina" icon="+" onPress={() => navigation.navigate("RoutineBuilder", {})} />

        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          {/* 10 métodos consagrados (grátis) — discovery, não atrapalha quem
              já tem rotina montada. */}
          {/* Rótulos curtos de propósito: "Métodos de treino" e "Importar
              treino do Hevy ou Strong" não cabem lado a lado num celular
              estreito e saíam truncados ("Métodos de tr..."). O complemento
              vai na segunda linha, onde há espaço. */}
          <FooterAction
            icon="barbell"
            label="Métodos"
            hint="10 metodologias"
            tint={colors.moduleTraining}
            onPress={() => navigation.navigate("AiHub")}
          />
          {/* Importar: é aqui que quem chegou de outro app procura, e redigitar
              tudo é o motivo nº1 de desistir de trocar. */}
          <FooterAction
            icon="download-outline"
            label="Importar"
            hint="Hevy ou Strong"
            tint={colors.info}
            onPress={() => navigation.navigate("ImportRoutines")}
          />
        </View>
      </View>

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

/** Uma das ações fixas do rodapé. Compacta pra as três caberem sem roubar a
 * área da lista de rotinas. */
function FooterAction({
  icon,
  label,
  hint,
  tint,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  hint: string;
  tint: string;
  onPress: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        flex: 1,
        flexDirection: "row",
        alignItems: "center",
        gap: spacing.sm,
        backgroundColor: colors.surface,
        borderWidth: 1,
        borderColor: colors.border,
        borderRadius: radius.card,
        paddingVertical: spacing.sm,
        paddingHorizontal: spacing.sm,
        opacity: pressed ? 0.75 : 1,
      })}
    >
      <View
        style={{
          width: 32,
          height: 32,
          borderRadius: 11,
          backgroundColor: tint + "1F",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Ionicons name={icon} size={17} color={tint} />
      </View>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "800" }]} numberOfLines={1}>
          {label}
        </Text>
        <Text style={[type.caption, { color: colors.textSecondary, fontSize: 10 }]} numberOfLines={1}>
          {hint}
        </Text>
      </View>
    </Pressable>
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
