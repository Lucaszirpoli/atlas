import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Modal, Pressable, ScrollView, Text, TouchableOpacity, View } from "react-native";

import {
  applyDietTemplate,
  listDietTemplates,
  previewDietTemplate,
  type DietContext,
  type DietTemplatePreview,
  type DietTemplateSummary,
} from "../../api/dietTemplates";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { InfoDialog } from "../../components/InfoDialog";
import { useTheme } from "../../theme/ThemeProvider";
import { exportDietAsPdf } from "../../utils/pdfExport";

const GOAL_LABELS: Record<string, string> = {
  emagrecimento: "Emagrecimento",
  hipertrofia: "Hipertrofia",
  manutencao: "Manutenção",
  performance: "Performance",
  recomposicao: "Recomposição",
};

export function DietTemplatesScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();

  const [context, setContext] = useState<DietContext | null>(null);
  const [templates, setTemplates] = useState<DietTemplateSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const [preview, setPreview] = useState<DietTemplatePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [confirmVisible, setConfirmVisible] = useState(false);
  const [applying, setApplying] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  async function handleDownload() {
    if (!preview || downloading) return;
    setDownloading(true);
    try {
      await exportDietAsPdf({
        name: preview.name,
        tagline: preview.tagline,
        meals: preview.meals.map((m) => ({
          category: m.category,
          items: m.items.map((i) => ({ food_name: i.food_name, quantity_g: i.quantity_g, kcal: i.kcal })),
        })),
        totals: preview.totals,
      });
    } finally {
      setDownloading(false);
    }
  }

  useEffect(() => {
    listDietTemplates()
      .then((r) => {
        setContext(r.context);
        setTemplates(r.templates);
      })
      .finally(() => setLoading(false));
  }, []);

  async function openPreview(id: string) {
    setPreviewLoading(true);
    setPreview(null);
    try {
      setPreview(await previewDietTemplate(id));
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleApply() {
    if (!preview) return;
    setApplying(true);
    try {
      const r = await applyDietTemplate(preview.id);
      setPreview(null);
      setSuccess(
        `Pronto! Registrei "${r.template_name}" no seu diário de hoje — ${r.items_logged} alimentos, ${r.totals.kcal} kcal. ` +
          "Você pode ajustar ou remover qualquer item na aba Dieta."
      );
    } finally {
      setApplying(false);
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }} showsVerticalScrollIndicator={false}>
        {/* Nota breve: as porções já vêm ajustadas à meta calórica (ver kcal em cada card abaixo). */}
        <TouchableOpacity
          activeOpacity={0.7}
          onPress={() => navigation.navigate("GoalSettings")}
          style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: spacing.md }}
        >
          <Ionicons name="information-circle-outline" size={15} color={colors.textSecondary} />
          <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]}>
            As porções já vêm ajustadas à sua meta ({context?.target_kcal ?? "—"} kcal). Pra mudar, toque aqui e ajuste em "Meta".
          </Text>
        </TouchableOpacity>

        <Text
          style={[
            type.caption,
            { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" },
          ]}
        >
          Escolha uma dieta pronta
        </Text>

        {templates.map((t) => (
          <TouchableOpacity key={t.id} activeOpacity={0.85} onPress={() => openPreview(t.id)}>
            <Card style={{ marginBottom: spacing.md }}>
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <View style={{ flex: 1 }}>
                  <Text style={[type.h2, { color: colors.textPrimary }]}>{t.name}</Text>
                  <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 2 }]}>{t.tagline}</Text>
                </View>
                <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
              </View>
              <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm }}>
                <Pill icon="flame" text={`${t.scaled_kcal} kcal`} color={colors.primary} colors={colors} type={type} radius={radius} />
                <Pill
                  icon="barbell"
                  text={`${Math.round(t.scaled_protein_g)}g proteína`}
                  color={colors.moduleTraining}
                  colors={colors}
                  type={type}
                  radius={radius}
                />
              </View>
              {t.goals.length > 0 ? (
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: spacing.sm }}>
                  {t.goals.slice(0, 3).map((g) => (
                    <View
                      key={g}
                      style={{ backgroundColor: colors.surfaceAlt, borderRadius: radius.pill, paddingVertical: 3, paddingHorizontal: 9 }}
                    >
                      <Text style={[type.caption, { color: colors.textSecondary, fontSize: 11 }]}>{GOAL_LABELS[g] ?? g}</Text>
                    </View>
                  ))}
                </View>
              ) : null}
            </Card>
          </TouchableOpacity>
        ))}

        <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 17 }]}>
          Dietas são um ponto de partida — não substituem orientação de um nutricionista.
        </Text>
      </ScrollView>

      {/* Preview do dia inteiro escalado */}
      <Modal visible={preview !== null || previewLoading} transparent animationType="slide" onRequestClose={() => setPreview(null)}>
        <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.45)", justifyContent: "flex-end" }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: "88%" }}>
            {previewLoading || !preview ? (
              <View style={{ padding: spacing.xxl, alignItems: "center" }}>
                <ActivityIndicator color={colors.primary} size="large" />
              </View>
            ) : (
              <>
                <View
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    padding: spacing.lg,
                    borderBottomWidth: 1,
                    borderBottomColor: colors.border,
                  }}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={[type.h1, { color: colors.textPrimary }]}>{preview.name}</Text>
                    <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 2 }]}>{preview.tagline}</Text>
                  </View>
                  <TouchableOpacity onPress={() => setPreview(null)} hitSlop={10}>
                    <Ionicons name="close" size={26} color={colors.textSecondary} />
                  </TouchableOpacity>
                </View>

                <ScrollView contentContainerStyle={{ padding: spacing.lg }} showsVerticalScrollIndicator={false}>
                  <Text style={[type.bodySmall, { color: colors.textSecondary, lineHeight: 20, marginBottom: spacing.md }]}>
                    {preview.description}
                  </Text>

                  {/* Totais do dia */}
                  <View
                    style={{
                      flexDirection: "row",
                      justifyContent: "space-around",
                      backgroundColor: colors.surface,
                      borderRadius: radius.card,
                      borderWidth: 1,
                      borderColor: colors.border,
                      paddingVertical: spacing.md,
                      marginBottom: spacing.md,
                    }}
                  >
                    <Total label="kcal" value={`${preview.totals.kcal}`} colors={colors} type={type} />
                    <Total label="proteína" value={`${Math.round(preview.totals.protein_g)}g`} colors={colors} type={type} />
                    <Total label="carbo" value={`${Math.round(preview.totals.carbs_g)}g`} colors={colors} type={type} />
                    <Total label="gordura" value={`${Math.round(preview.totals.fat_g)}g`} colors={colors} type={type} />
                  </View>

                  {preview.meals.map((meal) => (
                    <View key={meal.category} style={{ marginBottom: spacing.md }}>
                      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", marginBottom: spacing.xs }]}>
                        {meal.category}
                      </Text>
                      {meal.items.map((it) => (
                        <View key={it.food_id + it.food_name} style={{ flexDirection: "row", alignItems: "center", paddingVertical: 4 }}>
                          <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1 }]} numberOfLines={1}>
                            {it.food_name}
                            <Text style={{ color: colors.textSecondary }}> · {Math.round(it.quantity_g)}g</Text>
                          </Text>
                          <Text style={[type.caption, { color: colors.textSecondary }]}>{it.kcal} kcal</Text>
                        </View>
                      ))}
                    </View>
                  ))}
                </ScrollView>

                <View style={{ padding: spacing.lg, borderTopWidth: 1, borderTopColor: colors.border }}>
                  <TouchableOpacity
                    onPress={handleDownload}
                    disabled={downloading}
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 6,
                      paddingVertical: 10,
                      borderRadius: radius.pill,
                      borderWidth: 1,
                      borderColor: colors.border,
                      marginBottom: spacing.sm,
                    }}
                  >
                    {downloading ? (
                      <ActivityIndicator size="small" color={colors.textSecondary} />
                    ) : (
                      <Ionicons name="download-outline" size={16} color={colors.textSecondary} />
                    )}
                    <Text style={[type.bodySmall, { color: colors.textSecondary, fontWeight: "700" }]}>Baixar PDF</Text>
                  </TouchableOpacity>
                  <Button title="Usar esta dieta hoje" onPress={() => setConfirmVisible(true)} loading={applying} />
                  <Text style={[type.caption, { color: colors.textSecondary, textAlign: "center", marginTop: spacing.sm }]}>
                    Registra tudo no seu diário de hoje — você pode editar depois.
                  </Text>
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>

      <ConfirmDialog
        visible={confirmVisible}
        onClose={() => setConfirmVisible(false)}
        title="Usar esta dieta hoje?"
        message={
          preview
            ? `Vou registrar as ${preview.meals.length} refeições dessa dieta (${preview.totals.kcal} kcal) no seu diário de hoje. Isso não apaga o que você já registrou — só adiciona.`
            : undefined
        }
        confirmLabel="Registrar"
        onConfirm={handleApply}
      />

      <InfoDialog
        visible={success !== null}
        onClose={() => {
          setSuccess(null);
          navigation.navigate("Diary");
        }}
        title="Dieta registrada ✓"
        message={success ?? undefined}
      />
    </View>
  );
}

function Pill({
  icon,
  text,
  color,
  colors,
  type,
  radius,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  text: string;
  color: string;
  colors: any;
  type: any;
  radius: any;
}) {
  return (
    <View
      style={{
        flexDirection: "row",
        alignItems: "center",
        gap: 5,
        backgroundColor: color + "1A",
        borderRadius: radius.pill,
        paddingVertical: 4,
        paddingHorizontal: 10,
      }}
    >
      <Ionicons name={icon} size={13} color={color} />
      <Text style={[type.caption, { color, fontWeight: "700", fontSize: 12 }]}>{text}</Text>
    </View>
  );
}

function Total({ label, value, colors, type }: { label: string; value: string; colors: any; type: any }) {
  return (
    <View style={{ alignItems: "center" }}>
      <Text style={[type.h2, { color: colors.textPrimary }]}>{value}</Text>
      <Text style={[type.caption, { color: colors.textSecondary, fontSize: 11 }]}>{label}</Text>
    </View>
  );
}
