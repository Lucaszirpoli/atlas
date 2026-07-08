import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, Text, TouchableOpacity, View } from "react-native";

import {
  generateTraining,
  getTrainingMethods,
  type GenerateTrainingResult,
  type TrainingMethod,
} from "../../api/ai";
import { createRoutine } from "../../api/routines";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

const EXP_LABEL: Record<string, string> = {
  beginner: "Iniciante+",
  intermediate: "Intermediário+",
  advanced: "Avançado",
};

/** Extrai o primeiro inteiro de um texto ("2 séries" -> 2, "6-8" -> 6). */
function firstInt(s: string, fallback: number): number {
  const m = s.match(/\d+/);
  return m ? Number(m[0]) : fallback;
}
function repsRange(s: string): [number, number | null] {
  const nums = (s.match(/\d+/g) ?? []).map(Number);
  if (nums.length === 0) return [8, 12];
  if (nums.length === 1) return [nums[0], null];
  return [nums[0], nums[1]];
}

export function AiHubScreen() {
  const { colors, type, spacing } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();

  const [methods, setMethods] = useState<TrainingMethod[]>([]);
  const [selected, setSelected] = useState<TrainingMethod | null>(null);
  const [days, setDays] = useState<number | null>(null);
  const [result, setResult] = useState<GenerateTrainingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [savingIndex, setSavingIndex] = useState<number | null>(null);
  const [savedIndices, setSavedIndices] = useState<Set<number>>(new Set());

  useEffect(() => {
    getTrainingMethods()
      .then(setMethods)
      .catch(() => {});
  }, []);

  async function handleGenerate(method: TrainingMethod, d: number) {
    setLoading(true);
    setResult(null);
    setSavedIndices(new Set());
    try {
      const r = await generateTraining({ method_key: method.key, available_days: d });
      setResult(r);
    } catch (err: any) {
      Alert.alert("Não consegui gerar", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveSession(
    session: GenerateTrainingResult["plan"]["sessions"][number],
    sessionIndex: number
  ) {
    if (!result) return;
    setSavingIndex(sessionIndex);
    try {
      const exercises = session.slots
        .filter((s) => s.exercise_id != null)
        .map((s) => {
          const [rmin, rmax] = repsRange(s.reps);
          return {
            exercise_id: s.exercise_id as number,
            target_sets: firstInt(s.sets, 3),
            target_reps_min: rmin,
            target_reps_max: rmax,
            rest_seconds: firstInt(s.rest_seconds ?? "", 90),
            notes: s.note ?? null,
          };
        });
      await createRoutine({
        name: `${result.plan.method_name} — ${session.focus}`,
        exercises,
      });
      setSavedIndices((prev) => new Set(prev).add(sessionIndex));
    } catch (err: any) {
      if (err?.response?.status === 409) {
        // Limite de rotinas ativas atingido (3 Free / 7 Pro) — o backend já
        // devolve uma mensagem amigável explicando o limite e o plano atual.
        Alert.alert("Limite de rotinas atingido", err.response.data?.detail ?? "Arquive uma rotina para criar outra.");
      } else {
        Alert.alert("Não consegui salvar", err?.response?.data?.detail ?? "Tente novamente.");
      }
    } finally {
      setSavingIndex(null);
    }
  }

  // --- Passo 3: plano gerado ------------------------------------------------
  if (result) {
    const p = result.plan;
    return (
      <ScrollView
        style={{ backgroundColor: colors.bg }}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      >
        <TouchableOpacity onPress={() => setResult(null)} style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}>
          <Ionicons name="chevron-back" size={20} color={colors.primary} />
          <Text style={[type.body, { color: colors.primary, fontWeight: "600" }]}>Escolher outro método</Text>
        </TouchableOpacity>

        <Text style={[type.h1, { color: colors.textPrimary }]}>{p.method_name}</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
          {p.author} · {p.days_per_week} dias/semana{p.phase_context ? ` · ${p.phase_context}` : ""}
        </Text>

        {/* Selo de fidelidade — a promessa central do recurso */}
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 6,
            backgroundColor: result.is_faithful ? colors.success + "22" : colors.warning + "22",
            borderRadius: 12,
            paddingVertical: 8,
            paddingHorizontal: 12,
            marginTop: spacing.md,
          }}
        >
          <Ionicons
            name={result.is_faithful ? "shield-checkmark" : "alert-circle"}
            size={16}
            color={result.is_faithful ? colors.success : colors.warning}
          />
          <Text style={[type.caption, { color: colors.textPrimary, flex: 1 }]}>
            {result.is_faithful
              ? "Plano validado: segue as regras do método (frequência, proporção, ordem)."
              : "Atenção: algumas regras não puderam ser respeitadas — veja as notas."}
          </Text>
        </View>

        {result.intro ? (
          <Card style={{ marginTop: spacing.md }}>
            <Text style={[type.body, { color: colors.textPrimary }]}>{result.intro}</Text>
          </Card>
        ) : null}
        {result.ai_locked ? (
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
            💡 O plano é fiel ao método. Assine o Pro para receber a explicação e as dicas da IA por exercício.
          </Text>
        ) : null}

        {p.notes.map((n, i) => (
          <Text key={i} style={[type.caption, { color: colors.warning, marginTop: spacing.sm }]}>
            ⚠️ {n}
          </Text>
        ))}

        {p.sessions.map((session, si) => (
          <Card key={si} style={{ marginTop: spacing.md }}>
            <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
              <View style={{ flex: 1 }}>
                <Text style={[type.h2, { color: colors.textPrimary, fontSize: 16 }]}>
                  {session.day_label} · {session.focus}
                </Text>
                {session.phase_name ? (
                  <Text style={[type.caption, { color: colors.textSecondary }]}>{session.phase_name}</Text>
                ) : null}
              </View>
              {savingIndex === si ? (
                <ActivityIndicator color={colors.primary} />
              ) : savedIndices.has(si) ? (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                  <Ionicons name="checkmark-circle" size={26} color={colors.success} />
                </View>
              ) : (
                <TouchableOpacity onPress={() => handleSaveSession(session, si)} disabled={savingIndex != null}>
                  <Ionicons name="add-circle" size={26} color={colors.primary} />
                </TouchableOpacity>
              )}
            </View>
            {session.slots.map((slot, i) => (
              <View
                key={i}
                style={{
                  paddingVertical: spacing.sm,
                  borderTopWidth: i === 0 ? 0 : 1,
                  borderTopColor: colors.border,
                }}
              >
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  <View
                    style={{
                      backgroundColor: slot.is_compound ? colors.moduleTraining + "33" : colors.secondary + "22",
                      borderRadius: 6,
                      paddingHorizontal: 6,
                      paddingVertical: 1,
                    }}
                  >
                    <Text style={[type.caption, { color: slot.is_compound ? colors.moduleTraining : colors.secondary, fontSize: 10, fontWeight: "700" }]}>
                      {slot.is_compound ? "COMPOSTO" : "ISOLADO"}
                    </Text>
                  </View>
                  <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600", flex: 1 }]}>
                    {slot.order}. {slot.exercise_name}
                  </Text>
                </View>
                <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
                  {slot.sets} × {slot.reps}
                  {slot.tempo ? ` · cadência ${slot.tempo}` : ""}
                  {slot.rest_seconds ? ` · descanso ${slot.rest_seconds}s` : ""}
                  {slot.rir ? ` · RIR ${slot.rir}` : ""}
                </Text>
                {slot.note ? (
                  <Text style={[type.caption, { color: colors.primary, marginTop: 2 }]}>💬 {slot.note}</Text>
                ) : null}
              </View>
            ))}
          </Card>
        ))}

        <Card style={{ marginTop: spacing.md }}>
          <Text style={[type.caption, { color: colors.textSecondary }]}>
            <Text style={{ fontWeight: "700", color: colors.textPrimary }}>Progressão: </Text>
            {p.progression_rule}
          </Text>
          {p.deload_rule ? (
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
              <Text style={{ fontWeight: "700", color: colors.textPrimary }}>Deload: </Text>
              {p.deload_rule}
            </Text>
          ) : null}
          {p.mesocycle ? (
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
              <Text style={{ fontWeight: "700", color: colors.textPrimary }}>Ciclo: </Text>
              {p.mesocycle}
            </Text>
          ) : null}
        </Card>
      </ScrollView>
    );
  }

  // --- Passo 2: escolher os dias -------------------------------------------
  if (selected) {
    return (
      <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg }}>
        <TouchableOpacity onPress={() => setSelected(null)} style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}>
          <Ionicons name="chevron-back" size={20} color={colors.primary} />
          <Text style={[type.body, { color: colors.primary, fontWeight: "600" }]}>Métodos</Text>
        </TouchableOpacity>

        <Text style={[type.h1, { color: colors.textPrimary }]}>{selected.name}</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>{selected.author}</Text>
        <Card style={{ marginTop: spacing.md }}>
          <Text style={[type.body, { color: colors.textPrimary }]}>{selected.goal}</Text>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>{selected.guide_excerpt}</Text>
        </Card>

        <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
          Quantos dias por semana você treina?
        </Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm }}>
          {selected.days_per_week.map((d) => (
            <TouchableOpacity
              key={d}
              onPress={() => {
                setDays(d);
                handleGenerate(selected, d);
              }}
              style={{
                backgroundColor: colors.surface,
                borderWidth: 1,
                borderColor: colors.border,
                borderRadius: 14,
                paddingVertical: spacing.md,
                paddingHorizontal: spacing.lg,
              }}
            >
              <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>{d} dias</Text>
            </TouchableOpacity>
          ))}
        </View>
        {loading ? <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.xl }} size="large" /> : null}
      </ScrollView>
    );
  }

  // --- Passo 1: catálogo de métodos ----------------------------------------
  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
    >
      <Text style={[type.h1, { color: colors.textPrimary }]}>Treino com IA</Text>
      <Text style={[type.body, { color: colors.textSecondary, marginTop: 4 }]}>
        Escolha uma metodologia consagrada. A IA monta seu treino fiel ao método — frequência, volume,
        proporção e ordem exatas — usando só a base oficial, sem inventar.
      </Text>

      {methods.map((m) => (
        <TouchableOpacity key={m.key} activeOpacity={0.8} onPress={() => setSelected(m)}>
          <Card style={{ marginTop: spacing.md }}>
            <View style={{ flexDirection: "row", alignItems: "center" }}>
              <View style={{ flex: 1 }}>
                <Text style={[type.h2, { color: colors.textPrimary, fontSize: 17 }]}>{m.name}</Text>
                <Text style={[type.caption, { color: colors.textSecondary }]}>
                  {m.author} · {EXP_LABEL[m.experience_min] ?? m.experience_min} · {m.days_per_week.join("/")} dias
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
            </View>
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.sm }]} numberOfLines={2}>
              {m.goal}
            </Text>
          </Card>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}
