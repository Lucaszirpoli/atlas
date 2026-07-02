import DateTimePicker from "@react-native-community/datetimepicker";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { Alert, ScrollView, Text, TextInput, View } from "react-native";

import { listSleepLogs, logSleep, type SleepLog, type WakeFeeling } from "../../api/sleep";
import { Button } from "../../components/Button";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";

const WAKE_FEELING_LABELS: Record<WakeFeeling, string> = {
  descansado: "Descansado",
  cansado: "Cansado",
  muito_cansado: "Muito cansado",
};

function defaultSleepTime(): Date {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  d.setHours(23, 0, 0, 0);
  return d;
}

function defaultWakeTime(): Date {
  const d = new Date();
  d.setHours(7, 0, 0, 0);
  return d;
}

export function SleepScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();

  const [logs, setLogs] = useState<SleepLog[]>([]);
  const [sleepAt, setSleepAt] = useState(defaultSleepTime());
  const [wakeAt, setWakeAt] = useState(defaultWakeTime());
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

  async function handleSave() {
    setIsSubmitting(true);
    try {
      await logSleep({
        sleep_at: sleepAt.toISOString(),
        wake_at: wakeAt.toISOString(),
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
    <ScrollView contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}>
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.md }]}>Sono</Text>

      <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.xs }]}>
        Dormiu às
      </Text>
      <DateTimePicker
        value={sleepAt}
        mode="datetime"
        onChange={(_, date) => date && setSleepAt(date)}
        style={{ alignSelf: "flex-start" }}
      />

      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm, marginBottom: spacing.xs }]}>
        Acordou às
      </Text>
      <DateTimePicker
        value={wakeAt}
        mode="datetime"
        onChange={(_, date) => date && setWakeAt(date)}
        style={{ alignSelf: "flex-start" }}
      />

      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.md, marginBottom: spacing.xs }]}>
        Qualidade do sono
      </Text>
      <View style={{ flexDirection: "row", gap: spacing.xs }}>
        {[1, 2, 3, 4, 5].map((n) => (
          <OptionButton key={n} label={String(n)} selected={quality === n} onPress={() => setQuality(n)} />
        ))}
      </View>

      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm, marginBottom: spacing.xs }]}>
        Como você acordou
      </Text>
      {(Object.keys(WAKE_FEELING_LABELS) as WakeFeeling[]).map((f) => (
        <OptionButton
          key={f}
          label={WAKE_FEELING_LABELS[f]}
          selected={wakeFeeling === f}
          onPress={() => setWakeFeeling(f)}
        />
      ))}

      <TextInput
        value={notes}
        onChangeText={setNotes}
        placeholder="Notas (opcional): acordou de madrugada, dificuldade pra dormir..."
        placeholderTextColor={colors.textSecondary}
        style={[
          type.bodySmall,
          {
            color: colors.textPrimary,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.button,
            padding: spacing.sm,
            marginTop: spacing.sm,
            marginBottom: spacing.md,
          },
        ]}
      />

      <Button title="Registrar sono" onPress={handleSave} loading={isSubmitting} />

      <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
        Últimos registros
      </Text>
      {logs.map((log) => (
        <View key={log.id} style={{ marginBottom: spacing.sm }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
            <Text style={[type.bodySmall, { color: colors.textPrimary }]}>
              {new Date(log.sleep_at).toLocaleDateString("pt-BR")}
            </Text>
            <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
              {Math.floor(log.duration_minutes / 60)}h{log.duration_minutes % 60}min · nota {log.quality}
            </Text>
          </View>
          <View style={{ height: 6, backgroundColor: colors.border, borderRadius: 3, marginTop: spacing.xs }}>
            <View
              style={{
                height: 6,
                width: `${(log.duration_minutes / maxDuration) * 100}%`,
                backgroundColor: colors.moduleSleep,
                borderRadius: 3,
              }}
            />
          </View>
        </View>
      ))}
    </ScrollView>
  );
}
