import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import { Alert, ScrollView, Text, TextInput, View } from "react-native";

import { listSleepLogs, logSleep, type SleepLog, type WakeFeeling } from "../../api/sleep";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";

const WAKE_FEELING_LABELS: Record<WakeFeeling, string> = {
  descansado: "😊 Descansado",
  cansado: "😐 Cansado",
  muito_cansado: "😫 Muito cansado",
};

/** Converte "HH:MM" em Date de hoje (ou ontem, se for horário de dormir e
 * cair "depois" do acordar — dormiu antes da meia-noite). */
function parseTimes(sleepHHMM: string, wakeHHMM: string): { sleepAt: Date; wakeAt: Date } | null {
  const re = /^(\d{1,2}):(\d{2})$/;
  const s = sleepHHMM.match(re);
  const w = wakeHHMM.match(re);
  if (!s || !w) return null;
  const [sh, sm] = [Number(s[1]), Number(s[2])];
  const [wh, wm] = [Number(w[1]), Number(w[2])];
  if (sh > 23 || wh > 23 || sm > 59 || wm > 59) return null;

  const wakeAt = new Date();
  wakeAt.setHours(wh, wm, 0, 0);
  const sleepAt = new Date();
  sleepAt.setHours(sh, sm, 0, 0);
  if (sleepAt >= wakeAt) {
    sleepAt.setDate(sleepAt.getDate() - 1);
  }
  return { sleepAt, wakeAt };
}

export function SleepScreen() {
  const { colors, type, spacing, radius } = useTheme();

  const [logs, setLogs] = useState<SleepLog[]>([]);
  const [sleepTime, setSleepTime] = useState("23:00");
  const [wakeTime, setWakeTime] = useState("07:00");
  const [quality, setQuality] = useState(3);
  const [wakeFeeling, setWakeFeeling] = useState<WakeFeeling>("descansado");
  const [notes, setNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  function load() {
    listSleepLogs().then(setLogs);
  }

  useEffect(() => {
    load();
  }, []);

  const parsed = parseTimes(sleepTime, wakeTime);
  const durationMin = parsed ? Math.round((parsed.wakeAt.getTime() - parsed.sleepAt.getTime()) / 60000) : 0;

  async function handleSave() {
    if (!parsed) {
      Alert.alert("Horário inválido", "Use o formato HH:MM, ex: 23:30");
      return;
    }
    setIsSubmitting(true);
    try {
      await logSleep({
        sleep_at: parsed.sleepAt.toISOString(),
        wake_at: parsed.wakeAt.toISOString(),
        quality,
        wake_feeling: wakeFeeling,
        notes: notes.trim() || null,
      });
      setNotes("");
      load();
    } catch (err: any) {
      Alert.alert("Não foi possível registrar", err?.response?.data?.detail ?? "Tente novamente.");
    } finally {
      setIsSubmitting(false);
    }
  }

  const maxDuration = Math.max(...logs.map((l) => l.duration_minutes), 1);

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      <Card accent={colors.moduleSleep} style={{ marginBottom: spacing.lg }}>
        <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}>
          <Ionicons name="moon" size={20} color={colors.moduleSleep} />
          <Text style={[type.h2, { color: colors.textPrimary, marginLeft: 8 }]}>Como foi sua noite?</Text>
        </View>

        <View style={{ flexDirection: "row", gap: spacing.md, alignItems: "center" }}>
          <TimeInput label="Dormi às" value={sleepTime} onChangeText={setSleepTime} />
          <Ionicons name="arrow-forward" size={18} color={colors.textSecondary} style={{ marginTop: 18 }} />
          <TimeInput label="Acordei às" value={wakeTime} onChangeText={setWakeTime} />
          <View style={{ flex: 1, alignItems: "flex-end" }}>
            <Text style={[type.caption, { color: colors.textSecondary }]}>duração</Text>
            <Text style={[type.h2, { color: colors.moduleSleep }]}>
              {Math.floor(durationMin / 60)}h{String(durationMin % 60).padStart(2, "0")}
            </Text>
          </View>
        </View>

        <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.md, marginBottom: spacing.xs }]}>
          Qualidade do sono
        </Text>
        <View style={{ flexDirection: "row", gap: spacing.xs }}>
          {[1, 2, 3, 4, 5].map((n) => (
            <OptionButton key={n} compact label={"★".repeat(n)} selected={quality === n} onPress={() => setQuality(n)} />
          ))}
        </View>

        <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm, marginBottom: spacing.xs }]}>
          Como você acordou
        </Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs }}>
          {(Object.keys(WAKE_FEELING_LABELS) as WakeFeeling[]).map((f) => (
            <OptionButton
              key={f}
              compact
              label={WAKE_FEELING_LABELS[f]}
              selected={wakeFeeling === f}
              onPress={() => setWakeFeeling(f)}
            />
          ))}
        </View>

        <TextInput
          value={notes}
          onChangeText={setNotes}
          placeholder="Notas (opcional): acordou de madrugada, sonhos..."
          placeholderTextColor={colors.textSecondary}
          style={[
            type.bodySmall,
            {
              color: colors.textPrimary,
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.button,
              padding: spacing.sm,
              paddingHorizontal: spacing.md,
              marginTop: spacing.sm,
              marginBottom: spacing.md,
              minHeight: 44,
            },
          ]}
        />

        <Button title="Registrar sono" onPress={handleSave} loading={isSubmitting} />
      </Card>

      {logs.length > 0 ? (
        <>
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
            Últimas noites
          </Text>
          <Card>
            {logs.map((log, i) => (
              <View key={log.id} style={{ marginTop: i === 0 ? 0 : spacing.md }}>
                <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 4 }}>
                  <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600" }]}>
                    {new Date(log.sleep_at).toLocaleDateString("pt-BR", { weekday: "short", day: "numeric" })}
                  </Text>
                  <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
                    {Math.floor(log.duration_minutes / 60)}h{String(log.duration_minutes % 60).padStart(2, "0")}
                    {" · "}
                    {"★".repeat(log.quality)}
                  </Text>
                </View>
                <View style={{ height: 8, backgroundColor: colors.surfaceAlt, borderRadius: 4 }}>
                  <View
                    style={{
                      height: 8,
                      width: `${(log.duration_minutes / maxDuration) * 100}%`,
                      backgroundColor: colors.moduleSleep,
                      borderRadius: 4,
                    }}
                  />
                </View>
              </View>
            ))}
          </Card>
        </>
      ) : null}
    </ScrollView>
  );
}

function TimeInput({ label, value, onChangeText }: { label: string; value: string; onChangeText: (v: string) => void }) {
  const { colors, type, radius } = useTheme();
  return (
    <View>
      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: 4 }]}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={(v) => onChangeText(v.replace(/[^0-9:]/g, "").slice(0, 5))}
        keyboardType="numbers-and-punctuation"
        placeholder="HH:MM"
        placeholderTextColor={colors.textSecondary}
        style={[
          type.h2,
          {
            color: colors.textPrimary,
            backgroundColor: colors.surfaceAlt,
            borderRadius: radius.button,
            width: 88,
            height: 50,
            textAlign: "center",
          },
        ]}
      />
    </View>
  );
}
