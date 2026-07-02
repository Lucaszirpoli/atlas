import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { Alert, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import type { Exercise } from "../../api/exercises";
import { createRoutine, getRoutine, updateRoutine } from "../../api/routines";
import { Button } from "../../components/Button";
import { useTheme } from "../../theme/ThemeProvider";

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
  const { routineId, pickedExercise } = route.params ?? {};

  const [name, setName] = useState("");
  const [exercises, setExercises] = useState<BuilderExercise[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

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

  useEffect(() => {
    if (pickedExercise) {
      setExercises((prev) => [
        ...prev,
        { exercise: pickedExercise, target_sets: 3, target_reps_min: 8, target_reps_max: 12, rest_seconds: 90 },
      ]);
      navigation.setParams({ pickedExercise: undefined });
    }
  }, [pickedExercise]);

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
      Alert.alert("Não foi possível salvar", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}>
      <TextInput
        value={name}
        onChangeText={setName}
        placeholder="Nome da rotina (ex: Treino A - Peito e Tríceps)"
        placeholderTextColor={colors.textSecondary}
        style={[
          type.h2,
          {
            color: colors.textPrimary,
            borderBottomWidth: 2,
            borderBottomColor: colors.primary,
            paddingVertical: spacing.sm,
            marginBottom: spacing.lg,
          },
        ]}
      />

      {exercises.map((item, index) => (
        <View
          key={`${item.exercise.id}-${index}`}
          style={{
            backgroundColor: colors.surface,
            borderRadius: radius.card,
            borderWidth: 1,
            borderColor: colors.border,
            padding: spacing.md,
            marginBottom: spacing.md,
          }}
        >
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>{item.exercise.name}</Text>
            <TouchableOpacity onPress={() => removeExercise(index)}>
              <Text style={[type.bodySmall, { color: colors.danger }]}>Remover</Text>
            </TouchableOpacity>
          </View>

          <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.sm }}>
            <NumberField
              label="Séries"
              value={item.target_sets}
              onChange={(v) => updateExercise(index, { target_sets: v })}
            />
            <NumberField
              label="Reps mín."
              value={item.target_reps_min}
              onChange={(v) => updateExercise(index, { target_reps_min: v })}
            />
            <NumberField
              label="Reps máx."
              value={item.target_reps_max ?? item.target_reps_min}
              onChange={(v) => updateExercise(index, { target_reps_max: v })}
            />
            <NumberField
              label="Descanso (s)"
              value={item.rest_seconds}
              onChange={(v) => updateExercise(index, { rest_seconds: v })}
            />
          </View>
        </View>
      ))}

      <Button
        title="+ Adicionar exercício"
        variant="ghost"
        onPress={() => navigation.navigate("ExercisePicker")}
      />

      <View style={{ marginTop: spacing.lg }}>
        <Button title="Salvar rotina" onPress={handleSave} loading={isSubmitting} />
      </View>
    </ScrollView>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  const { colors, type, spacing } = useTheme();
  return (
    <View style={{ alignItems: "center" }}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>
        {label}
      </Text>
      <TextInput
        value={String(value)}
        onChangeText={(v) => onChange(Number(v.replace(/[^0-9]/g, "")) || 0)}
        keyboardType="number-pad"
        style={[
          type.body,
          {
            color: colors.textPrimary,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: 6,
            width: 56,
            textAlign: "center",
            paddingVertical: spacing.xs,
          },
        ]}
      />
    </View>
  );
}
