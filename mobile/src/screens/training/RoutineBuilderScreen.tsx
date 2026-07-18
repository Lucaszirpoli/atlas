import { Ionicons } from "@expo/vector-icons";
import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import type { Exercise } from "../../api/exercises";
import { createRoutine, getRoutine, updateRoutine } from "../../api/routines";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { useTheme } from "../../theme/ThemeProvider";
import { exercisePickBus } from "./exercisePickBus";
import { mensagemDeErro } from "../../utils/errorMessage";

type BuilderExercise = {
  exercise: Exercise;
  target_sets: number;
  target_reps_min: number;
  target_reps_max: number | null;
  rest_seconds: number;
};

export function RoutineBuilderScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { routineId } = route.params ?? {};

  const [name, setName] = useState("");
  const [exercises, setExercises] = useState<BuilderExercise[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Registra o handler que recebe cada exercício escolhido no picker. Fica
  // ativo enquanto o builder está montado; permite adicionar quantos quiser.
  useEffect(() => {
    exercisePickBus.setHandler((exercise: Exercise) => {
      setExercises((prev) => [
        ...prev,
        { exercise, target_sets: 3, target_reps_min: 8, target_reps_max: 12, rest_seconds: 90 },
      ]);
    });
    return () => exercisePickBus.setHandler(null);
  }, []);

  useEffect(() => {
    if (routineId) {
      getRoutine(routineId).then((routine) => {
        setName(routine.name);
        setExercises(
          routine.exercises.map((e) => ({
            exercise: e.exercise,
            target_sets: e.target_sets,
            target_reps_min: e.target_reps_min,
            target_reps_max: e.target_reps_max,
            rest_seconds: e.rest_seconds,
          }))
        );
      });
    }
  }, [routineId]);

  function updateExercise(index: number, patch: Partial<BuilderExercise>) {
    setExercises((prev) => prev.map((e, i) => (i === index ? { ...e, ...patch } : e)));
  }

  function removeExercise(index: number) {
    setExercises((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSave() {
    if (!name.trim()) {
      Alert.alert("Dê um nome à rotina", "Ex: Treino A - Peito e Tríceps");
      return;
    }
    if (exercises.length === 0) {
      Alert.alert("Adicione ao menos um exercício");
      return;
    }
    setIsSubmitting(true);
    const payload = {
      name: name.trim(),
      exercises: exercises.map((e) => ({
        exercise_id: e.exercise.id,
        target_sets: e.target_sets,
        target_reps_min: e.target_reps_min,
        target_reps_max: e.target_reps_max,
        rest_seconds: e.rest_seconds,
      })),
    };
    try {
      if (routineId) {
        await updateRoutine(routineId, payload);
      } else {
        await createRoutine(payload);
      }
      navigation.goBack();
    } catch (err: any) {
      Alert.alert("Não foi possível salvar", mensagemDeErro(err, "Tente novamente."));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      <Card style={{ marginBottom: spacing.lg }}>
        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>
          Nome da rotina
        </Text>
        {/* Placeholder curto de propósito: o campo usa type.h2 (18px) e num
            celular de 375px sobram ~263px aqui dentro — "Ex: Treino A - Peito
            e Tríceps" pedia ~285px e aparecia cortado no meio, ilegível. */}
        <TextInput
          value={name}
          onChangeText={setName}
          placeholder="Ex: Treino A - Peito"
          placeholderTextColor={colors.textSecondary}
          style={[
            type.h2,
            {
              color: colors.textPrimary,
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.button,
              paddingHorizontal: spacing.md,
              height: 54,
            },
          ]}
        />
      </Card>

      {exercises.map((item, index) => (
        <Card key={`${item.exercise.id}-${index}`} accent={colors.moduleTraining} style={{ marginBottom: spacing.md }}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}>
            <View
              style={{
                width: 30,
                height: 30,
                borderRadius: 10,
                backgroundColor: colors.secondarySoft,
                alignItems: "center",
                justifyContent: "center",
                marginRight: spacing.sm,
              }}
            >
              <Text style={[type.caption, { color: colors.secondary, fontWeight: "800" }]}>{index + 1}</Text>
            </View>
            <Text style={[type.h2, { color: colors.textPrimary, flex: 1, fontSize: 17 }]} numberOfLines={2}>
              {item.exercise.name}
            </Text>
            <TouchableOpacity onPress={() => removeExercise(index)} hitSlop={10}>
              <Ionicons name="trash-outline" size={20} color={colors.danger} />
            </TouchableOpacity>
          </View>

          <View style={{ flexDirection: "row", justifyContent: "space-between", gap: spacing.sm }}>
            <NumberField label="Séries" value={item.target_sets} onChange={(v) => updateExercise(index, { target_sets: v })} />
            <NumberField label="Reps mín" value={item.target_reps_min} onChange={(v) => updateExercise(index, { target_reps_min: v })} />
            <NumberField label="Reps máx" value={item.target_reps_max ?? item.target_reps_min} onChange={(v) => updateExercise(index, { target_reps_max: v })} />
            <NumberField label="Desc. (s)" value={item.rest_seconds} onChange={(v) => updateExercise(index, { rest_seconds: v })} />
          </View>
        </Card>
      ))}

      <TouchableOpacity
        onPress={() => navigation.navigate("ExercisePicker")}
        activeOpacity={0.7}
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          borderWidth: 2,
          borderStyle: "dashed",
          borderColor: colors.primary + "66",
          borderRadius: radius.card,
          paddingVertical: spacing.md,
          marginBottom: spacing.lg,
        }}
      >
        <Ionicons name="add-circle" size={22} color={colors.primary} />
        <Text style={[type.body, { color: colors.primary, fontWeight: "700" }]}>Adicionar exercício</Text>
      </TouchableOpacity>

      <Button title="Salvar rotina" onPress={handleSave} loading={isSubmitting} />
    </ScrollView>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View style={{ alignItems: "center", flex: 1 }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: 4 }]}>{label}</Text>
      <TextInput
        value={String(value)}
        onChangeText={(v) => onChange(Number(v.replace(/[^0-9]/g, "")) || 0)}
        keyboardType="number-pad"
        style={[
          type.body,
          {
            color: colors.textPrimary,
            backgroundColor: colors.surfaceAlt,
            borderRadius: radius.button,
            width: "100%",
            height: 46,
            textAlign: "center",
            fontWeight: "700",
          },
        ]}
      />
    </View>
  );
}
