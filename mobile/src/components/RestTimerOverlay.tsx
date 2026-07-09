import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import { Text, TouchableOpacity, View } from "react-native";
import Svg, { Circle } from "react-native-svg";

import { useTheme } from "../theme/ThemeProvider";
import { HelpDot } from "./HelpDot";

const RING_SIZE = 220;
const STROKE_WIDTH = 14;

/** Cronômetro de descanso em tela cheia — anel circular com o tempo restante
 * dentro, +30s/-30s pra ajustar rápido e Pular. `total` é a duração alvo
 * configurada no exercício (ex: 90/120s); ajustar com +/-30s move só o
 * `remaining`, o anel usa remaining/total como fração (trava em 100% se
 * ultrapassar). */
export function RestTimerOverlay({
  seconds,
  onFinish,
  onSkip,
}: {
  seconds: number;
  onFinish: () => void;
  onSkip: () => void;
}) {
  const { colors, type, spacing } = useTheme();
  const [total] = useState(Math.max(seconds, 1));
  const [remaining, setRemaining] = useState(seconds);

  useEffect(() => {
    setRemaining(seconds);
  }, [seconds]);

  useEffect(() => {
    if (remaining <= 0) {
      onFinish();
      return;
    }
    const timeout = setTimeout(() => setRemaining((r) => r - 1), 1000);
    return () => clearTimeout(timeout);
  }, [remaining]);

  function adjust(delta: number) {
    setRemaining((r) => Math.max(0, r + delta));
  }

  const fmt = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  const radius = (RING_SIZE - STROKE_WIDTH) / 2;
  const circumference = 2 * Math.PI * radius;
  const fraction = Math.min(remaining / total, 1);
  const strokeDashoffset = circumference * (1 - fraction);

  return (
    <View
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: colors.bg,
        alignItems: "center",
        justifyContent: "center",
        padding: spacing.lg,
        zIndex: 10,
      }}
    >
      {/* Cabeçalho: fechar (pula o descanso) + título + ajuda */}
      <View
        style={{
          position: "absolute",
          top: spacing.xl,
          left: spacing.lg,
          right: spacing.lg,
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <TouchableOpacity
          onPress={onSkip}
          hitSlop={10}
          style={{
            width: 36,
            height: 36,
            borderRadius: 18,
            backgroundColor: colors.surfaceAlt,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Ionicons name="close" size={20} color={colors.textPrimary} />
        </TouchableOpacity>
        <Text style={[type.h2, { color: colors.textPrimary, fontSize: 17 }]}>Descanso</Text>
        <HelpDot
          title="Cronômetro de descanso"
          text={
            "Conta o tempo de descanso configurado pro exercício entre as séries. Use −30s/+30s pra ajustar " +
            "rápido, ou toque em Pular pra ir direto pra próxima série."
          }
        />
      </View>

      {/* Anel com o tempo dentro */}
      <View style={{ width: RING_SIZE, height: RING_SIZE, alignItems: "center", justifyContent: "center" }}>
        <Svg width={RING_SIZE} height={RING_SIZE} style={{ position: "absolute", transform: [{ rotate: "-90deg" }] }}>
          <Circle
            cx={RING_SIZE / 2}
            cy={RING_SIZE / 2}
            r={radius}
            stroke={colors.border}
            strokeWidth={STROKE_WIDTH}
            fill="none"
          />
          <Circle
            cx={RING_SIZE / 2}
            cy={RING_SIZE / 2}
            r={radius}
            stroke={colors.primary}
            strokeWidth={STROKE_WIDTH}
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
          />
        </Svg>
        <Text style={{ fontSize: 52, fontWeight: "800", color: colors.textPrimary }}>{fmt(remaining)}</Text>
        <Text style={[type.body, { color: colors.textSecondary, marginTop: 2 }]}>{fmt(total)}</Text>
      </View>

      {/* Ajuste rápido + pular */}
      <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.xl }}>
        <TouchableOpacity
          onPress={() => adjust(-30)}
          style={{
            paddingVertical: spacing.md,
            paddingHorizontal: spacing.lg,
            borderRadius: 14,
            backgroundColor: colors.surfaceAlt,
          }}
        >
          <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>−30s</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => adjust(30)}
          style={{
            paddingVertical: spacing.md,
            paddingHorizontal: spacing.lg,
            borderRadius: 14,
            backgroundColor: colors.surfaceAlt,
          }}
        >
          <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>+30s</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={onSkip}
          style={{
            paddingVertical: spacing.md,
            paddingHorizontal: spacing.lg,
            borderRadius: 14,
            backgroundColor: colors.primary,
          }}
        >
          <Text style={[type.body, { color: colors.textOnPrimary, fontWeight: "700" }]}>Pular</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
