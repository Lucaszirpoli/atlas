import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TouchableOpacity, View } from "react-native";

import {
  generateTraining,
  getTrainingMethodDetail,
  getTrainingMethods,
  type GenerateTrainingResult,
  type TrainingMethod,
  type TrainingMethodDetail,
} from "../../api/ai";
import { createRoutinesBulk, listRoutines } from "../../api/routines";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

const EXP_LABEL: Record<string, string> = {
  beginner: "Iniciante+",
  intermediate: "Intermediário+",
  advanced: "Avançado",
};

// Os valores batem com o enum MuscleGroup do backend. Só músculos que fazem
// sentido como "ponto fraco" de quem treina — nada de full_body/cardio.
const WEAK_POINT_OPTIONS: { value: string | null; label: string }[] = [
  { value: null, label: "Nenhum" },
  { value: "chest", label: "Peito" },
  { value: "back", label: "Costas" },
  { value: "shoulders", label: "Ombros" },
  { value: "biceps", label: "Bíceps" },
  { value: "triceps", label: "Tríceps" },
  { value: "quads", label: "Quadríceps" },
  { value: "hamstrings", label: "Posterior" },
  { value: "glutes", label: "Glúteos" },
  { value: "calves", label: "Panturrilha" },
  { value: "abs", label: "Abdômen" },
];

/** Linha "rótulo: valor" da ficha do método. Some quando o método não define
 *  aquele parâmetro (ex: Westside não fixa séries/reps — quem manda é a fase). */
function SpecRow({ label, value }: { label: string; value: string | null }) {
  const { colors, type, spacing } = useTheme();
  if (!value) return null;
  return (
    <View style={{ flexDirection: "row", marginBottom: spacing.xs }}>
      <Text style={[type.caption, { color: colors.textSecondary, width: 116 }]}>{label}</Text>
      <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1, lineHeight: 19 }]}>{value}</Text>
    </View>
  );
}

/** Extrai o primeiro inteiro de um texto ("2 séries" -> 2, "6-8" -> 6). */
function firstInt(s: string, fallback: number): number {
  const m = s.match(/\d+/);
  return m ? Number(m[0]) : fallback;
}
function repsRange(s: string): [number, number | null] {
  const nums = (s.match(/\d+/g) ?? []).map(Number);
  if (nums.length === 0) return [8, 12];
  if (nums.length === 1) return [nums[0], null];
  return [nums[0], nums[1]];
}

type Session = GenerateTrainingResult["plan"]["sessions"][number];

// Nome da rotina de uma sessão — é a "identidade" que usamos pra dedup: se já
// existe uma rotina com esse nome, o treino daquele dia já está salvo.
function routineNameFor(methodName: string, session: Session): string {
  return `${methodName} — ${session.day_label} · ${session.focus}`;
}

function slotsToExercises(session: Session) {
  return session.slots
    .filter((s) => s.exercise_id != null)
    .map((s) => {
      const [rmin, rmax] = repsRange(s.reps);
      return {
        exercise_id: s.exercise_id as number,
        target_sets: firstInt(s.sets, 3),
        target_reps_min: rmin,
        target_reps_max: rmax,
        rest_seconds: firstInt(s.rest_seconds ?? "", 90),
        notes: s.note ?? null,
      };
    });
}

export function AiHubScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();
  const isPro = user?.plan === "pro";

  const [methods, setMethods] = useState<TrainingMethod[]>([]);
  const [selected, setSelected] = useState<TrainingMethod | null>(null);
  // Ficha completa do método aberto. Buscada só ao abrir (a lista continua
  // leve) — é o que dá a explicação detalhada e diz se o método aceita ponto
  // fraco. Null enquanto carrega: a tela mostra o resumo que já tem.
  const [detail, setDetail] = useState<TrainingMethodDetail | null>(null);
  const [weakPoint, setWeakPoint] = useState<string | null>(null);
  const [days, setDays] = useState<number | null>(null);
  const [result, setResult] = useState<GenerateTrainingResult | null>(null);
  const [loading, setLoading] = useState(false);
  // Índices das sessões que já estão salvas nas rotinas do usuário (✓).
  const [savedIndices, setSavedIndices] = useState<Set<number>>(new Set());
  // Resumo do que foi salvo automaticamente ao gerar o plano.
  const [saveSummary, setSaveSummary] = useState<{ created: number; existing: number } | null>(null);
  const [info, setInfo] = useState<{ title: string; message: string } | null>(null);

  useEffect(() => {
    getTrainingMethods()
      .then(setMethods)
      .catch(() => {});
  }, []);

  // Ao escolher o método + os dias, o treino COMPLETO já vai pras rotinas do
  // usuário automaticamente. Dedup por nome: se ele já tinha salvado esse
  // método antes e só excluiu o treino de algum dia, só o(s) dia(s) que
  // faltam são recriados — os que já existem não duplicam.
  // Abre a ficha do método. A explicação detalhada e a opção de ponto fraco só
  // existem aqui — a lista fica com o resumo, pra carregar rápido.
  function openMethod(m: TrainingMethod) {
    setSelected(m);
    setDetail(null);
    setWeakPoint(null);
    getTrainingMethodDetail(m.key)
      .then(setDetail)
      // Sem a ficha, a tela ainda funciona com o resumo da lista: dá pra
      // escolher os dias e gerar. Não vale bloquear o treino por causa do texto.
      .catch(() => {});
  }

  async function handleGenerate(method: TrainingMethod, d: number) {
    setLoading(true);
    setResult(null);
    setSavedIndices(new Set());
    setSaveSummary(null);
    try {
      const r = await generateTraining({
        method_key: method.key,
        available_days: d,
        // Só manda quando o método aceita — nos outros o backend ignora.
        weak_point: detail?.targets_weak_point ? weakPoint : null,
      });
      setResult(r);
      await autoSavePlan(r);
    } catch (err: any) {
      setInfo({ title: "Não consegui gerar", message: err?.response?.data?.detail ?? "Tente novamente." });
    } finally {
      setLoading(false);
    }
  }

  // "Criar treino com IA": conversa — a IA pergunta rotina/objetivo/dias/local
  // e monta o treino pra pessoa. Pro-only; Free vê o card mas cai no paywall.
  function handleCreateWithAi() {
    if (!isPro) {
      navigation.navigate("Paywall");
      return;
    }
    navigation.navigate("Assistant", {
      autoSend:
        "Quero que você monte um treino personalizado pra mim. Me pergunte o que precisar — " +
        "meu objetivo, quantos dias por semana posso treinar, onde treino (academia completa/básica ou casa), " +
        "quanto tempo tenho por sessão, e preferências ou limitações. Depois monte o treino completo.",
    });
  }

  async function autoSavePlan(r: GenerateTrainingResult) {
    try {
      const existing = await listRoutines();
      const existingNames = new Set(existing.map((x) => x.name));
      const saved = new Set<number>();

      // UMA chamada atômica pros dias que faltam. Antes era um laço de N
      // createRoutine soltos: se um dia falhava, o erro aparecia mas os
      // anteriores FICAVAM salvos — foi assim que um método de 4 dias virou 3
      // no aparelho (o Dia 1 morreu e os outros ficaram).
      const pendentes: number[] = [];
      let already = 0;
      for (let i = 0; i < r.plan.sessions.length; i++) {
        const name = routineNameFor(r.plan.method_name, r.plan.sessions[i]);
        if (existingNames.has(name)) {
          already += 1;
          saved.add(i);
        } else {
          pendentes.push(i);
        }
      }

      if (pendentes.length > 0) {
        const res = await createRoutinesBulk({
          rotinas: pendentes.map((i) => ({
            nome: routineNameFor(r.plan.method_name, r.plan.sessions[i]),
            exercicios: slotsToExercises(r.plan.sessions[i]).map((e) => ({
              exercise_id: e.exercise_id,
              target_sets: e.target_sets,
              target_reps_min: e.target_reps_min,
              target_reps_max: e.target_reps_max ?? null,
              rest_seconds: e.rest_seconds ?? 90,
            })),
          })),
        });
        pendentes.forEach((i) => saved.add(i));
        setSavedIndices(saved);
        setSaveSummary({ created: res.created, existing: already });
        if (res.skipped_exercises.length > 0) {
          setInfo({
            title: "Treino salvo",
            message: `${res.skipped_exercises.length} exercício(s) não existiam na base e ficaram de fora.`,
          });
        }
        return;
      }
      setSavedIndices(saved);
      setSaveSummary({ created: 0, existing: already });
    } catch (err: any) {
      setInfo({ title: "Não consegui salvar os treinos", message: err?.response?.data?.detail ?? "Tente novamente." });
    }
  }

  // --- Passo 3: plano gerado ------------------------------------------------
  if (result) {
    const p = result.plan;
    return (
      <ScrollView
        style={{ backgroundColor: colors.bg }}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      >
        <TouchableOpacity onPress={() => setResult(null)} style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}>
          <Ionicons name="chevron-back" size={20} color={colors.primary} />
          <Text style={[type.body, { color: colors.primary, fontWeight: "600" }]}>Escolher outro método</Text>
        </TouchableOpacity>

        <Text style={[type.h1, { color: colors.textPrimary }]}>{p.method_name}</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
          {p.author} · {p.days_per_week} dias/semana{p.phase_context ? ` · ${p.phase_context}` : ""}
        </Text>

        {result.recommended && result.recommended_reason ? (
          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 6,
              backgroundColor: colors.primary + "1A",
              borderRadius: 12,
              paddingVertical: 8,
              paddingHorizontal: 12,
              marginTop: spacing.md,
            }}
          >
            <Ionicons name="sparkles" size={15} color={colors.primary} />
            <Text style={[type.caption, { color: colors.textPrimary, flex: 1 }]}>{result.recommended_reason}</Text>
          </View>
        ) : null}

        {/* Selo de fidelidade — a promessa central do recurso */}
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            gap: 6,
            backgroundColor: result.is_faithful ? colors.success + "22" : colors.warning + "22",
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
              ? "Plano validado: segue as regras do método (frequência, proporção, ordem)."
              : "Atenção: algumas regras não puderam ser respeitadas — veja as notas."}
          </Text>
        </View>

        {/* Resumo do salvamento automático — o treino completo já foi pras
            rotinas do usuário (dedup por dia). */}
        {saveSummary ? (
          <View
            style={{
              flexDirection: "row",
              alignItems: "center",
              gap: 8,
              backgroundColor: colors.secondary + "1A",
              borderRadius: 12,
              paddingVertical: 10,
              paddingHorizontal: 12,
              marginTop: spacing.sm,
            }}
          >
            <Ionicons name="albums" size={16} color={colors.secondary} />
            <Text style={[type.caption, { color: colors.textPrimary, flex: 1 }]}>
              {saveSummary.created > 0
                ? `${saveSummary.created} ${saveSummary.created === 1 ? "treino adicionado" : "treinos adicionados"} às suas rotinas` +
                  (saveSummary.existing > 0 ? ` · ${saveSummary.existing} já ${saveSummary.existing === 1 ? "estava salvo" : "estavam salvos"}` : "")
                : "Todos os treinos deste método já estavam nas suas rotinas."}
            </Text>
          </View>
        ) : null}

        {result.intro ? (
          <Card style={{ marginTop: spacing.md }}>
            <Text style={[type.body, { color: colors.textPrimary }]}>{result.intro}</Text>
          </Card>
        ) : null}
        {result.ai_locked ? (
          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
            💡 O plano é fiel ao método. Assine o Pro para receber a explicação e as dicas da IA por exercício.
          </Text>
        ) : null}

        {p.notes.map((n, i) => (
          <Text key={i} style={[type.caption, { color: colors.warning, marginTop: spacing.sm }]}>
            ⚠️ {n}
          </Text>
        ))}

        {p.sessions.map((session, si) => (
          <Card key={si} style={{ marginTop: spacing.md }}>
            <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
              <View style={{ flex: 1 }}>
                <Text style={[type.h2, { color: colors.textPrimary, fontSize: 16 }]}>
                  {session.day_label} · {session.focus}
                </Text>
                {session.phase_name ? (
                  <Text style={[type.caption, { color: colors.textSecondary }]}>{session.phase_name}</Text>
                ) : null}
              </View>
              {savedIndices.has(si) ? (
                <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                  <Ionicons name="checkmark-circle" size={20} color={colors.success} />
                  <Text style={[type.caption, { color: colors.success, fontWeight: "700" }]}>na sua rotina</Text>
                </View>
              ) : null}
            </View>
            {session.slots.map((slot, i) => (
              <View
                key={i}
                style={{
                  paddingVertical: spacing.sm,
                  borderTopWidth: i === 0 ? 0 : 1,
                  borderTopColor: colors.border,
                }}
              >
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  <View
                    style={{
                      backgroundColor: slot.is_compound ? colors.moduleTraining + "33" : colors.secondary + "22",
                      borderRadius: 6,
                      paddingHorizontal: 6,
                      paddingVertical: 1,
                    }}
                  >
                    <Text style={[type.caption, { color: slot.is_compound ? colors.moduleTraining : colors.secondary, fontSize: 10, fontWeight: "700" }]}>
                      {slot.is_compound ? "COMPOSTO" : "ISOLADO"}
                    </Text>
                  </View>
                  <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600", flex: 1 }]}>
                    {slot.order}. {slot.exercise_name}
                  </Text>
                </View>
                <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
                  {slot.sets} × {slot.reps}
                  {slot.tempo ? ` · cadência ${slot.tempo}` : ""}
                  {slot.rest_seconds ? ` · descanso ${slot.rest_seconds}s` : ""}
                  {slot.rir ? ` · RIR ${slot.rir}` : ""}
                </Text>
                {slot.note ? (
                  <Text style={[type.caption, { color: colors.primary, marginTop: 2 }]}>💬 {slot.note}</Text>
                ) : null}
              </View>
            ))}
          </Card>
        ))}

        <Card style={{ marginTop: spacing.md }}>
          <Text style={[type.caption, { color: colors.textSecondary }]}>
            <Text style={{ fontWeight: "700", color: colors.textPrimary }}>Progressão: </Text>
            {p.progression_rule}
          </Text>
          {p.deload_rule ? (
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
              <Text style={{ fontWeight: "700", color: colors.textPrimary }}>Deload: </Text>
              {p.deload_rule}
            </Text>
          ) : null}
          {p.mesocycle ? (
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
              <Text style={{ fontWeight: "700", color: colors.textPrimary }}>Ciclo: </Text>
              {p.mesocycle}
            </Text>
          ) : null}
        </Card>
        <InfoDialog
          visible={info != null}
          onClose={() => setInfo(null)}
          title={info?.title ?? ""}
          message={info?.message}
        />
      </ScrollView>
    );
  }

  // --- Passo 2: escolher os dias -------------------------------------------
  if (selected) {
    return (
      <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg }}>
        <TouchableOpacity onPress={() => setSelected(null)} style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}>
          <Ionicons name="chevron-back" size={20} color={colors.primary} />
          <Text style={[type.body, { color: colors.primary, fontWeight: "600" }]}>Métodos</Text>
        </TouchableOpacity>

        <Text style={[type.h1, { color: colors.textPrimary }]}>{selected.name}</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
          {selected.author} · {EXP_LABEL[selected.experience_min] ?? selected.experience_min}
        </Text>
        <Card style={{ marginTop: spacing.md }}>
          <Text style={[type.body, { color: colors.textPrimary }]}>{selected.goal}</Text>
          {detail?.guide_excerpt ? (
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.sm, lineHeight: 20 }]}>
              {detail.guide_excerpt}
            </Text>
          ) : null}
        </Card>

        {/* Ficha do método. Antes a tela mostrava só a frase do goal e já
            pulava pro "quantos dias?" — quem escolhe entre 10 metodologias
            precisa saber o que cada uma cobra dele. */}
        {detail ? (
          <>
            <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
              Como funciona
            </Text>
            <Card>
              <SpecRow label="Frequência" value={detail.frequency_per_muscle} />
              <SpecRow label="Por sessão" value={detail.exercises_per_session} />
              <SpecRow label="Séries" value={detail.sets_per_exercise} />
              <SpecRow label="Repetições" value={detail.reps} />
              <SpecRow label="Cadência" value={detail.tempo} />
              <SpecRow label="Descanso" value={detail.rest_seconds} />
              <SpecRow label="Intensidade (RIR)" value={detail.rir} />
              <SpecRow label="Ciclo" value={detail.mesocycle_weeks} />
            </Card>

            {detail.progression_rule ? (
              <>
                <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
                  Como progredir
                </Text>
                <Card>
                  <Text style={[type.bodySmall, { color: colors.textPrimary, lineHeight: 20 }]}>
                    {detail.progression_rule}
                  </Text>
                  {detail.deload_rule ? (
                    <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.sm, lineHeight: 20 }]}>
                      Deload: {detail.deload_rule}
                    </Text>
                  ) : null}
                </Card>
              </>
            ) : null}

            {detail.phases.length > 0 ? (
              <>
                <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
                  Fases
                </Text>
                {detail.phases.map((p, i) => (
                  <Card key={i} style={{ marginBottom: spacing.sm }}>
                    <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>{p.name}</Text>
                    {p.sets || p.reps ? (
                      <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]}>
                        {[p.sets, p.reps].filter(Boolean).join(" · ")}
                      </Text>
                    ) : null}
                    {p.note ? (
                      <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 19 }]}>
                        {p.note}
                      </Text>
                    ) : null}
                  </Card>
                ))}
              </>
            ) : null}

            {detail.forbidden.length > 0 ? (
              <>
                <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
                  O que não fazer
                </Text>
                <Card>
                  {detail.forbidden.map((f, i) => (
                    <View key={i} style={{ flexDirection: "row", marginBottom: i === detail.forbidden.length - 1 ? 0 : spacing.xs }}>
                      <Ionicons name="close-circle" size={15} color={colors.warning} style={{ marginTop: 2, marginRight: 6 }} />
                      <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1, lineHeight: 19 }]}>{f}</Text>
                    </View>
                  ))}
                </Card>
              </>
            ) : null}

            {/* Ponto fraco: só nos métodos desenhados pra isso. Perguntar num
                método que ignora a resposta seria enganar a pessoa. */}
            {detail.targets_weak_point ? (
              <>
                <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: 2 }]}>
                  Algum ponto fraco?
                </Text>
                <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm }]}>
                  Este método monta os acessórios em volta do seu ponto fraco. O músculo escolhido vem
                  logo depois dos exercícios pesados, quando você ainda está descansado.
                </Text>
                <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs }}>
                  {WEAK_POINT_OPTIONS.map((o) => {
                    const on = weakPoint === o.value;
                    return (
                      <TouchableOpacity
                        key={o.value ?? "nenhum"}
                        onPress={() => setWeakPoint(o.value)}
                        style={{
                          backgroundColor: on ? colors.primary : colors.surface,
                          borderWidth: 1,
                          borderColor: on ? colors.primary : colors.border,
                          borderRadius: 999,
                          paddingVertical: 8,
                          paddingHorizontal: 14,
                        }}
                      >
                        <Text
                          style={[
                            type.caption,
                            { color: on ? colors.textOnPrimary : colors.textPrimary, fontWeight: on ? "700" : "400" },
                          ]}
                        >
                          {o.label}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </>
            ) : null}
          </>
        ) : (
          <ActivityIndicator color={colors.textSecondary} style={{ marginTop: spacing.lg }} />
        )}

        <Text style={[type.h2, { color: colors.textPrimary, marginTop: spacing.lg, marginBottom: spacing.sm }]}>
          Quantos dias por semana você treina?
        </Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm }}>
          {selected.days_per_week.map((d) => (
            <TouchableOpacity
              key={d}
              onPress={() => {
                setDays(d);
                handleGenerate(selected, d);
              }}
              style={{
                backgroundColor: colors.surface,
                borderWidth: 1,
                borderColor: colors.border,
                borderRadius: 14,
                paddingVertical: spacing.md,
                paddingHorizontal: spacing.lg,
              }}
            >
              <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>{d} dias</Text>
            </TouchableOpacity>
          ))}
        </View>
        {loading ? <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.xl }} size="large" /> : null}
        <InfoDialog
          visible={info != null}
          onClose={() => setInfo(null)}
          title={info?.title ?? ""}
          message={info?.message}
        />
      </ScrollView>
    );
  }

  // --- Passo 1: catálogo de métodos ----------------------------------------
  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
    >
      <Text style={[type.h1, { color: colors.textPrimary }]}>Monte seu treino</Text>
      <Text style={[type.body, { color: colors.textSecondary, marginTop: 4 }]}>
        A IA monta um treino do zero pra você (Pro), ou escolha um dos 10 métodos consagrados — fiel ao
        método (frequência, volume, proporção e ordem).
      </Text>

      {/* Criar treino com IA (conversa): a IA pergunta rotina/objetivo e monta.
          Pro-only — quem é Free vê o card mas cai no paywall ao tocar. */}
      <TouchableOpacity activeOpacity={0.85} onPress={handleCreateWithAi}>
        <View
          style={{
            flexDirection: "row",
            alignItems: "center",
            backgroundColor: colors.primary,
            borderRadius: radius.card,
            padding: spacing.md,
            marginTop: spacing.md,
          }}
        >
          <View
            style={{
              width: 46,
              height: 46,
              borderRadius: 15,
              backgroundColor: "rgba(255,255,255,0.22)",
              alignItems: "center",
              justifyContent: "center",
              marginRight: spacing.md,
            }}
          >
            <Ionicons name="sparkles" size={24} color="#FFFFFF" />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[type.h2, { color: "#FFFFFF", fontSize: 16 }]}>Criar treino com IA</Text>
            <Text style={[type.caption, { color: "rgba(255,255,255,0.9)" }]} numberOfLines={2}>
              A IA pergunta seu objetivo, dias e preferências e monta pra você{isPro ? "" : " · Pro"}
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={20} color="#FFFFFF" />
        </View>
      </TouchableOpacity>

      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.lg, fontWeight: "700" }]}>
        OU ESCOLHA UM MÉTODO PRONTO
      </Text>

      {methods.map((m) => (
        <TouchableOpacity key={m.key} activeOpacity={0.8} onPress={() => openMethod(m)}>
          <Card style={{ marginTop: spacing.md }}>
            <View style={{ flexDirection: "row", alignItems: "center" }}>
              <View style={{ flex: 1 }}>
                <Text style={[type.h2, { color: colors.textPrimary, fontSize: 17 }]}>{m.name}</Text>
                <Text style={[type.caption, { color: colors.textSecondary }]}>
                  {m.author} · {EXP_LABEL[m.experience_min] ?? m.experience_min} · {m.days_per_week.join("/")} dias
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={20} color={colors.textSecondary} />
            </View>
            {/* Explicação curta na lista; a ficha completa vem ao abrir. */}
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.sm, lineHeight: 19 }]}>
              {m.goal}
            </Text>
            <Text style={[type.caption, { color: colors.primary, marginTop: spacing.xs, fontWeight: "600" }]}>
              Ver como funciona
            </Text>
          </Card>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}
