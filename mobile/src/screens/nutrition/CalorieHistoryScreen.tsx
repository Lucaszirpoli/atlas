import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import { getNutritionHistory, type NutritionHistory } from "../../api/evolution";
import { Card } from "../../components/Card";
import { useTheme } from "../../theme/ThemeProvider";

const PERIODOS: { dias: number; label: string }[] = [
  { dias: 7, label: "7 dias" },
  { dias: 30, label: "30 dias" },
  { dias: 60, label: "60 dias" },
];

/** Histórico de calorias: quanto a pessoa comeu por dia, com médias e adesão à
 * meta. Usa o endpoint /evolution/nutrition (já existente) que dá o total por
 * dia + a meta. Complementa o diário (que só mostra HOJE) com a visão do
 * período — "quanto comi na média da semana / nos últimos X dias". */
export function CalorieHistoryScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const [dias, setDias] = useState(30);
  const [data, setData] = useState<NutritionHistory | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let vivo = true;
    setLoading(true);
    getNutritionHistory(dias)
      .then((d) => vivo && setData(d))
      .finally(() => vivo && setLoading(false));
    return () => {
      vivo = false;
    };
  }, [dias]);

  const stats = useMemo(() => {
    const dd = data?.days ?? [];
    const registrados = dd.filter((d) => d.kcal > 0);
    const total = registrados.reduce((s, d) => s + d.kcal, 0);
    const media = registrados.length ? Math.round(total / registrados.length) : 0;
    // Média da última semana (7 dias mais recentes com registro).
    const ult7 = registrados.slice(-7);
    const mediaSemana = ult7.length ? Math.round(ult7.reduce((s, d) => s + d.kcal, 0) / ult7.length) : 0;
    const maxKcal = Math.max(1, ...dd.map((d) => d.kcal), data?.goal_kcal ?? 0);
    return { registrados: registrados.length, total: Math.round(total), media, mediaSemana, maxKcal };
  }, [data]);

  const meta = data?.goal_kcal ?? null;

  return (
    <ScrollView style={{ flex: 1, backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg }}>
      {/* Seletor de período */}
      <View style={{ flexDirection: "row", gap: spacing.xs, marginBottom: spacing.lg }}>
        {PERIODOS.map((p) => {
          const on = dias === p.dias;
          return (
            <Pressable
              key={p.dias}
              onPress={() => setDias(p.dias)}
              style={{
                flex: 1,
                alignItems: "center",
                backgroundColor: on ? colors.primary : colors.surface,
                borderWidth: 1,
                borderColor: on ? colors.primary : colors.border,
                borderRadius: radius.pill,
                paddingVertical: 10,
              }}
            >
              <Text style={[type.bodySmall, { color: on ? colors.textOnPrimary : colors.textPrimary, fontWeight: "700" }]}>
                {p.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {loading ? (
        <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.xl }} />
      ) : (
        <>
          {/* Médias */}
          <Card style={{ marginBottom: spacing.md }}>
            <View style={{ flexDirection: "row" }}>
              <Metrica label="Média por dia" valor={`${stats.media}`} sufixo="kcal" cor={colors.primary} destaque />
              <Metrica label="Média da semana" valor={`${stats.mediaSemana}`} sufixo="kcal" cor={colors.moduleTraining} />
            </View>
            {meta ? (
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
                Sua meta é {Math.round(meta)} kcal/dia.{" "}
                {stats.media > 0
                  ? stats.media <= meta
                    ? "Na média, você está dentro. 👏"
                    : `Na média, ${stats.media - Math.round(meta)} kcal acima.`
                  : ""}
              </Text>
            ) : null}
          </Card>

          {/* Registrados + total */}
          <Card style={{ marginBottom: spacing.md }}>
            <View style={{ flexDirection: "row" }}>
              <Metrica label="Dias registrados" valor={`${stats.registrados}`} sufixo={`de ${dias}`} cor={colors.info} />
              <Metrica label={`Total em ${dias} dias`} valor={`${(stats.total / 1000).toFixed(1)}`} sufixo="mil kcal" cor={colors.textPrimary} />
              {meta ? (
                <Metrica label="Dias na meta" valor={`${data?.days_within_goal ?? 0}`} sufixo={`de ${stats.registrados}`} cor={colors.success} />
              ) : null}
            </View>
          </Card>

          {/* Gráfico de barras: kcal por dia */}
          <Card>
            <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", marginBottom: spacing.sm }]}>
              Calorias por dia
            </Text>
            <Barras dias={data?.days ?? []} maxKcal={stats.maxKcal} meta={meta} />
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
              Cada barra é um dia. A linha tracejada é a sua meta. Dias sem registro ficam vazios.
            </Text>
          </Card>
        </>
      )}
    </ScrollView>
  );
}

function Metrica({
  label,
  valor,
  sufixo,
  cor,
  destaque,
}: {
  label: string;
  valor: string;
  sufixo?: string;
  cor: string;
  destaque?: boolean;
}) {
  const { colors, type } = useTheme();
  return (
    <View style={{ flex: 1 }}>
      <Text style={[type.caption, { color: colors.textSecondary }]}>{label}</Text>
      <Text style={[destaque ? type.h1 : type.h2, { color: cor, marginTop: 2 }]}>
        {valor}
        {sufixo ? <Text style={[type.caption, { color: colors.textSecondary }]}> {sufixo}</Text> : null}
      </Text>
    </View>
  );
}

/** Barra por dia. Sem dependência de biblioteca — Views com altura proporcional.
 * Verde dentro da meta, laranja acima; a meta vira uma linha tracejada. */
function Barras({
  dias,
  maxKcal,
  meta,
}: {
  dias: { date: string; kcal: number }[];
  maxKcal: number;
  meta: number | null;
}) {
  const { colors } = useTheme();
  const ALTURA = 130;

  return (
    <View style={{ height: ALTURA + 16 }}>
      <View style={{ flexDirection: "row", alignItems: "flex-end", height: ALTURA, gap: 2 }}>
        {dias.map((d) => {
          const h = maxKcal > 0 ? Math.max(d.kcal > 0 ? 3 : 0, (d.kcal / maxKcal) * ALTURA) : 0;
          const acima = meta != null && d.kcal > meta * 1.05;
          return (
            <View
              key={d.date}
              style={{
                flex: 1,
                height: h,
                backgroundColor: d.kcal === 0 ? colors.border : acima ? colors.warning : colors.success,
                borderTopLeftRadius: 3,
                borderTopRightRadius: 3,
              }}
            />
          );
        })}
      </View>
      {/* Linha da meta */}
      {meta != null && maxKcal > 0 ? (
        <View
          pointerEvents="none"
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            bottom: (meta / maxKcal) * ALTURA,
            height: 0,
            borderBottomWidth: 1.5,
            borderStyle: "dashed",
            borderColor: colors.textSecondary,
          }}
        />
      ) : null}
    </View>
  );
}
