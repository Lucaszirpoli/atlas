import { Ionicons } from "@expo/vector-icons";
import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Alert, ScrollView, Text, TouchableOpacity, View } from "react-native";

import {
  listWorkoutOverlays,
  removeTechniqueCue,
  revertCoachAction,
  type WorkoutOverlay,
} from "../../api/coaching";
import { CoachOverlayBlock, DeloadBanner } from "../../components/CoachOverlay";
import {
  getRoutine,
  swapRoutineExercise,
  type Routine,
  type RoutineExercise,
} from "../../api/routines";
import {
  getWorkoutPreview,
  startWorkoutSession,
  type ExercisePrefill,
} from "../../api/workoutSessions";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ExerciseThumb } from "../../components/ExerciseThumb";
import { HelpDot } from "../../components/HelpDot";
import { InfoDialog } from "../../components/InfoDialog";
import { useActiveWorkout } from "../../context/ActiveWorkoutContext";
import { useTheme } from "../../theme/ThemeProvider";
import { fmtKg } from "../../utils/format";
import { mensagemDeErro } from "../../utils/errorMessage";

const SET_TYPES_HELP_TEXT =
  "Aquecimento: a primeira série, bem leve (25% da carga de trabalho), só pra preparar a articulação e o músculo — não é série de esforço.\n\n" +
  "Feeder: a segunda série, um pouco mais pesada (50% da carga de trabalho), pra chegar afiado na primeira série de trabalho — também não conta como esforço.\n\n" +
  "Série de trabalho: as séries que valem, com o peso e reps que você realmente treina.\n\n" +
  "Até a falha: a última série de trabalho, levada até não dar mais pra fazer outra rep com boa forma (RIR 0).";

/** Prévia do treino: mostra os exercícios, séries e os pesos/reps da última vez
 * — igual à tela de execução, mas SEM iniciar a sessão. A pessoa vê o que vai
 * pegar e decide começar (aí sim inicia de verdade). */
export function WorkoutPreviewScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { startWorkout } = useActiveWorkout();
  const { routineId } = route.params as { routineId: number };

  const [routine, setRoutine] = useState<Routine | null>(null);
  const [prefill, setPrefill] = useState<ExercisePrefill[]>([]);
  const [overlays, setOverlays] = useState<WorkoutOverlay[]>([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  // Troca de exercício: qual vaga a pessoa pediu pra trocar (aviso aberto),
  // qual está trocando agora (spinner no lugar do botão), e o que o coach
  // respondeu depois de trocar.
  const [trocando, setTrocando] = useState<RoutineExercise | null>(null);
  const [emTroca, setEmTroca] = useState<number | null>(null);
  const [resultadoTroca, setResultadoTroca] = useState<{ titulo: string; texto: string } | null>(null);

  useEffect(() => {
    Promise.all([getRoutine(routineId), getWorkoutPreview(routineId)])
      .then(([r, p]) => {
        setRoutine(r);
        setPrefill(p);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    // Overlays do coach (técnica / subir carga / troca / deload) — silencioso se falhar.
    listWorkoutOverlays()
      .then(setOverlays)
      .catch(() => {});
  }, [routineId]);

  const deload = overlays.find((o) => o.kind === "deload");
  function overlaysFor(exerciseId: number): WorkoutOverlay[] {
    return overlays.filter((o) => o.exercise_id === exerciseId);
  }

  async function removerOverlay(o: WorkoutOverlay) {
    setOverlays((os) => os.filter((x) => !(x.source === o.source && x.id === o.id))); // otimista
    try {
      if (o.source === "technique") await removeTechniqueCue(o.id);
      else await revertCoachAction(o.id);
    } catch {
      listWorkoutOverlays().then(setOverlays).catch(() => {});
    }
  }

  async function handleStart() {
    if (!routine) return;
    setStarting(true);
    try {
      const { session, prefill: pf } = await startWorkoutSession(routine.id);
      startWorkout({
        sessionId: session.id,
        routineId: routine.id,
        routineName: routine.name,
        prefill: pf,
        startedAt: new Date(session.started_at).getTime(),
      });
      navigation.replace("WorkoutExecution", { sessionId: session.id, routineId: routine.id, prefill: pf });
    } catch (err: any) {
      Alert.alert("Não foi possível iniciar", mensagemDeErro(err, "Tente novamente."));
      setStarting(false);
    }
  }

  function prefillFor(exerciseId: number): ExercisePrefill | undefined {
    return prefill.find((p) => p.exercise_id === exerciseId);
  }

  /** Pede a troca ao coach. O app não escolhe o substituto — só diz qual vaga
   * a pessoa não quer; quem decide é o servidor, pelas regras da montagem. */
  async function confirmarTroca(alvo: RoutineExercise) {
    setEmTroca(alvo.id);
    try {
      const r = await swapRoutineExercise(routineId, alvo.id);
      setRoutine(r.routine);
      // Os pesos pré-preenchidos são POR EXERCÍCIO: o que entrou tem histórico
      // próprio (ou nenhum). Recarregar é o que evita a prévia mostrar a carga
      // do exercício que acabou de sair ao lado do nome do que entrou.
      getWorkoutPreview(routineId).then(setPrefill).catch(() => {});
      setResultadoTroca({ titulo: `Entrou ${r.exercicio_novo}`, texto: r.motivo });
    } catch (err: any) {
      setResultadoTroca({
        titulo: "Não deu pra trocar",
        texto: mensagemDeErro(err, "Tente de novo daqui a pouco."),
      });
    } finally {
      setEmTroca(null);
    }
  }

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  if (!routine) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center", padding: spacing.lg }}>
        <Text style={[type.body, { color: colors.textSecondary }]}>Não consegui carregar o treino.</Text>
      </View>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}>
        <Text style={[type.h1, { color: colors.textPrimary }]}>{routine.name}</Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, marginBottom: spacing.md }]}>
          Prévia · os pesos são os da sua última vez. O treino ainda não começou.
        </Text>

        {deload ? <DeloadBanner overlay={deload} onRemove={removerOverlay} /> : null}

        {routine.exercises.map((ex) => {
          const pf = prefillFor(ex.exercise_id);
          const reps =
            ex.target_reps_max != null ? `${ex.target_reps_min}-${ex.target_reps_max}` : `${ex.target_reps_min}`;
          return (
            <Card key={ex.id} style={{ marginBottom: spacing.md }}>
              <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
                <ExerciseThumb url={ex.exercise.video_url} size={44} />
                <View style={{ flex: 1, marginLeft: spacing.sm }}>
                  <View style={{ flexDirection: "row", alignItems: "center" }}>
                    {/* flex:1 no nome: sem isso, um nome de exercício comprido
                        empurrava o "?" pra fora da coluna (que é flex:1 lá em
                        cima) e ele ficava sobreposto/cortado atrás da setinha
                        de trocar exercício, ao lado. */}
                    <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700", flex: 1 }]}>{ex.exercise.name}</Text>
                    <HelpDot title="Tipos de série" text={SET_TYPES_HELP_TEXT} />
                  </View>
                  <Text style={[type.caption, { color: colors.textSecondary }]}>
                    {ex.target_sets} séries × {reps} reps · descanso {ex.rest_seconds}s
                  </Text>
                </View>

                {/* TROCAR EXERCÍCIO. A mesma setinha existe na tela de execução
                    (a máquina só está ocupada quando você chega nela) — lá ela
                    some assim que a primeira série da vaga é registrada, porque
                    a série já ficou gravada no exercício antigo. */}
                {emTroca === ex.id ? (
                  <View style={{ width: 38, height: 38, alignItems: "center", justifyContent: "center" }}>
                    <ActivityIndicator color={colors.primary} />
                  </View>
                ) : (
                  <TouchableOpacity
                    onPress={() => setTrocando(ex)}
                    disabled={emTroca !== null}
                    activeOpacity={0.7}
                    accessibilityRole="button"
                    accessibilityLabel={`Trocar ${ex.exercise.name} por outro exercício`}
                    // Área de toque generosa num alvo pequeno — o botão é
                    // discreto de propósito (trocar é a exceção, não o caminho),
                    // mas errar o toque num treino não pode ser fácil.
                    hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                    style={{
                      width: 38,
                      height: 38,
                      borderRadius: radius.pill,
                      alignItems: "center",
                      justifyContent: "center",
                      backgroundColor: colors.surfaceAlt,
                      opacity: emTroca !== null ? 0.4 : 1,
                    }}
                  >
                    <Ionicons name="swap-horizontal-outline" size={19} color={colors.textSecondary} />
                  </TouchableOpacity>
                )}
              </View>

              {/* Rampa de preparação (aquecimento + feeder), calculada da carga
                  real de trabalho — não conta como série de trabalho, só
                  aparece quando já existe histórico pra basear o peso. */}
              {(pf?.warmup_feeder ?? []).map((w, wi) => (
                <View
                  key={`prep-${wi}`}
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    justifyContent: "space-between",
                    paddingVertical: 6,
                    borderTopWidth: wi === 0 ? 0 : 1,
                    borderTopColor: colors.border,
                  }}
                >
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                    <Text style={[type.caption, { color: colors.textSecondary }]}>
                      {w.reps_min}-{w.reps_max} reps
                    </Text>
                    <View style={{ backgroundColor: colors.textSecondary + "22", borderRadius: radius.pill, paddingVertical: 2, paddingHorizontal: 8 }}>
                      <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700", fontSize: 10 }]}>{w.label}</Text>
                    </View>
                  </View>
                  <Text style={[type.body, { color: colors.textSecondary, fontWeight: "600" }]}>
                    {fmtKg(w.weight_kg)} kg
                  </Text>
                </View>
              ))}

              {/* Linhas das séries de trabalho com o peso/reps da última vez
                  (read-only) — toda série diz o que é: até a falha (RIR 0) ou
                  série de trabalho normal, com o RIR sugerido pro momento do
                  ciclo. */}
              {Array.from({ length: ex.target_sets }).map((_, i) => {
                const last = pf?.sets?.[i];
                const intent = ex.set_intents?.[i];
                // RIR 0 É até a falha — mesma regra da tela de execução, senão a
                // prévia prometeria "série de trabalho · RIR 0" e o treino
                // abriria com F.
                const isFailure = intent === "to_failure" || (pf?.suggested_rir ?? 2) === 0;
                const intentLabel = isFailure ? "Até a falha · RIR 0" : `Série de trabalho · RIR ${pf?.suggested_rir ?? 2}`;
                const intentColor = isFailure ? colors.danger : colors.textSecondary;
                return (
                  <View
                    key={i}
                    style={{
                      flexDirection: "row",
                      alignItems: "center",
                      justifyContent: "space-between",
                      paddingVertical: 6,
                      borderTopWidth: i === 0 && !(pf?.warmup_feeder ?? []).length ? 0 : 1,
                      borderTopColor: colors.border,
                    }}
                  >
                    <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                      <Text style={[type.caption, { color: colors.textSecondary }]}>Série {i + 1}</Text>
                      <View style={{ backgroundColor: intentColor + "22", borderRadius: radius.pill, paddingVertical: 2, paddingHorizontal: 8 }}>
                        <Text style={[type.caption, { color: intentColor, fontWeight: "700", fontSize: 10 }]}>{intentLabel}</Text>
                      </View>
                    </View>
                    <Text style={[type.body, { color: colors.textPrimary, fontWeight: "600" }]}>
                      {last ? `${fmtKg(last.weight_kg)} kg × ${last.reps}` : "—"}
                    </Text>
                  </View>
                );
              })}
              {!pf?.sets?.length ? (
                <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4 }]}>
                  Primeira vez neste exercício — os pesos ficam prontos quando você treinar.
                </Text>
              ) : null}

              {/* Overlays do coach neste exercício (técnica / subir carga /
                  troca). O "remover" é o desfazer, aqui onde eles vivem. */}
              {overlaysFor(ex.exercise_id).map((o) => (
                <CoachOverlayBlock key={`${o.source}:${o.id}`} overlay={o} onRemove={removerOverlay} />
              ))}
            </Card>
          );
        })}
      </ScrollView>

      <View
        style={{
          padding: spacing.lg,
          paddingTop: spacing.md,
          borderTopWidth: 1,
          borderTopColor: colors.border,
          backgroundColor: colors.bg,
        }}
      >
        <Button title="Treinar agora" onPress={handleStart} loading={starting} />
      </View>

      <ConfirmDialog
        visible={trocando !== null}
        onClose={() => setTrocando(null)}
        title="Trocar este exercício?"
        message={
          trocando
            ? `Quem escolhe o substituto de ${trocando.exercise.name} é o coach — vem outro exercício ` +
              "para o mesmo músculo, com o mesmo papel no treino e respeitando suas preferências. " +
              "Suas séries e reps continuam iguais, e o volume da semana não muda."
            : undefined
        }
        confirmLabel="Trocar"
        onConfirm={() => {
          if (trocando) confirmarTroca(trocando);
        }}
      />

      <InfoDialog
        visible={resultadoTroca !== null}
        onClose={() => setResultadoTroca(null)}
        title={resultadoTroca?.titulo ?? ""}
        message={resultadoTroca?.texto}
      />
    </View>
  );
}
