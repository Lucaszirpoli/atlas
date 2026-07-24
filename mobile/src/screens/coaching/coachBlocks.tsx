import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import { Modal, Text, TouchableOpacity, View } from "react-native";

import {
  buildCoachWorkout,
  setTrainingPrefs,
  type CoachingAnalysis,
  type TrainingPrefs,
} from "../../api/coaching";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

// Blocos reutilizáveis do coaching — extraídos da CoachingScreen para poderem
// aparecer TAMBÉM como cabeçalho do coach no topo das telas de módulo (Treino,
// Dieta). Assim o Pro vê a análise do coach + a funcionalidade manual na mesma
// tela, sem duplicar código.

// Chip de macro (meta + média) — usado na dieta.
export function MacroChip({
  label,
  goal,
  avg,
  color,
}: {
  label: string;
  goal: number | null;
  avg: number | null;
  color: string;
}) {
  const { colors, type } = useTheme();
  return (
    <View style={{ flex: 1 }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 5, marginBottom: 2 }}>
        <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: color }} />
        <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
          {label}
        </Text>
      </View>
      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]} numberOfLines={1}>
        {goal != null ? `${Math.round(goal)}g` : "—"}
      </Text>
      {avg != null ? (
        <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
          méd {Math.round(avg)}g
        </Text>
      ) : null}
    </View>
  );
}

// Card "Sua meta atual" da dieta — kcal/dia + macros. Usado no cabeçalho do
// coach na tela de Dieta.
export function DietMetaCard({ metrics }: { metrics: CoachingAnalysis["metrics"] }) {
  const { colors, type, spacing } = useTheme();
  const m = metrics;
  return (
    <Card style={{ marginBottom: spacing.md }}>
      <Text
        style={[
          type.caption,
          { color: colors.primary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: spacing.sm },
        ]}
      >
        Sua meta atual
      </Text>
      {m.goal_kcal ? (
        <>
          <View style={{ flexDirection: "row", alignItems: "baseline", gap: 5, marginBottom: spacing.sm }}>
            <Text style={[type.display, { color: colors.textPrimary, fontSize: 30 }]}>{Math.round(m.goal_kcal)}</Text>
            <Text style={[type.body, { color: colors.textSecondary }]}>kcal / dia</Text>
          </View>
          <View style={{ flexDirection: "row", gap: spacing.md }}>
            <MacroChip label="Proteína" goal={m.protein_target_g} avg={m.avg_protein_g} color={colors.moduleTraining} />
            <MacroChip label="Carbo" goal={m.goal_carbs_g} avg={m.avg_carbs_g} color={colors.info} />
            <MacroChip label="Gordura" goal={m.goal_fat_g} avg={m.avg_fat_g} color={colors.warning} />
          </View>
          {m.avg_kcal != null ? (
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
              Média recente: {Math.round(m.avg_kcal)} kcal/dia.
            </Text>
          ) : null}
        </>
      ) : (
        <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
          Você ainda não tem meta calórica. Defina uma pra o coach acompanhar sua dieta.
        </Text>
      )}
    </Card>
  );
}

// Setinha de expandir/recolher.
export function ExpandToggle({ expanded, onPress }: { expanded: boolean; onPress: () => void }) {
  const { colors } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      hitSlop={8}
      style={{
        width: 28,
        height: 28,
        borderRadius: 8,
        backgroundColor: colors.surfaceAlt,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Ionicons name={expanded ? "chevron-up" : "chevron-down"} size={16} color={colors.textSecondary} />
    </TouchableOpacity>
  );
}

// Uma linha da lista "Como eu monto seu treino": ícone + rótulo + valor atual.
function PrefRow({
  icon,
  label,
  value,
  onPress,
  last,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
  onPress: () => void;
  last?: boolean;
}) {
  const { colors, type } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.7}
      style={{ flexDirection: "row", alignItems: "center", gap: 10, paddingVertical: 11, borderBottomWidth: last ? 0 : 1, borderBottomColor: colors.border }}
    >
      <Ionicons name={icon} size={17} color={colors.textSecondary} />
      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600", flex: 1 }]}>{label}</Text>
      <Text style={[type.caption, { color: colors.textSecondary, maxWidth: 160, textAlign: "right" }]} numberOfLines={1}>
        {value}
      </Text>
      <Ionicons name="chevron-forward" size={15} color={colors.textSecondary} />
    </TouchableOpacity>
  );
}

// Folha de opções (sobe de baixo): radio + descrição por opção. Toca e aplica.
// `multi`: vira multi-seleção (checkbox) com teto `maxSelected` e botão Salvar.
type SheetConfig = {
  title: string;
  subtitle: string;
  options: { value: string; label: string; desc?: string }[];
  current?: string;
  pick?: (v: string) => void;
  multi?: boolean;
  maxSelected?: number;
  selected?: string[];
  onSaveMulti?: (values: string[]) => void;
};

function OptionSheet({
  visible,
  config,
  onClose,
}: {
  visible: boolean;
  config: SheetConfig | null;
  onClose: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [sel, setSel] = useState<string[]>([]);
  const maxSel = config?.maxSelected ?? 2;
  useEffect(() => {
    if (visible && config?.multi) setSel(config.selected ?? []);
  }, [visible, config?.multi, config?.selected]);

  function toggle(v: string) {
    setSel((cur) => {
      if (cur.includes(v)) return cur.filter((x) => x !== v);
      if (cur.length >= maxSel) return cur;
      return [...cur, v];
    });
  }

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <TouchableOpacity activeOpacity={1} onPress={onClose} style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.6)", justifyContent: "flex-end" }}>
        <TouchableOpacity activeOpacity={1} onPress={() => {}} style={{ backgroundColor: colors.surface, borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: spacing.lg, paddingBottom: spacing.xl }}>
          {config ? (
            <>
              <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.xs }}>
                <Text style={[type.h2, { color: colors.textPrimary, flex: 1 }]}>{config.title}</Text>
                <TouchableOpacity onPress={onClose} hitSlop={10} style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" }}>
                  <Ionicons name="close" size={18} color={colors.textPrimary} />
                </TouchableOpacity>
              </View>
              <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 18 }]}>{config.subtitle}</Text>
              {config.options.map((o) => {
                const on = config.multi ? sel.includes(o.value) : o.value === config.current;
                const atCap = !!config.multi && !on && sel.length >= maxSel;
                return (
                  <TouchableOpacity
                    key={o.value}
                    activeOpacity={0.7}
                    disabled={atCap}
                    onPress={() => (config.multi ? toggle(o.value) : config.pick?.(o.value))}
                    style={{
                      flexDirection: "row",
                      alignItems: "flex-start",
                      gap: 10,
                      borderWidth: 1,
                      borderColor: on ? colors.primary : colors.border,
                      backgroundColor: on ? colors.primary + "12" : "transparent",
                      borderRadius: radius.card,
                      padding: spacing.sm,
                      marginBottom: spacing.xs,
                      opacity: atCap ? 0.45 : 1,
                    }}
                  >
                    <Ionicons
                      name={
                        config.multi
                          ? on
                            ? "checkbox"
                            : "square-outline"
                          : on
                          ? "radio-button-on"
                          : "radio-button-off"
                      }
                      size={18}
                      color={on ? colors.primary : colors.textSecondary}
                      style={{ marginTop: 1 }}
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: on ? "700" : "600" }]}>{o.label}</Text>
                      {o.desc ? <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, lineHeight: 17 }]}>{o.desc}</Text> : null}
                    </View>
                  </TouchableOpacity>
                );
              })}
              {config.multi ? (
                <View style={{ marginTop: spacing.sm }}>
                  <Button
                    title={sel.length ? `Salvar (${sel.length} de ${maxSel})` : "Salvar — nenhum"}
                    onPress={() => config.onSaveMulti?.(sel)}
                  />
                </View>
              ) : null}
            </>
          ) : null}
        </TouchableOpacity>
      </TouchableOpacity>
    </Modal>
  );
}

// "Como eu monto seu treino": ponto fraco, tempo por sessão, cardio,
// periodização. O coach usa tudo isto pra montar/ajustar o treino.
type PrefSheetField = "weak_point" | "session_length" | "training_days" | "cardio" | "periodization";

export function TrainingPrefsCard({
  prefs,
  onChanged,
}: {
  prefs: TrainingPrefs;
  onChanged: (title: string, message: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [sheet, setSheet] = useState<PrefSheetField | null>(null);
  const [expanded, setExpanded] = useState(false);

  async function salvar(update: Parameters<typeof setTrainingPrefs>[0], titulo: string) {
    setSheet(null);
    try {
      const r = await setTrainingPrefs(update);
      onChanged(titulo, r.message);
    } catch {
      // silencioso — recarrega no próximo foco
    }
  }

  const pontoFracoTxt = prefs.weak_points_labels.length ? prefs.weak_points_labels.join(" + ") : "Nenhum";
  const tempoOpt = prefs.session_length_options.find((x) => x.value === prefs.session_length);
  const tempoTxt = tempoOpt ? `${tempoOpt.label} · ${tempoOpt.range}` : "Não definido";
  const diasTxt = prefs.training_days_per_week ? `${prefs.training_days_per_week}× por semana` : "Automático";
  const cardioTxt = prefs.wants_cardio == null ? "Não definido" : prefs.wants_cardio ? "Com cardio" : "Sem cardio";
  const periodTxt = prefs.periodization_options.find((x) => x.value === prefs.periodization)?.label ?? "Automática";

  const sheetConfig =
    sheet === "weak_point"
      ? {
          title: "Ponto fraco",
          subtitle: `Grupos pra priorizar nos acessórios — pode escolher até ${prefs.weak_points_max}. Opcional: o coach dá um empurrão extra neles ao montar o treino.`,
          multi: true,
          maxSelected: prefs.weak_points_max,
          selected: prefs.weak_points,
          options: prefs.weak_point_options.map((o) => ({ value: o.value, label: o.label })),
          onSaveMulti: (values: string[]) => salvar({ weak_points: values }, "Ponto fraco"),
        }
      : sheet === "session_length"
      ? {
          title: "Tempo por sessão",
          subtitle: "Quanto tempo você tem por treino. Define o tamanho do treino que o coach monta.",
          current: prefs.session_length ?? "",
          options: prefs.session_length_options.map((o) => ({ value: o.value, label: o.label, desc: o.range })),
          pick: (v: string) => salvar({ session_length: v as any }, "Tempo por sessão"),
        }
      : sheet === "training_days"
      ? {
          title: "Dias por semana",
          subtitle: "Quantos dias você pode treinar. É por aqui que o coach decide quantos treinos montar (2 a 7). No automático, ele infere pelos dias do seu perfil.",
          current: prefs.training_days_per_week ? String(prefs.training_days_per_week) : "__auto__",
          options: [
            { value: "__auto__", label: "Automático", desc: "O coach usa os dias que você marcou no perfil." },
            ...prefs.training_days_options.map((n) => ({
              value: String(n),
              label: `${n} dias`,
              desc:
                n <= 2
                  ? "Full body — cada grupo ~2× na semana."
                  : n <= 4
                  ? "Superior/inferior — 2× por grupo, bem equilibrado."
                  : "Push/pull/pernas repetido — volume alto, 2×+ por grupo.",
            })),
          ],
          pick: (v: string) =>
            salvar({ training_days_per_week: v === "__auto__" ? null : parseInt(v, 10) }, "Dias por semana"),
        }
      : sheet === "cardio"
      ? {
          title: "Cardio",
          subtitle: "Se você quer cardio no plano. Sem cardio, o coach avisa quando o seu objetivo pedir.",
          current: prefs.wants_cardio == null ? "" : prefs.wants_cardio ? "sim" : "nao",
          options: [
            { value: "sim", label: "Com cardio", desc: "Inclui condicionamento junto da musculação." },
            { value: "nao", label: "Sem cardio", desc: "Só musculação. Bom pra quem prioriza força/massa." },
          ],
          pick: (v: string) => salvar({ wants_cardio: v === "sim" }, "Cardio"),
        }
      : sheet === "periodization"
      ? {
          title: "Periodização",
          subtitle: "Como a carga e o volume evoluem ao longo das semanas — e se tem deload.",
          current: prefs.periodization,
          options: prefs.periodization_options.map((o) => ({ value: o.value, label: o.label, desc: o.desc })),
          pick: (v: string) => salvar({ periodization: v as any }, "Periodização"),
        }
      : null;

  const resumo = `${diasTxt} · ${pontoFracoTxt === "Nenhum" ? "sem ponto fraco" : pontoFracoTxt}`;

  return (
    <Card style={{ marginBottom: spacing.md }}>
      <TouchableOpacity
        onPress={() => setExpanded((v) => !v)}
        activeOpacity={0.7}
        style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
      >
        <Ionicons name="construct" size={16} color={colors.primary} />
        <Text style={[type.caption, { color: colors.primary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase", flex: 1 }]}>
          Como eu monto seu treino
        </Text>
        <Ionicons name={expanded ? "chevron-up" : "chevron-down"} size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 17 }]}>
        {expanded
          ? "O coach usa isto pra montar e ajustar seu treino: priorizar um músculo, caber nos seus dias e no seu tempo, e escolher técnica e deload na hora certa."
          : resumo}
      </Text>

      {expanded ? (
        <View style={{ marginTop: spacing.xs }}>
          <PrefRow icon="fitness" label="Ponto fraco" value={pontoFracoTxt} onPress={() => setSheet("weak_point")} />
          <PrefRow icon="calendar" label="Dias por semana" value={diasTxt} onPress={() => setSheet("training_days")} />
          <PrefRow icon="time" label="Tempo por sessão" value={tempoTxt} onPress={() => setSheet("session_length")} />
          <PrefRow icon="heart" label="Cardio" value={cardioTxt} onPress={() => setSheet("cardio")} />
          <PrefRow icon="repeat" label="Periodização" value={periodTxt} onPress={() => setSheet("periodization")} last />

          {prefs.cardio_warning ? (
            <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 6, marginTop: spacing.sm, backgroundColor: colors.warning + "14", borderRadius: radius.card, padding: spacing.sm }}>
              <Ionicons name="alert-circle" size={15} color={colors.warning} style={{ marginTop: 1 }} />
              <Text style={[type.caption, { color: colors.textSecondary, flex: 1, lineHeight: 18 }]}>{prefs.cardio_warning}</Text>
            </View>
          ) : null}
        </View>
      ) : null}

      <OptionSheet visible={sheet != null} config={sheetConfig} onClose={() => setSheet(null)} />
    </Card>
  );
}

// "Seu treino": o treino completo que o coach monta a partir das preferências.
export function WorkoutCard({
  workout,
  onApplied,
  onOpenTraining,
}: {
  workout: CoachingAnalysis["metrics"]["workout"];
  onApplied: (title: string, message: string) => void;
  onOpenTraining: () => void;
}) {
  const { colors, type, spacing } = useTheme();
  const [building, setBuilding] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const built = !!workout?.built;

  async function montar() {
    setErro(null);
    setBuilding(true);
    try {
      const r = await buildCoachWorkout();
      const extra = r.cardio_note ? `\n\n${r.cardio_note}` : "";
      const tecnica = r.technique_note ? `\n\n${r.technique_note}` : "";
      const foco = r.weak_point_label ? ` Priorizei ${r.weak_point_label}.` : "";
      onApplied("Treino montado", `${r.message}${foco}${extra}${tecnica}`);
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui montar agora."));
    } finally {
      setBuilding(false);
    }
  }

  const resumo =
    built && workout
      ? `${workout.count} treino${workout.count === 1 ? "" : "s"} · ${workout.total_exercises} exercícios no total.`
      : "Ainda não montei seu treino — abra pra montar com suas preferências.";

  return (
    <Card style={{ marginBottom: spacing.md }}>
      <TouchableOpacity
        onPress={() => setExpanded((v) => !v)}
        activeOpacity={0.7}
        style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
      >
        <Ionicons name="barbell" size={16} color={colors.primary} />
        <Text style={[type.caption, { color: colors.primary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase", flex: 1 }]}>
          Seu treino
        </Text>
        {built ? (
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
            <Ionicons name="checkmark-circle" size={14} color={colors.success} />
            <Text style={[type.caption, { color: colors.success, fontWeight: "700" }]}>Aplicado</Text>
          </View>
        ) : null}
        <Ionicons name={expanded ? "chevron-up" : "chevron-down"} size={18} color={colors.textSecondary} />
      </TouchableOpacity>
      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 17 }]}>{resumo}</Text>

      {expanded ? (
        built && workout ? (
          <View style={{ marginTop: spacing.xs }}>
            {workout.routines.map((r) => (
              <TouchableOpacity
                key={r.id}
                onPress={onOpenTraining}
                activeOpacity={0.7}
                style={{ flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 9, borderTopWidth: 1, borderTopColor: colors.border }}
              >
                <View style={{ width: 26, height: 26, borderRadius: 8, backgroundColor: colors.surfaceAlt, alignItems: "center", justifyContent: "center" }}>
                  <Ionicons name="fitness" size={14} color={colors.primary} />
                </View>
                <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600", flex: 1 }]} numberOfLines={1}>
                  {r.name}
                </Text>
                <Text style={[type.caption, { color: colors.textSecondary }]}>{r.exercises} ex.</Text>
                <Ionicons name="chevron-forward" size={15} color={colors.textSecondary} />
              </TouchableOpacity>
            ))}
            <View style={{ marginTop: spacing.md }}>
              <Button
                title={building ? "Montando..." : "Refazer com base nas minhas preferências"}
                variant="secondary"
                compact
                loading={building}
                onPress={montar}
              />
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4, textAlign: "center" }]}>
                Arquiva o treino atual e monta um novo. Seu histórico continua intacto.
              </Text>
            </View>
          </View>
        ) : (
          <View style={{ marginTop: spacing.sm }}>
            <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 17 }]}>
              Deixa que eu monto seu treino completo com base no que você definiu acima — dias por semana, ponto fraco,
              tempo por sessão e periodização. Fica salvo nas suas rotinas, pronto pra treinar.
            </Text>
            <Button title={building ? "Montando..." : "Montar meu treino"} loading={building} onPress={montar} />
          </View>
        )
      ) : null}
      {erro ? (
        <Text style={[type.caption, { color: colors.warning, marginTop: 6, textAlign: "center" }]}>{erro}</Text>
      ) : null}
    </Card>
  );
}
