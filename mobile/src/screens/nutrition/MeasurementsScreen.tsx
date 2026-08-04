// FOTOS DE PROGRESSO saíram desta tela a pedido do usuário: aqui ficam só as
// MEDIDAS. O acervo de quem já tinha fotos continua no servidor (histórico é
// append-only) — o que sumiu é a porta de entrada para novas.
import React, { useEffect, useState } from "react";
import { Alert, ScrollView, Text, TextInput, View } from "react-native";

import {
  createMeasurement,
  listMeasurements,
  type BodyMeasurement,
  type MeasurementType,
} from "../../api/measurements";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";

const MEASUREMENT_LABELS: Record<MeasurementType, string> = {
  waist: "Cintura",
  hip: "Quadril",
  chest: "Peito",
  arm_left: "Braço esq.",
  arm_right: "Braço dir.",
  thigh_left: "Coxa esq.",
  thigh_right: "Coxa dir.",
  neck: "Pescoço",
};

export function MeasurementsScreen() {
  const { colors, type, spacing, radius } = useTheme();

  const [measurements, setMeasurements] = useState<BodyMeasurement[]>([]);
  const [selectedType, setSelectedType] = useState<MeasurementType>("waist");
  const [valueCm, setValueCm] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function load() {
    setMeasurements(await listMeasurements());
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAddMeasurement() {
    const value = Number(valueCm);
    if (!value) {
      Alert.alert("Valor inválido", "Informe a medida em centímetros.");
      return;
    }
    setIsSubmitting(true);
    try {
      await createMeasurement(selectedType, value);
      setValueCm("");
      await load();
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
      keyboardShouldPersistTaps="handled"
      keyboardDismissMode="on-drag"
    >
      {/* Nova medida */}
      <Card style={{ marginBottom: spacing.lg }}>
        <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.md }]}>Nova medida</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs }}>
          {(Object.keys(MEASUREMENT_LABELS) as MeasurementType[]).map((key) => (
            <OptionButton
              key={key}
              compact
              label={MEASUREMENT_LABELS[key]}
              selected={selectedType === key}
              onPress={() => setSelectedType(key)}
            />
          ))}
        </View>
        <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm, alignItems: "center" }}>
          <TextInput
            value={valueCm}
            onChangeText={(v) => setValueCm(v.replace(/,/g, ".").replace(/[^0-9.]/g, ""))}
            placeholder="0.0"
            placeholderTextColor={colors.textSecondary}
            keyboardType="decimal-pad"
            style={[
              type.h1,
              {
                flex: 1,
                color: colors.textPrimary,
                borderRadius: radius.button,
                paddingHorizontal: spacing.md,
                height: 56,
                backgroundColor: colors.surfaceAlt,
                textAlign: "center",
              },
            ]}
          />
          <Text style={[type.h2, { color: colors.textSecondary }]}>cm</Text>
          <Button title="Registrar" onPress={handleAddMeasurement} loading={isSubmitting} />
        </View>
      </Card>

      {/* Histórico */}
      {measurements.length === 0 ? (
        <Card>
          <View style={{ alignItems: "center", paddingVertical: spacing.md }}>
            <Text style={[type.bodySmall, { color: colors.textSecondary, textAlign: "center" }]}>
              A fita métrica enxerga o que a balança não vê:{"\n"}a cintura pode cair sem o peso mudar.
            </Text>
          </View>
        </Card>
      ) : (
        <>
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
            Histórico
          </Text>
          <Card padded={false} style={{ marginBottom: spacing.lg }}>
            {measurements.map((m, i) => (
              <View
                key={m.id}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: spacing.md,
                  borderTopWidth: i === 0 ? 0 : 1,
                  borderTopColor: colors.border,
                }}
              >
                <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600" }]}>
                  {MEASUREMENT_LABELS[m.type]}
                </Text>
                <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
                  <Text style={{ color: colors.primary, fontWeight: "700" }}>{m.value_cm} cm</Text>
                  {"  ·  "}
                  {new Date(m.recorded_at).toLocaleDateString("pt-BR")}
                </Text>
              </View>
            ))}
          </Card>
        </>
      )}
    </ScrollView>
  );
}
