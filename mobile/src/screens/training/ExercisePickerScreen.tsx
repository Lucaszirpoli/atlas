import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { FlatList, Image, Pressable, Text, TextInput, View } from "react-native";

import { resolveMediaUrl } from "../../api/client";
import {
  createCustomExercise,
  listExercises,
  type Equipment,
  type Exercise,
  type MuscleGroup,
} from "../../api/exercises";
import { Button } from "../../components/Button";
import { ExerciseFigure } from "../../components/ExerciseFigure";
import { InfoDialog } from "../../components/InfoDialog";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";
import { classifyMovementPattern } from "../../utils/exercisePattern";
import { exercisePickBus } from "./exercisePickBus";
import { mensagemDeErro } from "../../utils/errorMessage";

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

const EQUIP_LABELS: { value: Equipment; label: string }[] = [
  { value: "barbell", label: "Barra" },
  { value: "dumbbell", label: "Halteres" },
  { value: "machine", label: "Máquina" },
  { value: "cable", label: "Polia" },
  { value: "bodyweight", label: "Peso do corpo" },
  { value: "smith_machine", label: "Smith" },
  { value: "kettlebell", label: "Kettlebell" },
  { value: "band", label: "Faixa" },
  { value: "other", label: "Outro" },
];

export function ExercisePickerScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();

  const [query, setQuery] = useState("");
  const [muscle, setMuscle] = useState<MuscleGroup | null>(null);
  const [exercises, setExercises] = useState<Exercise[]>([]);

  // Cadastro de exercício próprio. O endpoint POST /exercises existia desde o
  // começo e o app nunca chamou — não havia como cadastrar o aparelho da sua
  // academia que não está na base.
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newMuscle, setNewMuscle] = useState<MuscleGroup>("chest");
  const [newEquip, setNewEquip] = useState<Equipment>("machine");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function startCreating() {
    setNewName(query.trim());
    setNewMuscle(muscle ?? "chest");
    setNewEquip("machine");
    setCreating(true);
  }

  async function handleCreate() {
    const nome = newName.trim();
    if (!nome) return;
    setSaving(true);
    try {
      const ex = await createCustomExercise({
        name: nome,
        primary_muscle_group: newMuscle,
        equipment: newEquip,
      });
      // Já entrega o exercício pra quem pediu — o motivo de cadastrar era usá-lo.
      exercisePickBus.pick(ex);
      navigation.goBack();
    } catch (err: any) {
      setError(mensagemDeErro(err, "Não consegui cadastrar agora."));
    } finally {
      setSaving(false);
    }
  }

  useEffect(() => {
    const timeout = setTimeout(() => {
      listExercises({
        ...(query.trim() ? { q: query.trim() } : {}),
        ...(muscle ? { muscle_group: muscle } : {}),
      }).then(setExercises);
    }, 250);
    return () => clearTimeout(timeout);
  }, [query, muscle]);

  if (creating) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
        <Pressable
          onPress={() => setCreating(false)}
          style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}
        >
          <Ionicons name="chevron-back" size={20} color={colors.primary} />
          <Text style={[type.body, { color: colors.primary, fontWeight: "600" }]}>Voltar</Text>
        </Pressable>

        <Text style={[type.h1, { color: colors.textPrimary }]}>Novo exercício</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, marginBottom: spacing.lg }]}>
          Fica salvo só pra você e já entra no seu treino.
        </Text>

        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>Nome</Text>
        <TextInput
          value={newName}
          onChangeText={setNewName}
          placeholder="Ex: Remada cavalinho da minha academia"
          placeholderTextColor={colors.textSecondary}
          style={[
            type.body,
            {
              color: colors.textPrimary,
              backgroundColor: colors.surface,
              borderRadius: radius.button,
              borderWidth: 1,
              borderColor: colors.border,
              paddingHorizontal: spacing.md,
              height: 52,
              marginBottom: spacing.lg,
            },
          ]}
        />

        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>Músculo principal</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginBottom: spacing.lg }}>
          {(Object.keys(MUSCLE_LABELS) as MuscleGroup[]).map((m) => (
            <Pressable
              key={m}
              onPress={() => setNewMuscle(m)}
              style={{
                backgroundColor: newMuscle === m ? colors.primary : colors.surface,
                borderWidth: 1,
                borderColor: newMuscle === m ? colors.primary : colors.border,
                borderRadius: 999,
                paddingVertical: 8,
                paddingHorizontal: 13,
              }}
            >
              <Text style={[type.caption, { color: newMuscle === m ? colors.textOnPrimary : colors.textPrimary }]}>
                {MUSCLE_LABELS[m]}
              </Text>
            </Pressable>
          ))}
        </View>

        <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>Equipamento</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginBottom: spacing.xl }}>
          {EQUIP_LABELS.map((e) => (
            <Pressable
              key={e.value}
              onPress={() => setNewEquip(e.value)}
              style={{
                backgroundColor: newEquip === e.value ? colors.primary : colors.surface,
                borderWidth: 1,
                borderColor: newEquip === e.value ? colors.primary : colors.border,
                borderRadius: 999,
                paddingVertical: 8,
                paddingHorizontal: 13,
              }}
            >
              <Text style={[type.caption, { color: newEquip === e.value ? colors.textOnPrimary : colors.textPrimary }]}>
                {e.label}
              </Text>
            </Pressable>
          ))}
        </View>

        <Button title="Cadastrar e usar" onPress={handleCreate} loading={saving} disabled={!newName.trim()} />
        <InfoDialog
          visible={error !== null}
          onClose={() => setError(null)}
          title="Não foi possível cadastrar"
          message={error ?? undefined}
        />
      </View>
    );
  }

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
        // Sem resultado, o caminho natural é cadastrar o que faltou — a base
        // não tem todo aparelho de toda academia, e a importação de outro app
        // também deixa nomes sem par.
        ListEmptyComponent={
          <Pressable
            onPress={startCreating}
            style={{
              backgroundColor: colors.surface,
              borderRadius: radius.button,
              borderWidth: 1,
              borderColor: colors.border,
              borderStyle: "dashed",
              padding: spacing.lg,
              alignItems: "center",
            }}
          >
            <Ionicons name="add-circle-outline" size={26} color={colors.primary} />
            <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600", marginTop: spacing.xs }]}>
              {query.trim() ? `Cadastrar "${query.trim()}"` : "Cadastrar um exercício"}
            </Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, textAlign: "center" }]}>
              Não achou? Crie o seu — fica salvo só pra você.
            </Text>
          </Pressable>
        }
        ListFooterComponent={
          exercises.length > 0 ? (
            <Pressable
              onPress={startCreating}
              style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", paddingVertical: spacing.md }}
            >
              <Ionicons name="add-circle-outline" size={18} color={colors.primary} />
              <Text style={[type.bodySmall, { color: colors.primary, fontWeight: "600", marginLeft: 6 }]}>
                Não achou? Cadastrar exercício
              </Text>
            </Pressable>
          ) : null
        }
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
