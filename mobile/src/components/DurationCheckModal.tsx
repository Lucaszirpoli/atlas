import React, { useEffect, useRef, useState } from "react";
import { Modal, ScrollView, Text, TouchableOpacity, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";
import { Button } from "./Button";

// Opções de tempo (min) pra corrigir. Cobre de 10min a 3h em passos de 5.
const OPTIONS: number[] = Array.from({ length: (180 - 10) / 5 + 1 }, (_, i) => 10 + i * 5);

/** Aparece quando o treino durou bem mais que a média da pessoa (ex: ficou
 * minimizado). Pergunta de forma simples se o tempo está certo e deixa ela
 * ajustar num scroll — sem julgamento, é só pra o histórico não distorcer. */
export function DurationCheckModal({
  visible,
  measuredMinutes,
  onConfirm,
  onKeepMeasured,
  saving,
}: {
  visible: boolean;
  measuredMinutes: number;
  onConfirm: (minutes: number) => void;
  onKeepMeasured: () => void;
  saving?: boolean;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const scrollRef = useRef<ScrollView>(null);
  const [selected, setSelected] = useState(measuredMinutes);

  // Ao abrir, começa no valor mais próximo do medido.
  useEffect(() => {
    if (!visible) return;
    const nearest = OPTIONS.reduce((a, b) => (Math.abs(b - measuredMinutes) < Math.abs(a - measuredMinutes) ? b : a), OPTIONS[0]);
    setSelected(nearest);
  }, [visible, measuredMinutes]);

  function fmt(min: number): string {
    const h = Math.floor(min / 60);
    const m = min % 60;
    return h > 0 ? `${h}h${m > 0 ? String(m).padStart(2, "0") : ""}` : `${m}min`;
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onKeepMeasured}>
      <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.55)", justifyContent: "flex-end" }}>
        <View
          style={{
            backgroundColor: colors.surface,
            borderTopLeftRadius: 24,
            borderTopRightRadius: 24,
            padding: spacing.lg,
            paddingBottom: spacing.xl,
          }}
        >
          <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
            Esse treino durou {fmt(measuredMinutes)}?
          </Text>
          <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.lg }]}>
            É bem mais que a média dos seus treinos. Se ficou minimizado, ajuste o tempo real abaixo — senão, é só
            confirmar.
          </Text>

          {/* Scroll de tempo */}
          <ScrollView
            ref={scrollRef}
            horizontal
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={{ gap: spacing.sm, paddingVertical: spacing.xs }}
            style={{ marginBottom: spacing.lg }}
          >
            {OPTIONS.map((min) => {
              const on = selected === min;
              return (
                <TouchableOpacity
                  key={min}
                  onPress={() => setSelected(min)}
                  style={{
                    minWidth: 64,
                    alignItems: "center",
                    backgroundColor: on ? colors.primary : colors.surfaceAlt,
                    borderRadius: radius.card,
                    paddingVertical: spacing.md,
                    paddingHorizontal: spacing.sm,
                    borderWidth: 1,
                    borderColor: on ? colors.primary : colors.border,
                  }}
                >
                  <Text
                    style={[
                      type.body,
                      { color: on ? colors.textOnPrimary : colors.textPrimary, fontWeight: "700" },
                    ]}
                  >
                    {fmt(min)}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          <Button title={`Salvar com ${fmt(selected)}`} onPress={() => onConfirm(selected)} loading={saving} />
          <TouchableOpacity onPress={onKeepMeasured} disabled={saving} style={{ alignItems: "center", marginTop: spacing.md }}>
            <Text style={[type.bodySmall, { color: colors.textSecondary, fontWeight: "700" }]}>
              O tempo estava certo ({fmt(measuredMinutes)})
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}
