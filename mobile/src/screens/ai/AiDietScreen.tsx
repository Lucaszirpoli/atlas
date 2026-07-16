import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TouchableOpacity, View } from "react-native";

import {
  applyDiet,
  generateDiet,
  getDietContext,
  type DietContext,
  type GenerateDietResult,
} from "../../api/ai";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { useTheme } from "../../theme/ThemeProvider";

// Restrições que o motor entende (tokens canônicos = os do backend).
const RESTRICTIONS: { key: string; label: string }[] = [
  { key: "vegano", label: "Vegano" },
  { key: "vegetariano", label: "Vegetariano" },
  { key: "sem_lactose", label: "Sem lactose" },
  { key: "sem_gluten", label: "Sem glúten" },
];

function MacroPill({ label, value, unit, color }: { label: string; value: number | null; unit: string; color: string }) {
  const { colors, type } = useTheme();
  return (
    <View style={{ alignItems: "center", flex: 1 }}>
      <Text style={[type.h2, { color, fontSize: 18 }]}>{value != null ? Math.round(value) : "—"}</Text>
      <Text style={[type.caption, { color: colors.textSecondary, fontSize: 10 }]}>
        {label}
        {unit}
      </Text>
    </View>
  );
}

export function AiDietScreen() {
  const { colors, type, spacing } = useTheme();
  const navigation = useNavigation<any>();

  const [ctx, setCtx] = useState<DietContext | null>(null);
  const [restrictions, setRestrictions] = useState<Set<string>>(new Set());
  const [meals, setMeals] = useState<number>(4);
  const [variant, setVariant] = useState(0);
  const [result, setResult] = useState<GenerateDietResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [applied, setApplied] = useState(false);
  const [info, setInfo] = useState<{ title: string; message: string } | null>(null);

  useEffect(() => {
    getDietContext()
      .then((c) => {
        setCtx(c);
        setRestrictions(new Set(c.profile_restrictions));
      })
      .catch(() => {});
  }, []);

  function toggle(key: string) {
    setRestrictions((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  async function handleGenerate(nextVariant = 0) {
    setLoading(true);
    setResult(null);
    setApplied(false);
    try {
      const r = await generateDiet({
        restrictions: [...restrictions],
        meals_per_day: meals,
        variant: nextVariant,
      });
      setResult(r);
      setVariant(nextVariant);
    } catch (err: any) {
      setInfo({
        title: "Não consegui gerar",
        message: err?.response?.data?.detail ?? "Tente novamente.",
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleApply() {
    if (!result) return;
    setLoading(true);
    try {
      await applyDiet(
        result.plan.meals.map((m) => ({
          category: m.category,
          items: m.items.map((i) => ({ food_id: i.food_id, quantity_g: i.quantity_g })),
        }))
      );
      setApplied(true);
      setInfo({
        title: "Dieta registrada!",
        message: "As refeições de hoje foram lançadas no seu diário. Você pode editar ou remover qualquer item lá.",
      });
    } catch (err: any) {
      setInfo({ title: "Não consegui registrar", message: err?.response?.data?.detail ?? "Tente novamente." });
    } finally {
      setLoading(false);
    }
  }

  // --- Passo 2: plano gerado ------------------------------------------------
  if (result) {
    const p = result.plan;
    return (
      <ScrollView
        style={{ backgroundColor: colors.bg }}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      >
        <TouchableOpacity
          onPress={() => setResult(null)}
          style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}
        >
          <Ionicons name="chevron-back" size={20} color={colors.primary} />
          <Text style={[type.body, { color: colors.primary, fontWeight: "600" }]}>Ajustar opções</Text>
        </TouchableOpacity>

        <Text style={[type.h1, { color: colors.textPrimary }]}>Sua dieta do dia</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
          {p.meals.length} refeições
          {p.restrictions.length ? ` · ${p.restrictions.join(", ")}` : ""}
        </Text>

        {/* Selo de fidelidade — a promessa central: bate a meta de macros */}
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 6,
            backgroundColor: (result.is_faithful ? colors.success : colors.warning) + "22",
            borderRadius: 12,
            paddingVertical: 8,
            paddingHorizontal: 12,
            marginTop: spacing.md,
          }}
        >
          <Ionicons
            name={result.is_faithful ? "shield-checkmark" : "alert-circle"}
            size={16}
            color={result.is_faithful ? colors.success : colors.warning}
          />
          <Text style={[type.caption, { color: colors.textPrimary, flex: 1 }]}>
            {result.is_faithful
              ? "Plano validado: bate sua meta de calorias e macros."
              : "Atenção: não foi possível bater a meta com folga — veja as notas."}
          </Text>
        </View>

        {/* Meta vs. entregue */}
        <Card style={{ marginTop: spacing.md }}>
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
            Total do dia (meta: {Math.round(p.target.kcal)} kcal · P{Math.round(p.target.protein_g)} · C
            {Math.round(p.target.carbs_g)} · G{Math.round(p.target.fat_g)})
          </Text>
          <View style={{ flexDirection: "row" }}>
            <MacroPill label="kcal" value={p.totals.kcal} unit="" color={colors.textPrimary} />
            <MacroPill label="P " value={p.totals.protein_g} unit="g" color={colors.moduleTraining} />
            <MacroPill label="C " value={p.totals.carbs_g} unit="g" color={colors.secondary} />
            <MacroPill label="G " value={p.totals.fat_g} unit="g" color={colors.warning} />
          </View>
        </Card>

        {result.intro ? (
          <Card style={{ marginTop: spacing.md }}>
            <Text style={[type.body, { color: colors.textPrimary }]}>{result.intro}</Text>
          </Card>
        ) : null}
        {result.ai_locked ? (
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
            💡 O cardápio bate sua meta de macros. Assine o Pro para receber a explicação e dicas da IA por refeição.
          </Text>
        ) : null}

        {result.violations.map((v, i) => (
          <Text key={i} style={[type.caption, { color: colors.warning, marginTop: spacing.sm }]}>
            ⚠️ {v}
          </Text>
        ))}

        {p.meals.map((meal, mi) => (
          <Card key={mi} style={{ marginTop: spacing.md }}>
            <Text style={[type.h2, { color: colors.textPrimary, fontSize: 16, marginBottom: spacing.sm }]}>
              {meal.category}
            </Text>
            {meal.items.map((it, i) => (
              <View
                key={i}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  paddingVertical: spacing.sm,
                  borderTopWidth: i === 0 ? 0 : 1,
                  borderTopColor: colors.border,
                }}
              >
                <View style={{ flex: 1 }}>
                  <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600" }]}>{it.food_name}</Text>
                  <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
                    {Math.round(it.quantity_g)}g · {it.kcal} kcal · P{it.protein_g} C{it.carbs_g} G{it.fat_g}
                  </Text>
                </View>
              </View>
            ))}
            {meal.note ? (
              <Text style={[type.caption, { color: colors.primary, marginTop: spacing.sm }]}>💬 {meal.note}</Text>
            ) : null}
          </Card>
        ))}

        <Button
          title={applied ? "Registrado no diário ✓" : "Registrar no diário de hoje"}
          onPress={handleApply}
          disabled={applied || loading}
          style={{ marginTop: spacing.lg }}
        />
        <TouchableOpacity
          onPress={() => handleGenerate(variant + 1)}
          disabled={loading}
          style={{ flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, marginTop: spacing.md }}
        >
          <Ionicons name="refresh" size={18} color={colors.primary} />
          <Text style={[type.body, { color: colors.primary, fontWeight: "600" }]}>Gerar outra opção</Text>
        </TouchableOpacity>
        {loading ? <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.md }} /> : null}

        <InfoDialog visible={info != null} onClose={() => setInfo(null)} title={info?.title ?? ""} message={info?.message} />
      </ScrollView>
    );
  }

  // --- Passo 1: opções ------------------------------------------------------
  const noGoal = ctx != null && ctx.target_kcal == null;
  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
    >
      <Text style={[type.h1, { color: colors.textPrimary }]}>Dieta com IA</Text>
      <Text style={[type.body, { color: colors.textSecondary, marginTop: 4 }]}>
        Um cardápio de um dia inteiro, com alimentos reais, calculado pra bater exatamente sua meta de calorias e
        macros — não é chute, o app resolve as porções.
      </Text>

      {/* Meta atual */}
      <Card style={{ marginTop: spacing.lg }}>
        {ctx == null ? (
          <ActivityIndicator color={colors.primary} />
        ) : noGoal ? (
          <View>
            <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700", marginBottom: 4 }]}>
              Falta definir sua meta
            </Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md }]}>
              Defina sua meta de calorias/macros (ou complete o perfil com peso e objetivo) para a IA montar sua dieta.
            </Text>
            <Button title="Definir minha meta" onPress={() => navigation.navigate("GoalSettings")} />
          </View>
        ) : (
          <View>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
              Sua meta diária {ctx.has_goal_defined ? "" : "(estimada do seu perfil)"}
            </Text>
            <View style={{ flexDirection: "row" }}>
              <MacroPill label="kcal" value={ctx.target_kcal} unit="" color={colors.textPrimary} />
              <MacroPill label="P " value={ctx.target_protein_g} unit="g" color={colors.moduleTraining} />
              <MacroPill label="C " value={ctx.target_carbs_g} unit="g" color={colors.secondary} />
              <MacroPill label="G " value={ctx.target_fat_g} unit="g" color={colors.warning} />
            </View>
          </View>
        )}
      </Card>

      {!noGoal && ctx != null ? (
        <>
          <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
            Restrições alimentares
          </Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm }}>
            {RESTRICTIONS.map((r) => {
              const on = restrictions.has(r.key);
              return (
                <TouchableOpacity
                  key={r.key}
                  onPress={() => toggle(r.key)}
                  style={{
                    backgroundColor: on ? colors.primary : colors.surface,
                    borderWidth: 1,
                    borderColor: on ? colors.primary : colors.border,
                    borderRadius: 20,
                    paddingVertical: spacing.sm,
                    paddingHorizontal: spacing.md,
                  }}
                >
                  <Text style={[type.bodySmall, { color: on ? colors.textOnPrimary : colors.textPrimary, fontWeight: "600" }]}>
                    {r.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
            Quantas refeições por dia?
          </Text>
          <View style={{ flexDirection: "row", gap: spacing.sm }}>
            {[3, 4, 5, 6].map((n) => {
              const on = meals === n;
              return (
                <TouchableOpacity
                  key={n}
                  onPress={() => setMeals(n)}
                  style={{
                    flex: 1,
                    alignItems: "center",
                    backgroundColor: on ? colors.primary : colors.surface,
                    borderWidth: 1,
                    borderColor: on ? colors.primary : colors.border,
                    borderRadius: 14,
                    paddingVertical: spacing.md,
                  }}
                >
                  <Text style={[type.body, { color: on ? colors.textOnPrimary : colors.textPrimary, fontWeight: "700" }]}>
                    {n}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs }]}>
            {meals <= 3
              ? "Café, almoço e jantar"
              : meals === 4
                ? "Café, almoço, lanche da tarde e jantar"
                : meals === 5
                  ? "Café, almoço, lanche, jantar e ceia"
                  : "Café, lanche da manhã, almoço, lanche da tarde, jantar e ceia"}
          </Text>

          <Button
            title="Gerar minha dieta"
            onPress={() => handleGenerate(0)}
            disabled={loading}
            style={{ marginTop: spacing.xl }}
          />
          {loading ? <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.lg }} size="large" /> : null}

          {/* A outra forma de montar dieta: moldes prontos curados (sem IA). */}
          <TouchableOpacity
            activeOpacity={0.85}
            onPress={() => navigation.navigate("DietTemplates")}
            style={{
              flexDirection: "row",
              alignItems: "center",
              backgroundColor: colors.surface,
              borderWidth: 1,
              borderColor: colors.border,
              borderRadius: 14,
              padding: spacing.md,
              marginTop: spacing.xl,
            }}
          >
            <Ionicons name="restaurant-outline" size={20} color={colors.secondary} />
            <View style={{ flex: 1, marginLeft: spacing.sm }}>
              <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]}>
                Prefere uma dieta pronta?
              </Text>
              <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
                Clássica, low carb, alta proteína… já ajustadas pra sua meta
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
          </TouchableOpacity>
        </>
      ) : null}

      <InfoDialog visible={info != null} onClose={() => setInfo(null)} title={info?.title ?? ""} message={info?.message} />
    </ScrollView>
  );
}
