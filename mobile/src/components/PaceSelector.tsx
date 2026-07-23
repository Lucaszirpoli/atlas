import { Ionicons } from "@expo/vector-icons";
import React, { useState } from "react";
import { ActivityIndicator, Modal, Text, TextInput, TouchableOpacity, View } from "react-native";

import { setGoalPace, setTargetWeight, type GoalPaceBlock } from "../api/coaching";
import { useTheme } from "../theme/ThemeProvider";
import { Button } from "./Button";
import { InfoDialog } from "./InfoDialog";

// Ritmo do objetivo: rótulo + risco/benefício (o "?" de cada opção).
const PACE_META: Record<string, { label: string; info: string }> = {
  slow: {
    label: "Devagar",
    info: "Mais devagar: preserva mais músculo e é mais fácil de manter no dia a dia. O custo é levar mais tempo pra chegar no alvo.",
  },
  normal: {
    label: "Normal",
    info: "Recomendado: o equilíbrio. Resultado consistente com baixo risco de perder músculo (no corte) ou acumular gordura (no ganho).",
  },
  fast: {
    label: "Rápido",
    info: "Mais rápido: chega antes no alvo, mas sobe o risco — perder músculo no corte ou ganhar mais gordura no bulk — e é mais difícil de sustentar.",
  },
};

/**
 * Seletor de RITMO do objetivo (devagar/normal/rápido) + peso-alvo. Cada opção
 * mostra o tempo estimado até o peso-alvo (ou a velocidade) e um "?" com o
 * risco/benefício. Trocar recalcula a meta (com transição gradual se for grande).
 * Vive na tela de objetivo/cálculo automático — o ritmo escala o déficit/superávit.
 */
export function PaceSelector({
  pace,
  onChanged,
}: {
  pace: GoalPaceBlock;
  onChanged: (title: string, message: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [saving, setSaving] = useState<string | null>(null);
  const [info, setInfo] = useState<{ title: string; message: string } | null>(null);
  const [targetOpen, setTargetOpen] = useState(false);
  const [targetInput, setTargetInput] = useState(pace.target_weight_kg ? String(pace.target_weight_kg) : "");

  async function escolher(p: "slow" | "normal" | "fast") {
    if (p === pace.current || saving) return;
    setSaving(p);
    try {
      const r = await setGoalPace(p);
      onChanged("Ritmo atualizado", r.message);
    } catch {
      setSaving(null);
    }
  }

  async function salvarAlvo() {
    const kg = parseFloat(targetInput.replace(",", "."));
    setTargetOpen(false);
    try {
      const r = await setTargetWeight(Number.isFinite(kg) ? kg : null);
      onChanged("Peso-alvo", r.message);
    } catch {
      // recarrega no próximo foco
    }
  }
  async function limparAlvo() {
    setTargetOpen(false);
    setTargetInput("");
    try {
      const r = await setTargetWeight(null);
      onChanged("Peso-alvo", r.message);
    } catch {}
  }

  function tempoTexto(o: (typeof pace.options)[number]): string {
    if (o.weeks != null) {
      if (o.weeks >= 8) return `~${Math.round(o.weeks / 4)} meses`;
      return `~${o.weeks} sem`;
    }
    const r = o.rate_kg_per_week;
    return `${r > 0 ? "+" : ""}${r.toFixed(2)} kg/sem`;
  }

  return (
    <View style={{ marginTop: spacing.md }}>
      <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 0.5, textTransform: "uppercase", marginBottom: spacing.xs }]}>
        Ritmo
      </Text>
      {pace.options.map((o) => {
        const on = o.pace === pace.current;
        const m = PACE_META[o.pace];
        return (
          <View
            key={o.pace}
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 10,
              borderWidth: 1,
              borderColor: on ? colors.primary : colors.border,
              backgroundColor: on ? colors.primary + "12" : "transparent",
              borderRadius: radius.card,
              paddingVertical: 9,
              paddingHorizontal: spacing.sm,
              marginBottom: spacing.xs,
            }}
          >
            <TouchableOpacity
              onPress={() => escolher(o.pace)}
              activeOpacity={0.7}
              style={{ flexDirection: "row", alignItems: "center", gap: 10, flex: 1 }}
            >
              <Ionicons
                name={on ? "radio-button-on" : "radio-button-off"}
                size={18}
                color={on ? colors.primary : colors.textSecondary}
              />
              <View style={{ flex: 1 }}>
                <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: on ? "700" : "600" }]}>
                  {m.label}
                  {o.pace === "normal" ? "  ·  recomendado" : ""}
                </Text>
                <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
                  {tempoTexto(o)} · {o.kcal} kcal
                </Text>
              </View>
              {saving === o.pace ? <ActivityIndicator size="small" color={colors.primary} /> : null}
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setInfo({ title: m.label, message: m.info })} hitSlop={8}>
              <Ionicons name="help-circle-outline" size={19} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
        );
      })}

      {/* Peso-alvo — a referência que dá o tempo estimado. */}
      <TouchableOpacity
        onPress={() => {
          setTargetInput(pace.target_weight_kg ? String(pace.target_weight_kg) : "");
          setTargetOpen(true);
        }}
        style={{ flexDirection: "row", alignItems: "center", gap: 6, marginTop: 2 }}
      >
        <Ionicons name="flag-outline" size={14} color={colors.primary} />
        <Text style={[type.caption, { color: colors.primary, fontWeight: "600" }]}>
          {pace.target_weight_kg ? `Peso-alvo: ${pace.target_weight_kg} kg (tocar pra mudar)` : "Definir peso-alvo pra estimar o tempo"}
        </Text>
      </TouchableOpacity>

      <InfoDialog
        visible={info != null}
        onClose={() => setInfo(null)}
        title={info?.title ?? ""}
        message={info?.message}
      />

      {/* Modal simples pra digitar o peso-alvo. */}
      <Modal visible={targetOpen} transparent animationType="fade" onRequestClose={() => setTargetOpen(false)}>
        <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "center", padding: spacing.lg }}>
          <View style={{ backgroundColor: colors.surface, borderRadius: radius.card, padding: spacing.lg }}>
            <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.sm }]}>Peso-alvo</Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>
              Onde você quer chegar. É a partir daqui que eu estimo o tempo de cada ritmo.
            </Text>
            <TextInput
              value={targetInput}
              onChangeText={setTargetInput}
              keyboardType="numeric"
              placeholder="ex: 75"
              placeholderTextColor={colors.textSecondary}
              style={{
                borderWidth: 1, borderColor: colors.border, borderRadius: radius.card,
                paddingVertical: 10, paddingHorizontal: spacing.md, color: colors.textPrimary,
                fontSize: 16, marginBottom: spacing.md,
              }}
            />
            <View style={{ flexDirection: "row", gap: spacing.sm }}>
              <View style={{ flex: 1 }}>
                <Button title="Salvar" onPress={salvarAlvo} />
              </View>
              {pace.target_weight_kg ? (
                <TouchableOpacity onPress={limparAlvo} style={{ justifyContent: "center", paddingHorizontal: spacing.md }}>
                  <Text style={[type.bodySmall, { color: colors.textSecondary }]}>Limpar</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity onPress={() => setTargetOpen(false)} style={{ justifyContent: "center", paddingHorizontal: spacing.md }}>
                  <Text style={[type.bodySmall, { color: colors.textSecondary }]}>Cancelar</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}
