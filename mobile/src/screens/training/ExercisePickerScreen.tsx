import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { FlatList, Pressable, Text, TextInput, View } from "react-native";

import { listExercises, type Exercise } from "../../api/exercises";
import { useTheme } from "../../theme/ThemeProvider";

export function ExercisePickerScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();

  const [query, setQuery] = useState("");
  const [exercises, setExercises] = useState<Exercise[]>([]);

  useEffect(() => {
    const timeout = setTimeout(() => {
      listExercises(query.trim() ? { q: query.trim() } : undefined).then(setExercises);
    }, 250);
    return () => clearTimeout(timeout);
  }, [query]);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Buscar exercício..."
        placeholderTextColor={colors.textSecondary}
        style={[
          type.body,
          {
            color: colors.textPrimary,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.button,
            paddingHorizontal: spacing.md,
            height: 48,
            marginBottom: spacing.md,
            backgroundColor: colors.surface,
          },
        ]}
      />
      <FlatList
        data={exercises}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <Pressable
            onPress={() => navigation.navigate("RoutineBuilder", { pickedExercise: item })}
            style={{ paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border }}
          >
            <Text style={[type.body, { color: colors.textPrimary }]}>{item.name}</Text>
            <Text style={[type.caption, { color: colors.textSecondary }]}>
              {item.primary_muscle_group} · {item.equipment}
            </Text>
          </Pressable>
        )}
      />
    </View>
  );
}
