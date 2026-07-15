import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { FlatList, Image, Pressable, Text, TextInput, View } from "react-native";

import { resolveMediaUrl } from "../../api/client";
import { listExercises, type Exercise, type MuscleGroup } from "../../api/exercises";
import { ExerciseFigure } from "../../components/ExerciseFigure";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";
import { classifyMovementPattern } from "../../utils/exercisePattern";
import { exercisePickBus } from "./exercisePickBus";

const MUSCLE_LABELS: Partial<Record<MuscleGroup, string>> = {
  chest: "Peito",
  back: "Costas",
  shoulders: "Ombros",
  biceps: "Bíceps",
  triceps: "Tríceps",
  quads: "Quadríceps",
  hamstrings: "Posterior",
  glutes: "Glúteos",
  calves: "Panturrilha",
  abs: "Abdômen",
  cardio: "Cardio",
};

export function ExercisePickerScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();

  const [query, setQuery] = useState("");
  const [muscle, setMuscle] = useState<MuscleGroup | null>(null);
  const [exercises, setExercises] = useState<Exercise[]>([]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      listExercises({
        ...(query.trim() ? { q: query.trim() } : {}),
        ...(muscle ? { muscle_group: muscle } : {}),
      }).then(setExercises);
    }, 250);
    return () => clearTimeout(timeout);
  }, [query, muscle]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: colors.surface,
          borderRadius: radius.pill,
          paddingHorizontal: spacing.md,
          height: 50,
          borderWidth: 1,
          borderColor: colors.border,
          marginBottom: spacing.sm,
        }}
      >
        <Ionicons name="search" size={18} color={colors.textSecondary} />
        <TextInput
          value={query}
          onChangeText={setQuery}
          placeholder="Buscar exercício..."
          placeholderTextColor={colors.textSecondary}
          style={[type.body, { flex: 1, color: colors.textPrimary, marginLeft: spacing.sm, height: "100%" }]}
        />
      </View>

      {/* Filtro por grupo muscular */}
      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        data={Object.entries(MUSCLE_LABELS)}
        keyExtractor={([key]) => key}
        style={{ flexGrow: 0, marginBottom: spacing.sm }}
        renderItem={({ item: [key, label] }) => (
          <View style={{ marginRight: spacing.xs }}>
            <OptionButton
              compact
              label={label!}
              selected={muscle === key}
              onPress={() => setMuscle(muscle === key ? null : (key as MuscleGroup))}
            />
          </View>
        )}
      />

      <FlatList
        data={exercises}
        keyExtractor={(item) => String(item.id)}
        showsVerticalScrollIndicator={false}
        renderItem={({ item }) => (
          <Pressable
            onPress={() => {
              exercisePickBus.pick(item);
              navigation.goBack();
            }}
            style={({ pressed }) => ({
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: colors.surface,
              borderRadius: radius.button,
              padding: spacing.md,
              marginBottom: spacing.sm,
              opacity: pressed ? 0.8 : 1,
            })}
          >
            {item.video_url ? (
              <Image
                source={{ uri: resolveMediaUrl(item.video_url) ?? undefined }}
                style={{ width: 46, height: 46, borderRadius: 14, marginRight: spacing.md, backgroundColor: colors.surfaceAlt }}
              />
            ) : (
              <View
                style={{
                  width: 46,
                  height: 46,
                  borderRadius: 14,
                  backgroundColor: colors.secondarySoft,
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: spacing.md,
                }}
              >
                <ExerciseFigure
                  pattern={classifyMovementPattern(item.name, item.primary_muscle_group, item.equipment)}
                  size={46}
                  animated={false}
                />
              </View>
            )}
            <View style={{ flex: 1 }}>
              <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600" }]}>{item.name}</Text>
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
                {MUSCLE_LABELS[item.primary_muscle_group] ?? item.primary_muscle_group} · {item.equipment}
              </Text>
            </View>
            <Ionicons name="add-circle" size={26} color={colors.primary} />
          </Pressable>
        )}
      />
    </View>
  );
}
