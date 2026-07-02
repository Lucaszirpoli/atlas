import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";
import { Button } from "./Button";

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

  const minutes = Math.floor(remaining / 60);
  const secs = remaining % 60;

  return (
    <View style={[styles.overlay, { backgroundColor: colors.bg + "F5" }]}>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
        Descanso
      </Text>
      <Text style={[styles.big, { color: colors.secondary }]}>
        {minutes}:{String(secs).padStart(2, "0")}
      </Text>
      <View style={{ marginTop: spacing.xl, width: 200 }}>
        <Button title="Pular descanso" variant="ghost" onPress={onSkip} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
    zIndex: 10,
  },
  big: {
    fontSize: 72,
    fontWeight: "700",
  },
});
