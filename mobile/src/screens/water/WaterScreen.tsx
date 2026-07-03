import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";

import { deleteWaterLog, getTodayWaterSummary, logWater, type WaterSummary } from "../../api/water";
import { Card } from "../../components/Card";
import { HelpDot } from "../../components/HelpDot";
import { ProgressRing } from "../../components/ProgressRing";
import { useTheme } from "../../theme/ThemeProvider";

const AMOUNTS = [200, 300, 500, 750];

export function WaterScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const [water, setWater] = useState<WaterSummary | null>(null);

  async function load() {
    setWater(await getTodayWaterSummary());
  }
  useFocusEffect(
    useCallback(() => {
      load();
    }, [])
  );

  async function add(ml: number) {
    await logWater(ml);
    load();
  }
  async function remove(id: number) {
    await deleteWaterLog(id);
    load();
  }

  const pct = water && water.goal_ml > 0 ? water.total_ml_today / water.goal_ml : 0;

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      <Card accent={colors.info} style={{ marginBottom: spacing.md, alignItems: "center" }}>
        <View style={{ flexDirection: "row", alignItems: "center", alignSelf: "flex-start", marginBottom: spacing.sm }}>
          <Ionicons name="water" size={18} color={colors.info} />
          <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8 }]}>Hoje</Text>
          <HelpDot
            title="Meta de água"
            text="Sua meta é 35ml por kg do seu peso atual. Ao atualizar o peso, ela se ajusta sozinha."
          />
        </View>
        <ProgressRing
          size={150}
          strokeWidth={15}
          progress={pct}
          color={colors.info}
          value={`${((water?.total_ml_today ?? 0) / 1000).toFixed(1)}L`}
          label={`de ${((water?.goal_ml ?? 0) / 1000).toFixed(1)}L`}
        />
      </Card>

      {/* Botões de adicionar */}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.lg }}>
        {AMOUNTS.map((ml) => (
          <TouchableOpacity
            key={ml}
            onPress={() => add(ml)}
            activeOpacity={0.8}
            style={{
              flexGrow: 1,
              flexBasis: "22%",
              alignItems: "center",
              paddingVertical: spacing.md,
              borderRadius: radius.card,
              backgroundColor: colors.info + "18",
            }}
          >
            <Ionicons name="add-circle" size={22} color={colors.info} />
            <Text style={[type.bodySmall, { color: colors.info, fontWeight: "800", marginTop: 2 }]}>{ml}ml</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Registros de hoje com excluir */}
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
        Registros de hoje
      </Text>
      {(water?.logs_today ?? []).length === 0 ? (
        <Card>
          <Text style={[type.bodySmall, { color: colors.textSecondary, textAlign: "center", paddingVertical: spacing.sm }]}>
            Nenhum copo registrado ainda hoje.
          </Text>
        </Card>
      ) : (
        <Card padded={false}>
          {(water?.logs_today ?? []).map((log, i) => (
            <View
              key={log.id}
              style={{
                flexDirection: "row",
                alignItems: "center",
                padding: spacing.md,
                borderTopWidth: i === 0 ? 0 : 1,
                borderTopColor: colors.border,
              }}
            >
              <Ionicons name="water-outline" size={18} color={colors.info} style={{ marginRight: spacing.sm }} />
              <Text style={[type.body, { color: colors.textPrimary, flex: 1 }]}>{log.amount_ml} ml</Text>
              <Text style={[type.caption, { color: colors.textSecondary, marginRight: spacing.md }]}>
                {new Date(log.logged_at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
              </Text>
              <TouchableOpacity onPress={() => remove(log.id)} hitSlop={8}>
                <Ionicons name="trash-outline" size={19} color={colors.danger} />
              </TouchableOpacity>
            </View>
          ))}
        </Card>
      )}
    </ScrollView>
  );
}
