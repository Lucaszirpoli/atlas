import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { listWeightLogs, logWeight, type WeightLog } from "../../api/weight";
import { Card } from "../../components/Card";
import { LineChart, type ChartPoint } from "../../components/LineChart";
import { useTheme } from "../../theme/ThemeProvider";
import { WeightCoachHeader } from "../coaching/CoachModuleHeader";

const PERIOD_DAYS = 90;

/** Tela de Peso: registro rápido + gráfico de evolução + histórico. Para o Pro,
 * o topo traz a leitura do coach; o Free vê só o registro manual e os gráficos. */
export function WeightScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const insets = useSafeAreaInsets();

  const [logs, setLogs] = useState<WeightLog[]>([]);
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    listWeightLogs()
      .then(setLogs)
      .catch(() => {});
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const sorted = [...logs].sort((a, b) => a.recorded_at.localeCompare(b.recorded_at));
  const current = sorted.length ? sorted[sorted.length - 1] : null;

  // Tendência vs o registro mais próximo de 7 dias atrás (fallback: o primeiro).
  const trend = (() => {
    if (!current || sorted.length < 2) return null;
    const curT = new Date(current.recorded_at).getTime();
    const weekAgo = curT - 7 * 86400000;
    const past = [...sorted.slice(0, -1)].reverse().find((l) => new Date(l.recorded_at).getTime() <= weekAgo) ?? sorted[0];
    const delta = current.weight_kg - past.weight_kg;
    if (Math.abs(delta) < 0.05) return { delta: 0 };
    return { delta };
  })();

  const base = input !== "" ? Number(input.replace(",", ".")) : current?.weight_kg ?? 0;
  const valid = Number.isFinite(base) && base > 0;

  function bump(delta: number) {
    const next = Math.max(0, Math.round((base + delta) * 10) / 10);
    setInput(String(next).replace(".", ","));
  }

  async function salvar() {
    if (!valid) return;
    setSaving(true);
    try {
      await logWeight(Math.round(base * 10) / 10);
      setInput("");
      load();
    } catch {
      /* silencioso */
    } finally {
      setSaving(false);
    }
  }

  const cutoff = Date.now() - PERIOD_DAYS * 86400000;
  const points: ChartPoint[] = sorted
    .map((l) => ({ x: new Date(l.recorded_at).getTime(), y: l.weight_kg }))
    .filter((p) => p.x >= cutoff);

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl + insets.bottom }}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
    >
      {/* Leitura do coach (Pro). Some no Free. */}
      <WeightCoachHeader />

      {/* Registro rápido */}
      <Card accent={colors.moduleSleep} style={{ marginBottom: spacing.lg }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: spacing.md }}>
          <Ionicons name="scale-outline" size={20} color={colors.moduleSleep} />
          <Text style={[type.h2, { color: colors.textPrimary, fontSize: 16, flex: 1 }]}>Seu peso</Text>
          {current ? (
            <Text style={[type.caption, { color: colors.textSecondary }]}>
              atual {current.weight_kg.toString().replace(".", ",")} kg
            </Text>
          ) : null}
        </View>

        {current ? (
          <View style={{ flexDirection: "row", alignItems: "baseline", gap: 6, marginBottom: spacing.md }}>
            <Text style={[type.display, { color: colors.textPrimary, fontSize: 34 }]}>
              {current.weight_kg.toString().replace(".", ",")}
            </Text>
            <Text style={[type.body, { color: colors.textSecondary }]}>kg</Text>
            {trend ? (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 3, marginLeft: 4 }}>
                <Ionicons
                  name={trend.delta === 0 ? "remove" : trend.delta < 0 ? "arrow-down" : "arrow-up"}
                  size={14}
                  color={trend.delta === 0 ? colors.textSecondary : colors.success}
                />
                <Text style={[type.caption, { color: colors.textSecondary }]}>
                  {trend.delta === 0
                    ? "estável"
                    : `${Math.abs(trend.delta).toFixed(1).replace(".", ",")} kg / sem`}
                </Text>
              </View>
            ) : null}
          </View>
        ) : (
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>
            Registre seu peso pra começar a acompanhar 👇
          </Text>
        )}

        {/* Stepper − valor +  e Registrar */}
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8, marginBottom: spacing.sm }}>
          <StepBtn icon="remove" onPress={() => bump(-0.1)} />
          <View
            style={{
              flex: 1,
              flexDirection: "row",
              alignItems: "center",
              justifyContent: "center",
              gap: 2,
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.button,
              height: 48,
            }}
          >
            <TextInput
              value={input !== "" ? input : current ? String(current.weight_kg).replace(".", ",") : ""}
              onChangeText={(v) => setInput(v.replace(/[^0-9.,]/g, ""))}
              keyboardType="decimal-pad"
              placeholder="0,0"
              placeholderTextColor={colors.textSecondary}
              style={[type.h2, { color: colors.textPrimary, fontSize: 20, minWidth: 44, textAlign: "center", paddingVertical: 0 }]}
            />
            <Text style={[type.caption, { color: colors.textSecondary }]}>kg</Text>
          </View>
          <StepBtn icon="add" onPress={() => bump(0.1)} />
        </View>
        <TouchableOpacity
          onPress={salvar}
          disabled={!valid || saving}
          activeOpacity={0.85}
          style={{
            height: 48,
            borderRadius: radius.button,
            backgroundColor: colors.primary,
            alignItems: "center",
            justifyContent: "center",
            opacity: !valid || saving ? 0.5 : 1,
          }}
        >
          <Text style={[type.body, { color: colors.textOnPrimary, fontWeight: "700" }]}>
            {saving ? "..." : "Registrar peso"}
          </Text>
        </TouchableOpacity>
      </Card>

      {/* Gráfico de evolução */}
      {points.length >= 2 ? (
        <>
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
            Evolução ({PERIOD_DAYS} dias)
          </Text>
          <Card style={{ marginBottom: spacing.lg }}>
            <LineChart
              series={[{ data: points, color: colors.primary, area: true, showDots: true }]}
              height={180}
              formatY={(v) => `${v.toFixed(1).replace(".", ",")}`}
            />
          </Card>
        </>
      ) : null}

      {/* Histórico */}
      {sorted.length > 0 ? (
        <>
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
            Registros
          </Text>
          <Card>
            {[...sorted].reverse().slice(0, 30).map((log, i) => (
              <View
                key={log.id}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "space-between",
                  paddingVertical: spacing.sm,
                  borderTopWidth: i === 0 ? 0 : 1,
                  borderTopColor: colors.border,
                }}
              >
                <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
                  {new Date(log.recorded_at).toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "short" })}
                </Text>
                <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]}>
                  {log.weight_kg.toString().replace(".", ",")} kg
                </Text>
              </View>
            ))}
          </Card>
        </>
      ) : null}
    </ScrollView>
  );
}

function StepBtn({ icon, onPress }: { icon: keyof typeof Ionicons.glyphMap; onPress: () => void }) {
  const { colors } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.7}
      style={{
        width: 44,
        height: 48,
        borderRadius: 12,
        backgroundColor: colors.surfaceAlt,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Ionicons name={icon} size={20} color={colors.textPrimary} />
    </TouchableOpacity>
  );
}
