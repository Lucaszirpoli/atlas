import { Ionicons } from "@expo/vector-icons";
import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Modal, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import {
  activateObjectivePlan,
  applyPersonalDiet,
  COMPONENT_LABEL,
  discardObjectiveDraft,
  formatAnswer,
  getObjectiveState,
  getPersonalDiet,
  getQuestionnaire,
  saveObjectiveDraft,
  type Answers,
  type ObjectiveState,
  type PendingChange,
  type PersonalDiet,
  type PlanSummary,
  type QuestionField,
  type Questionnaire,
} from "../../api/objective";
import { getCurrentGoal, type CalorieGoal } from "../../api/goals";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { HelpDot } from "../../components/HelpDot";
import { InfoDialog } from "../../components/InfoDialog";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";
import { exportDietAsPdf } from "../../utils/pdfExport";

/**
 * ABA OBJETIVO (Premium) — o centro visual e informacional do Coaching.
 *
 * Deixa de ser "uma área simples de meta" (spec §3) e passa a concentrar:
 * apresentação e questionário no primeiro acesso, painel-resumo depois,
 * consulta e edição das respostas, alterações pendentes, atualização do plano
 * e histórico das versões.
 *
 * O fluxo é decidido por um estado só, vindo do backend:
 *   sem plano                -> apresentação -> questionário (6 etapas)
 *   com plano                -> painel-resumo
 *   com plano + pendências   -> painel-resumo + aviso de alterações pendentes
 */

type Modo = "resumo" | "questionario" | "atualizado";

export function ObjectiveScreen({
  onScrollTop,
  onPlanActivated,
}: {
  /** Avisa a tela do Coaching que o plano mudou, pra ela recarregar a análise.
   * Sem isto, logo depois de "Seu plano foi atualizado" o card do coach acima
   * continuava mostrando o objetivo ANTIGO — duas versões da verdade na mesma
   * tela, que é justamente o que a ativação atômica existe pra evitar. */
  onPlanActivated?: () => void;
  /** Sobe a rolagem ao trocar de etapa. Quem rola é a tela do Coaching (esta
   * vive dentro do ScrollView dela) — dois ScrollViews aninhados brigariam. */
  onScrollTop?: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();

  const [quest, setQuest] = useState<Questionnaire | null>(null);
  const [state, setState] = useState<ObjectiveState | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  const [modo, setModo] = useState<Modo>("resumo");
  const [etapa, setEtapa] = useState(0);
  const [respostas, setRespostas] = useState<Answers>({});
  const [gerando, setGerando] = useState(false);
  const [confirmarDescarte, setConfirmarDescarte] = useState(false);
  const [verRespostas, setVerRespostas] = useState(false);
  const [verHistorico, setVerHistorico] = useState(false);
  const [verMetas, setVerMetas] = useState(false);
  const [metaAtual, setMetaAtual] = useState<CalorieGoal | null>(null);
  const [planoNovo, setPlanoNovo] = useState<PlanSummary | null>(null);

  // "Ver dieta em PDF" — modal interno (não uma tela navegada): a dieta que o
  // Coaching montou pra ESSA pessoa (meta + restrições do questionário), nunca
  // as dietas prontas genéricas (essas ficam só na aba Dieta).
  const [dietaAberta, setDietaAberta] = useState(false);
  const [dieta, setDieta] = useState<PersonalDiet | null>(null);
  const [carregandoDieta, setCarregandoDieta] = useState(false);
  const [erroDieta, setErroDieta] = useState<string | null>(null);
  const [baixandoDieta, setBaixandoDieta] = useState(false);
  const [aplicandoDieta, setAplicandoDieta] = useState(false);
  const [confirmarUsarDieta, setConfirmarUsarDieta] = useState(false);
  const [sucessoDieta, setSucessoDieta] = useState<string | null>(null);

  async function abrirDietaPdf() {
    setDietaAberta(true);
    setErroDieta(null);
    setCarregandoDieta(true);
    try {
      setDieta(await getPersonalDiet());
    } catch (e: any) {
      setErroDieta(mensagemDeErro(e, "Não consegui montar sua dieta agora."));
    } finally {
      setCarregandoDieta(false);
    }
  }

  async function baixarDietaPdf() {
    if (!dieta || baixandoDieta) return;
    setBaixandoDieta(true);
    try {
      await exportDietAsPdf({
        name: dieta.name,
        tagline: dieta.tagline,
        meals: dieta.meals.map((m) => ({
          category: m.category,
          items: m.items.map((i) => ({ food_name: i.food_name, quantity_g: i.quantity_g, kcal: i.kcal })),
        })),
        totals: dieta.totals,
      });
    } finally {
      setBaixandoDieta(false);
    }
  }

  async function usarDietaHoje() {
    setConfirmarUsarDieta(false);
    setAplicandoDieta(true);
    try {
      const r = await applyPersonalDiet();
      setSucessoDieta(
        `Registrei sua dieta no diário de hoje — ${r.items_logged} alimentos, ${r.totals.kcal} kcal. ` +
          "Você pode ajustar ou remover qualquer item na aba Dieta."
      );
    } catch (e: any) {
      setErroDieta(mensagemDeErro(e, "Não consegui registrar agora."));
    } finally {
      setAplicandoDieta(false);
    }
  }

  const carregar = useCallback(async () => {
    setErro(null);
    try {
      const [q, s] = await Promise.all([getQuestionnaire(), getObjectiveState()]);
      setQuest(q);
      setState(s);
      setRespostas(s.draft_answers ?? {});
      setEtapa(Math.min(s.draft_step ?? 0, Math.max(q.steps.length - 1, 0)));
      if (s.has_plan) getCurrentGoal().then(setMetaAtual).catch(() => {});
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui carregar seu objetivo agora."));
    } finally {
      setCarregando(false);
    }
  }, []);

  useEffect(() => {
    carregar();
  }, [carregar]);

  // Progresso temporário: salva ao avançar, voltar ou sair. Sem isto, fechar o
  // app no meio das 6 etapas custava tudo que já tinha sido respondido.
  const salvarProgresso = useCallback(
    async (ans: Answers, step: number) => {
      try {
        const novo = await saveObjectiveDraft(ans, step);
        setState(novo);
      } catch {
        // Sem rede: o que está na tela continua ali, e a próxima navegação
        // entre etapas tenta salvar de novo.
      }
    },
    []
  );

  function setCampo(key: string, valor: any) {
    setRespostas((r) => ({ ...r, [key]: valor }));
  }

  const passos = quest?.steps ?? [];
  const passoAtual = passos[etapa];

  /** Campo condicional (ex.: meta manual só aparece com calorie_goal_mode =
   * "manual"). Sem shows_if, o campo sempre vale. */
  function visivel(f: QuestionField, respostasAtuais: Answers): boolean {
    if (!f.shows_if) return true;
    return String(respostasAtuais[f.shows_if.field] ?? "") === f.shows_if.equals;
  }

  /** Obrigatórios em branco NESTA etapa — bloqueiam o avanço (spec §3.1). */
  function faltandoNaEtapa(): string[] {
    if (!passoAtual) return [];
    return passoAtual.fields
      .filter((f) => f.required && visivel(f, respostas))
      .filter((f) => {
        const v = respostas[f.key];
        return v === null || v === undefined || v === "" || (Array.isArray(v) && v.length === 0);
      })
      .map((f) => f.label);
  }

  /** Meta manual (calorie_goal_mode = "manual"): proteína + carbo + gordura
   * precisa fechar 100% (spec §9.2) — mesma regra que a antiga tela de meta. */
  function macroSplitErro(): string | null {
    if (respostas.calorie_goal_mode !== "manual") return null;
    const soma =
      (Number(respostas.manual_pct_protein) || 0) +
      (Number(respostas.manual_pct_carbs) || 0) +
      (Number(respostas.manual_pct_fat) || 0);
    const arred = Math.round(soma * 10) / 10;
    if (arred === 100) return null;
    return arred > 100 ? `Somando ${arred}% — excede em ${(arred - 100).toFixed(1)}%.` : `Somando ${arred}% — faltam ${(100 - arred).toFixed(1)}%.`;
  }

  async function avancar() {
    if (faltandoNaEtapa().length > 0) return;
    const proxima = Math.min(etapa + 1, passos.length - 1);
    setEtapa(proxima);
    onScrollTop?.();
    salvarProgresso(respostas, proxima);
  }

  function voltar() {
    const anterior = Math.max(etapa - 1, 0);
    setEtapa(anterior);
    onScrollTop?.();
    salvarProgresso(respostas, anterior);
  }

  async function finalizar() {
    setGerando(true);
    setErro(null);
    try {
      await saveObjectiveDraft(respostas, etapa);
      const novo = await activateObjectivePlan();
      setState(novo);
      setPlanoNovo(novo.active_plan);
      setModo("atualizado");
      onPlanActivated?.();
      onScrollTop?.();
      getCurrentGoal().then(setMetaAtual).catch(() => {});
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui gerar seu plano agora. Seu plano atual continua valendo."));
    } finally {
      setGerando(false);
    }
  }

  /** Sair do questionário SALVA o que foi mexido (spec §3.1: o progresso é
   * guardado ao avançar, voltar, minimizar ou fechar). Sem isto a pessoa
   * editava, tocava em "Sair" e a alteração sumia em silêncio — que é o
   * oposto do que a tela promete. O que foi editado vira pendência, não
   * substitui nada até ela confirmar. */
  async function sairDoQuestionario() {
    await salvarProgresso(respostas, etapa);
    setModo("resumo");
    onScrollTop?.();
  }

  async function descartar() {
    setConfirmarDescarte(false);
    try {
      const novo = await discardObjectiveDraft();
      setState(novo);
      setRespostas(novo.draft_answers ?? {});
      setModo("resumo");
    } catch (e: any) {
      setErro(mensagemDeErro(e, "Não consegui descartar agora."));
    }
  }

  function campoPorChave(key: string): QuestionField | undefined {
    return passos.flatMap((s) => s.fields).find((f) => f.key === key);
  }

  if (carregando) {
    return (
      <Card style={{ alignItems: "center", paddingVertical: spacing.xl }}>
        <ActivityIndicator color={colors.primary} />
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm }]}>
          Abrindo seu objetivo...
        </Text>
      </Card>
    );
  }

  if (!state || !quest) {
    return (
      <Card>
        <Text style={[type.body, { color: colors.textPrimary }]}>
          {erro ?? "Não consegui carregar seu objetivo agora."}
        </Text>
        <View style={{ marginTop: spacing.md }}>
          <Button title="Tentar de novo" variant="secondary" compact onPress={carregar} />
        </View>
      </Card>
    );
  }

  // ---------------------------------------------------------------------
  // 1) PRIMEIRO ACESSO — apresentação do questionário obrigatório (§3.1)
  // ---------------------------------------------------------------------
  if (!state.has_plan && modo !== "questionario") {
    return (
      <View>
        <Card accent={colors.primary}>
          <View
            style={{
              width: 52, height: 52, borderRadius: 17,
              backgroundColor: colors.primary + "1F",
              alignItems: "center", justifyContent: "center", marginBottom: spacing.md,
            }}
          >
            <Ionicons name="compass-outline" size={26} color={colors.primary} />
          </View>
          <Text style={[type.h1, { color: colors.textPrimary, fontSize: 24 }]}>
            Vamos montar sua estratégia
          </Text>
          <Text style={[type.body, { color: colors.textSecondary, marginTop: spacing.sm, lineHeight: 23 }]}>
            Responda algumas perguntas para que o Coaching possa trabalhar com seu treino, suas metas
            nutricionais, sua dieta em PDF, sua periodização e suas análises.
          </Text>

          <View style={{ marginTop: spacing.lg, gap: spacing.sm }}>
            {quest.steps.map((s, i) => (
              <View key={s.key} style={{ flexDirection: "row", alignItems: "center", gap: 10 }}>
                <View
                  style={{
                    width: 24, height: 24, borderRadius: 12,
                    backgroundColor: colors.surfaceAlt,
                    alignItems: "center", justifyContent: "center",
                  }}
                >
                  <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "800", fontSize: 11 }]}>
                    {i + 1}
                  </Text>
                </View>
                <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1 }]}>{s.title}</Text>
              </View>
            ))}
          </View>

          <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.lg, lineHeight: 17 }]}>
            Leva uns 3 minutos. Dá pra sair no meio — eu guardo o que você já respondeu e você volta de onde
            parou.
          </Text>
          <View style={{ marginTop: spacing.md }}>
            <Button title="Começar questionário" onPress={() => setModo("questionario")} />
          </View>
        </Card>
      </View>
    );
  }

  // ---------------------------------------------------------------------
  // 2) QUESTIONÁRIO — 6 etapas, com progresso e rascunho salvo (§3.1/§3.2)
  // ---------------------------------------------------------------------
  if (modo === "questionario" && passoAtual) {
    const ultima = etapa === passos.length - 1;
    const faltando = faltandoNaEtapa();
    const erroMacros = macroSplitErro();
    return (
      <View>
        {/* Indicador de progresso */}
        <View style={{ marginBottom: spacing.md }}>
          <View style={{ flexDirection: "row", alignItems: "center", marginBottom: 6 }}>
            <Text style={[type.caption, { color: colors.primary, fontWeight: "800", flex: 1 }]}>
              Etapa {etapa + 1} de {passos.length}
            </Text>
            {state.has_plan ? (
              <TouchableOpacity onPress={sairDoQuestionario} hitSlop={8}>
                <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700" }]}>Sair</Text>
              </TouchableOpacity>
            ) : null}
          </View>
          <View style={{ height: 6, borderRadius: 3, backgroundColor: colors.surfaceAlt, overflow: "hidden" }}>
            <View
              style={{
                width: `${((etapa + 1) / passos.length) * 100}%`,
                height: "100%",
                backgroundColor: colors.primary,
              }}
            />
          </View>
        </View>

        <Text style={[type.h1, { color: colors.textPrimary, fontSize: 22 }]}>{passoAtual.title}</Text>
        <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 4, marginBottom: spacing.md, lineHeight: 20 }]}>
          {passoAtual.subtitle}
        </Text>

        {passoAtual.fields
          .filter((f) => visivel(f, respostas))
          .map((f) => (
            <FieldEditor key={f.key} field={f} value={respostas[f.key]} onChange={(v) => setCampo(f.key, v)} />
          ))}

        {/* Meta manual: soma de macros em tempo real — mesma regra da antiga
            tela de meta (§9.2), agora só aqui no questionário. */}
        {respostas.calorie_goal_mode === "manual" ? (
          <View
            style={{
              flexDirection: "row", alignItems: "flex-start", gap: 7,
              backgroundColor: erroMacros ? colors.warning + "14" : colors.success + "14",
              borderRadius: radius.card, padding: spacing.sm, marginBottom: spacing.md,
            }}
          >
            <Ionicons
              name={erroMacros ? "alert-circle" : "checkmark-circle"}
              size={15}
              color={erroMacros ? colors.warning : colors.success}
              style={{ marginTop: 1 }}
            />
            <Text style={[type.caption, { color: colors.textSecondary, flex: 1, lineHeight: 17 }]}>
              {erroMacros ?? "100% — divisão de macros válida."}
            </Text>
          </View>
        ) : null}

        {faltando.length > 0 ? (
          <View
            style={{
              flexDirection: "row", alignItems: "flex-start", gap: 7,
              backgroundColor: colors.warning + "14", borderRadius: radius.card,
              padding: spacing.sm, marginTop: spacing.sm,
            }}
          >
            <Ionicons name="alert-circle" size={15} color={colors.warning} style={{ marginTop: 1 }} />
            <Text style={[type.caption, { color: colors.textSecondary, flex: 1, lineHeight: 17 }]}>
              Falta preencher: {faltando.join(", ")}.
            </Text>
          </View>
        ) : null}

        {erro ? (
          <Text style={[type.bodySmall, { color: colors.warning, marginTop: spacing.sm, textAlign: "center" }]}>
            {erro}
          </Text>
        ) : null}

        <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg, marginBottom: spacing.xl }}>
          {etapa > 0 ? (
            <View style={{ flex: 1 }}>
              <Button title="Voltar" variant="ghost" onPress={voltar} disabled={gerando} />
            </View>
          ) : null}
          <View style={{ flex: 2 }}>
            <Button
              title={ultima ? "Finalizar e gerar meu plano" : "Continuar"}
              onPress={ultima ? finalizar : avancar}
              loading={gerando}
              disabled={faltando.length > 0 || !!erroMacros}
            />
          </View>
        </View>
      </View>
    );
  }

  // ---------------------------------------------------------------------
  // 3) TELA APÓS ATUALIZAÇÃO (§3.6)
  // ---------------------------------------------------------------------
  if (modo === "atualizado" && planoNovo) {
    return (
      <View>
        <Card accent={colors.success}>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 10, marginBottom: spacing.sm }}>
            <Ionicons name="checkmark-circle" size={26} color={colors.success} />
            <Text style={[type.h1, { color: colors.textPrimary, fontSize: 22, flex: 1 }]}>
              {planoNovo.version === 1 ? "Seu plano está pronto" : "Seu plano foi atualizado"}
            </Text>
          </View>
          <View
            style={{
              alignSelf: "flex-start", backgroundColor: colors.surfaceAlt,
              borderRadius: radius.pill, paddingVertical: 4, paddingHorizontal: 10, marginBottom: spacing.md,
            }}
          >
            <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "800" }]}>
              versão {planoNovo.version}
            </Text>
          </View>

          <PlanComponents plan={planoNovo} />

          {planoNovo.changes.length > 0 ? (
            <View style={{ marginTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.md }}>
              <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: spacing.xs }]}>
                O que mudou
              </Text>
              {planoNovo.changes.map((c) => (
                <ChangeRow key={c.field} change={c} field={campoPorChave(c.field)} />
              ))}
            </View>
          ) : null}
        </Card>

        <View style={{ gap: spacing.sm, marginTop: spacing.md, marginBottom: spacing.xl }}>
          <Button
            title="Ver novas metas"
            onPress={() => {
              setModo("resumo");
              setVerMetas(true);
              getCurrentGoal().then(setMetaAtual).catch(() => {});
            }}
          />
          <Button title="Ver dieta em PDF" variant="secondary" onPress={abrirDietaPdf} />
          <TouchableOpacity onPress={() => setModo("resumo")} style={{ alignItems: "center", paddingVertical: spacing.sm }}>
            <Text style={[type.bodySmall, { color: colors.textSecondary, fontWeight: "700" }]}>
              Voltar pro meu objetivo
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  // ---------------------------------------------------------------------
  // 4) PAINEL-RESUMO (§3.3, §3.4, §3.5) — a tela padrão depois do questionário
  // ---------------------------------------------------------------------
  const plano = state.active_plan;
  const a = state.active_answers;
  const temPendencias = state.pending_changes.length > 0;

  return (
    <View>
      {/* Alterações pendentes — não substituem o que está valendo até a pessoa
          confirmar e o plano novo ser gerado com sucesso (§3.5). */}
      {temPendencias ? (
        <Card accent={colors.warning} style={{ marginBottom: spacing.md }}>
          <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 8 }}>
            <Ionicons name="alert-circle" size={18} color={colors.warning} style={{ marginTop: 1 }} />
            <View style={{ flex: 1 }}>
              <Text style={[type.body, { color: colors.textPrimary, fontWeight: "800" }]}>
                Você tem alterações pendentes
              </Text>
              <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 3, lineHeight: 19 }]}>
                Você alterou informações que podem impactar{" "}
                {state.impacted_components.length > 0
                  ? state.impacted_components.map((c) => COMPONENT_LABEL[c] ?? c).join(", ")
                  : "seu plano"}
                . Até você confirmar, tudo continua como está.
              </Text>
            </View>
          </View>

          <View style={{ marginTop: spacing.sm }}>
            {state.pending_changes.map((c) => (
              <ChangeRow key={c.field} change={c} field={campoPorChave(c.field)} />
            ))}
          </View>

          {erro ? (
            <Text style={[type.caption, { color: colors.warning, marginTop: spacing.sm, textAlign: "center" }]}>
              {erro}
            </Text>
          ) : null}

          <View style={{ gap: spacing.xs, marginTop: spacing.md }}>
            <Button title="Atualizar meu plano" onPress={finalizar} loading={gerando} />
            <Button
              title="Continuar editando"
              variant="ghost"
              compact
              disabled={gerando}
              onPress={() => setModo("questionario")}
            />
            <TouchableOpacity
              onPress={() => setConfirmarDescarte(true)}
              disabled={gerando}
              style={{ alignItems: "center", paddingVertical: spacing.xs }}
            >
              <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700" }]}>
                Descartar alterações
              </Text>
            </TouchableOpacity>
          </View>
        </Card>
      ) : null}

      {/* Seu objetivo atual */}
      <Card accent={colors.primary} style={{ marginBottom: spacing.md }}>
        <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 0.5, textTransform: "uppercase" }]}>
          Seu objetivo atual
        </Text>
        <Text style={[type.h1, { color: colors.textPrimary, fontSize: 24, marginTop: 2 }]}>
          {formatAnswer(campoPorChave("goal"), a.goal)}
        </Text>

        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs, marginTop: spacing.sm }}>
          <Pill icon="flag" text={`Meta ${formatAnswer(campoPorChave("target_weight_kg"), a.target_weight_kg)}`} />
          <Pill icon="calendar-outline" text={`${formatAnswer(campoPorChave("training_days_per_week"), a.training_days_per_week)}/semana`} />
          <Pill icon="time-outline" text={formatAnswer(campoPorChave("session_length"), a.session_length)} />
          <Pill icon="speedometer" text={formatAnswer(campoPorChave("goal_pace"), a.goal_pace)} />
        </View>

        <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.md, lineHeight: 20 }]}>
          Seu treino, suas metas nutricionais, sua dieta em PDF, sua periodização e sua análise foram
          preparados com base neste questionário.
        </Text>

        {plano ? (
          <View style={{ marginTop: spacing.md, borderTopWidth: 1, borderTopColor: colors.border, paddingTop: spacing.md }}>
            <PlanComponents plan={plano} />
          </View>
        ) : null}
      </Card>

      {/* Atalhos — só a dieta personalizada mora aqui (a do Coaching, não uma
          pronta). "Ver meu treino" e "Ver análise" saíram: quem quiser essas
          informações vai direto nas abas Treino e Coaching. */}
      <View style={{ gap: spacing.xs, marginBottom: spacing.md }}>
        <Atalho icon="document-text" tint={colors.info} title="Ver dieta em PDF" onPress={abrirDietaPdf} />
      </View>

      {/* Metas nutricionais — só consulta. Editar é só pelo questionário
          ("Alterar respostas" abaixo), não existe mais uma tela separada. */}
      <Card style={{ marginBottom: spacing.md }}>
        <TouchableOpacity
          onPress={() => setVerMetas((v) => !v)}
          activeOpacity={0.7}
          style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
        >
          <Ionicons name="restaurant-outline" size={16} color={colors.primary} />
          <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", flex: 1 }]}>
            Ver metas nutricionais
          </Text>
          <Ionicons name={verMetas ? "chevron-up" : "chevron-down"} size={18} color={colors.textSecondary} />
        </TouchableOpacity>

        {verMetas ? (
          metaAtual ? (
            <View style={{ marginTop: spacing.sm }}>
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]}>
                  {metaAtual.mode === "auto" ? "AUTOMÁTICA" : "MANUAL"}
                </Text>
                <Text style={[type.h2, { color: colors.textPrimary }]}>
                  {Math.round(metaAtual.kcal)}
                  <Text style={[type.caption, { color: colors.textSecondary }]}> kcal</Text>
                </Text>
              </View>
              <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.sm }}>
                <Pill icon="flag" text={`P ${Math.round(metaAtual.protein_g)}g`} />
                <Pill icon="flag" text={`C ${Math.round(metaAtual.carbs_g)}g`} />
                <Pill icon="flag" text={`G ${Math.round(metaAtual.fat_g)}g`} />
              </View>
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm, lineHeight: 17 }]}>
                Pra mudar entre automática e manual, ou ajustar os números, use "Alterar respostas" abaixo.
              </Text>
            </View>
          ) : (
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.sm }]}>
              Você ainda não tem meta calórica.
            </Text>
          )
        ) : null}
      </Card>

      {/* Respostas do questionário — recolhido por padrão (§3.4), só consulta. */}
      <Card style={{ marginBottom: spacing.md }}>
        <TouchableOpacity
          onPress={() => setVerRespostas((v) => !v)}
          activeOpacity={0.7}
          style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
        >
          <Ionicons name="list-outline" size={16} color={colors.primary} />
          <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", flex: 1 }]}>
            Ver respostas do questionário
          </Text>
          <Ionicons name={verRespostas ? "chevron-up" : "chevron-down"} size={18} color={colors.textSecondary} />
        </TouchableOpacity>

        {verRespostas ? (
          <View style={{ marginTop: spacing.sm }}>
            {passos.map((s) => (
              <View key={s.key} style={{ marginTop: spacing.sm }}>
                <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "800", letterSpacing: 0.5, textTransform: "uppercase" }]}>
                  {s.title}
                </Text>
                {s.fields.map((f) => (
                  <View
                    key={f.key}
                    style={{ flexDirection: "row", alignItems: "flex-start", gap: 8, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.border }}
                  >
                    <Text style={[type.caption, { color: colors.textSecondary, flex: 1 }]}>{f.label}</Text>
                    <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "700", flex: 1, textAlign: "right" }]}>
                      {formatAnswer(f, a[f.key])}
                    </Text>
                  </View>
                ))}
              </View>
            ))}
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.sm, lineHeight: 17 }]}>
              Esta é a leitura das suas respostas. Pra mudar alguma coisa, use "Alterar respostas".
            </Text>
          </View>
        ) : null}
      </Card>

      <Button
        title="Alterar respostas"
        variant="secondary"
        onPress={() => {
          setRespostas(state.draft_answers ?? {});
          setEtapa(0);
          setModo("questionario");
        }}
      />

      {/* Histórico de planos (§3.3 / §12) */}
      {state.history.length > 0 ? (
        <Card style={{ marginTop: spacing.md, marginBottom: spacing.xl }}>
          <TouchableOpacity
            onPress={() => setVerHistorico((v) => !v)}
            activeOpacity={0.7}
            style={{ flexDirection: "row", alignItems: "center", gap: 8 }}
          >
            <Ionicons name="time-outline" size={16} color={colors.primary} />
            <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", flex: 1 }]}>
              Histórico de planos · {state.history.length}
            </Text>
            <Ionicons name={verHistorico ? "chevron-up" : "chevron-down"} size={18} color={colors.textSecondary} />
          </TouchableOpacity>
          {verHistorico ? (
            <View style={{ marginTop: spacing.sm }}>
              {state.history.map((p) => (
                <HistoryRow key={p.id} plan={p} />
              ))}
            </View>
          ) : null}
        </Card>
      ) : (
        <View style={{ height: spacing.xl }} />
      )}

      <ConfirmDialog
        visible={confirmarDescarte}
        onClose={() => setConfirmarDescarte(false)}
        title="Descartar alterações"
        message="Suas respostas voltam a ser as que estão valendo hoje. Seu plano atual não muda."
        confirmLabel="Descartar"
        destructive
        onConfirm={descartar}
      />

      {/* Dieta personalizada — montada pelo Coaching (meta + restrições do
          questionário), nunca uma dieta pronta genérica. Modal em vez de tela
          navegada: mesmo padrão do preview de "Dietas prontas" na aba Dieta. */}
      <Modal
        visible={dietaAberta}
        transparent
        animationType="slide"
        onRequestClose={() => setDietaAberta(false)}
      >
        <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.45)", justifyContent: "flex-end" }}>
          <View style={{ backgroundColor: colors.bg, borderTopLeftRadius: 24, borderTopRightRadius: 24, maxHeight: "88%" }}>
            {carregandoDieta || !dieta ? (
              <View style={{ padding: spacing.xxl, alignItems: "center" }}>
                {erroDieta ? (
                  <>
                    <Text style={[type.body, { color: colors.textPrimary, textAlign: "center", marginBottom: spacing.md }]}>
                      {erroDieta}
                    </Text>
                    <Button title="Fechar" variant="secondary" compact onPress={() => setDietaAberta(false)} />
                  </>
                ) : (
                  <ActivityIndicator color={colors.primary} size="large" />
                )}
              </View>
            ) : (
              <>
                <View
                  style={{
                    flexDirection: "row", alignItems: "center", padding: spacing.lg,
                    borderBottomWidth: 1, borderBottomColor: colors.border,
                  }}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={[type.h1, { color: colors.textPrimary }]}>{dieta.name}</Text>
                    <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 2 }]}>{dieta.tagline}</Text>
                  </View>
                  <TouchableOpacity onPress={() => setDietaAberta(false)} hitSlop={10}>
                    <Ionicons name="close" size={26} color={colors.textSecondary} />
                  </TouchableOpacity>
                </View>

                <ScrollView contentContainerStyle={{ padding: spacing.lg }} showsVerticalScrollIndicator={false}>
                  <View
                    style={{
                      flexDirection: "row", justifyContent: "space-around",
                      backgroundColor: colors.surface, borderRadius: radius.card, borderWidth: 1, borderColor: colors.border,
                      paddingVertical: spacing.md, marginBottom: spacing.md,
                    }}
                  >
                    <Total label="kcal" value={`${dieta.totals.kcal}`} colors={colors} type={type} />
                    <Total label="proteína" value={`${Math.round(dieta.totals.protein_g)}g`} colors={colors} type={type} />
                    <Total label="carbo" value={`${Math.round(dieta.totals.carbs_g)}g`} colors={colors} type={type} />
                    <Total label="gordura" value={`${Math.round(dieta.totals.fat_g)}g`} colors={colors} type={type} />
                  </View>

                  {dieta.restrictions.length > 0 ? (
                    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: spacing.md }}>
                      {dieta.restrictions.map((r) => (
                        <View key={r} style={{ backgroundColor: colors.surfaceAlt, borderRadius: radius.pill, paddingVertical: 4, paddingHorizontal: 10 }}>
                          <Text style={[type.caption, { color: colors.textSecondary, fontSize: 11 }]}>{r}</Text>
                        </View>
                      ))}
                    </View>
                  ) : null}

                  {dieta.meals.map((meal) => (
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
                          <Text style={[type.caption, { color: colors.textSecondary }]}>{Math.round(it.kcal)} kcal</Text>
                        </View>
                      ))}
                    </View>
                  ))}
                </ScrollView>

                <View style={{ padding: spacing.lg, borderTopWidth: 1, borderTopColor: colors.border }}>
                  <TouchableOpacity
                    onPress={baixarDietaPdf}
                    disabled={baixandoDieta}
                    style={{
                      flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6,
                      paddingVertical: 10, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border,
                      marginBottom: spacing.sm,
                    }}
                  >
                    {baixandoDieta ? (
                      <ActivityIndicator size="small" color={colors.textSecondary} />
                    ) : (
                      <Ionicons name="download-outline" size={16} color={colors.textSecondary} />
                    )}
                    <Text style={[type.bodySmall, { color: colors.textSecondary, fontWeight: "700" }]}>Baixar PDF</Text>
                  </TouchableOpacity>
                  <Button title="Usar esta dieta hoje" onPress={() => setConfirmarUsarDieta(true)} loading={aplicandoDieta} />
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>

      <ConfirmDialog
        visible={confirmarUsarDieta}
        onClose={() => setConfirmarUsarDieta(false)}
        title="Usar esta dieta hoje?"
        message={
          dieta
            ? `Vou registrar as ${dieta.meals.length} refeições (${dieta.totals.kcal} kcal) no seu diário de hoje. Isso não apaga o que você já registrou — só adiciona.`
            : undefined
        }
        confirmLabel="Registrar"
        onConfirm={usarDietaHoje}
      />
      <InfoDialog
        visible={sucessoDieta !== null}
        onClose={() => {
          setSucessoDieta(null);
          setDietaAberta(false);
        }}
        title="Dieta registrada ✓"
        message={sucessoDieta ?? undefined}
      />
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

// ---------------------------------------------------------------------------
// Blocos auxiliares
// ---------------------------------------------------------------------------

function Pill({ icon, text }: { icon: keyof typeof Ionicons.glyphMap; text: string }) {
  const { colors, type, radius } = useTheme();
  return (
    <View
      style={{
        flexDirection: "row", alignItems: "center", gap: 5,
        backgroundColor: colors.surfaceAlt, borderRadius: radius.pill,
        paddingVertical: 5, paddingHorizontal: 10,
      }}
    >
      <Ionicons name={icon} size={12} color={colors.primary} />
      <Text style={[type.caption, { color: colors.textPrimary, fontWeight: "700" }]} numberOfLines={1}>
        {text}
      </Text>
    </View>
  );
}

function Atalho({
  icon,
  tint,
  title,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  tint: string;
  title: string;
  onPress: () => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <TouchableOpacity
      activeOpacity={0.85}
      onPress={onPress}
      style={{
        flexDirection: "row", alignItems: "center", gap: spacing.md,
        backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border,
        borderRadius: radius.card, padding: spacing.sm,
      }}
    >
      <View
        style={{
          width: 36, height: 36, borderRadius: 12, backgroundColor: tint + "1F",
          alignItems: "center", justifyContent: "center",
        }}
      >
        <Ionicons name={icon} size={18} color={tint} />
      </View>
      <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", flex: 1 }]}>{title}</Text>
      <Ionicons name="chevron-forward" size={17} color={colors.textSecondary} />
    </TouchableOpacity>
  );
}

/** O que este plano gerou — treino, metas, PDF, periodização, análise. */
function PlanComponents({ plan }: { plan: PlanSummary }) {
  const { colors, type, spacing } = useTheme();
  const w = plan.components.workout;
  const itens: { icon: keyof typeof Ionicons.glyphMap; texto: string }[] = [];
  if (w) {
    itens.push({
      icon: "barbell-outline",
      texto: `${w.method_name} · ${w.days} ${w.days === 1 ? "treino" : "treinos"} · ${w.total_exercises} exercícios`,
    });
  }
  if (plan.components.calorie_goal_id) itens.push({ icon: "flame", texto: "Metas de calorias e macros atualizadas" });
  if (plan.components.dieta_pdf) itens.push({ icon: "document-text", texto: "Dieta completa disponível em PDF" });
  if (plan.components.periodizacao) {
    itens.push({ icon: "repeat", texto: `Periodização: ${plan.components.periodizacao}` });
  }
  if (itens.length === 0) return null;

  return (
    <View style={{ gap: 7 }}>
      {itens.map((i) => (
        <View key={i.texto} style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <Ionicons name={i.icon} size={14} color={colors.primary} />
          <Text style={[type.caption, { color: colors.textSecondary, flex: 1, lineHeight: 18 }]}>{i.texto}</Text>
        </View>
      ))}
      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs, fontStyle: "italic" }]}>
        Todas as áreas do app refletem esta mesma versão.
      </Text>
    </View>
  );
}

function ChangeRow({ change, field }: { change: PendingChange; field?: QuestionField }) {
  const { colors, type } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-start", gap: 6, paddingVertical: 4 }}>
      <Ionicons name="swap-horizontal-outline" size={12} color={colors.textSecondary} style={{ marginTop: 3 }} />
      <Text style={[type.caption, { color: colors.textSecondary, flex: 1, lineHeight: 17 }]}>
        <Text style={{ fontWeight: "700", color: colors.textPrimary }}>{change.label}: </Text>
        {formatAnswer(field, change.from)} → {formatAnswer(field, change.to)}
      </Text>
    </View>
  );
}

function HistoryRow({ plan }: { plan: PlanSummary }) {
  const { colors, type, spacing, radius } = useTheme();
  const data = new Date(plan.activated_at ?? plan.created_at).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
  const cor =
    plan.status === "active" ? colors.success : plan.status === "failed" ? colors.warning : colors.textSecondary;
  const rotulo = plan.status === "active" ? "Ativo" : plan.status === "failed" ? "Falhou" : "Arquivado";
  return (
    <View style={{ paddingVertical: 8, borderTopWidth: 1, borderTopColor: colors.border }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
        <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "800" }]}>v{plan.version}</Text>
        <View style={{ backgroundColor: cor + "20", borderRadius: radius.pill, paddingVertical: 2, paddingHorizontal: 8 }}>
          <Text style={[type.caption, { color: cor, fontWeight: "700", fontSize: 10 }]}>{rotulo}</Text>
        </View>
        <Text style={[type.caption, { color: colors.textSecondary, flex: 1, textAlign: "right" }]}>{data}</Text>
      </View>
      {plan.error ? (
        <Text style={[type.caption, { color: colors.warning, marginTop: 3, lineHeight: 16 }]} numberOfLines={2}>
          Não foi ativado: {plan.error}
        </Text>
      ) : plan.changes.length > 0 ? (
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 3, lineHeight: 16 }]} numberOfLines={3}>
          {plan.changes.map((c) => c.label).join(" · ")}
        </Text>
      ) : (
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 3 }]}>
          {plan.reason === "primeiro_plano" ? "Primeiro plano" : "Sem mudanças de resposta"}
        </Text>
      )}
      <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs, fontSize: 10 }]}>
        As respostas usadas nesta versão ficam guardadas pra comparação.
      </Text>
    </View>
  );
}

/** Desenha UM campo do questionário conforme o tipo que veio do backend. */
function FieldEditor({
  field,
  value,
  onChange,
}: {
  field: QuestionField;
  value: any;
  onChange: (v: any) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();

  function toggleMulti(v: string) {
    const atual: string[] = Array.isArray(value) ? value : [];
    if (atual.includes(v)) {
      onChange(atual.filter((x) => x !== v));
      return;
    }
    if (field.max_selected && atual.length >= field.max_selected) return;
    onChange([...atual, v]);
  }

  return (
    <View style={{ marginBottom: spacing.md }}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginBottom: spacing.xs }}>
        <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700" }]}>
          {field.label}
          {field.required ? <Text style={{ color: colors.primary }}> *</Text> : null}
        </Text>
        {field.help ? <HelpDot title={field.label} text={field.help} /> : null}
      </View>

      {field.type === "text" ? (
        <TextInput
          value={value ?? ""}
          onChangeText={onChange}
          placeholder={field.placeholder}
          placeholderTextColor={colors.textSecondary}
          multiline={field.multiline}
          style={[
            type.bodySmall,
            {
              color: colors.textPrimary,
              backgroundColor: colors.surfaceAlt,
              borderRadius: radius.button,
              padding: spacing.sm,
              minHeight: field.multiline ? 84 : 48,
              textAlignVertical: field.multiline ? "top" : "center",
            },
          ]}
        />
      ) : field.type === "number" ? (
        <View
          style={{
            flexDirection: "row", alignItems: "center",
            backgroundColor: colors.surfaceAlt, borderRadius: radius.button,
            paddingHorizontal: spacing.sm, height: 48,
          }}
        >
          <NumberInput field={field} value={value} onChange={onChange} colors={colors} type={type} />
          {field.suffix ? (
            <Text style={[type.caption, { color: colors.textSecondary }]}>{field.suffix}</Text>
          ) : null}
        </View>
      ) : field.type === "bool" ? (
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          {[
            { v: true, label: "Sim" },
            { v: false, label: "Não" },
          ].map((o) => {
            const on = value === o.v;
            return (
              <TouchableOpacity
                key={o.label}
                onPress={() => onChange(on ? null : o.v)}
                activeOpacity={0.8}
                style={{
                  flex: 1, alignItems: "center", paddingVertical: spacing.sm,
                  borderRadius: radius.pill, borderWidth: 1.5,
                  borderColor: on ? colors.primary : colors.border,
                  backgroundColor: on ? colors.primary : colors.surfaceAlt,
                }}
              >
                <Text
                  style={[
                    type.bodySmall,
                    { color: on ? colors.textOnPrimary : colors.textPrimary, fontWeight: on ? "700" : "500" },
                  ]}
                >
                  {o.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      ) : (
        <View style={{ gap: spacing.xs }}>
          {(field.options ?? []).map((o) => {
            const on =
              field.type === "multi"
                ? Array.isArray(value) && value.includes(o.value)
                : String(value ?? "") === o.value;
            const noTeto =
              field.type === "multi" &&
              !on &&
              !!field.max_selected &&
              Array.isArray(value) &&
              value.length >= field.max_selected;
            return (
              <TouchableOpacity
                key={o.value}
                activeOpacity={0.75}
                disabled={noTeto}
                onPress={() => (field.type === "multi" ? toggleMulti(o.value) : onChange(on ? null : o.value))}
                style={{
                  flexDirection: "row", alignItems: "flex-start", gap: 10,
                  borderWidth: 1.5, borderColor: on ? colors.primary : colors.border,
                  backgroundColor: on ? colors.primary + "12" : colors.surface,
                  borderRadius: radius.card, padding: spacing.sm,
                  opacity: noTeto ? 0.45 : 1,
                }}
              >
                <Ionicons
                  name={
                    field.type === "multi"
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
                  <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: on ? "700" : "500" }]}>
                    {o.label}
                  </Text>
                  {o.desc ? (
                    <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, lineHeight: 17 }]}>
                      {o.desc}
                    </Text>
                  ) : null}
                </View>
              </TouchableOpacity>
            );
          })}
        </View>
      )}
    </View>
  );
}

/** Campo numérico com estado local de texto — sem isto, re-derivar o texto a
 * partir do número a cada tecla ("78." -> Number -> 78 -> "78") apaga o ponto
 * decimal assim que ele é digitado, e "78.4" nunca consegue ser completado
 * (o "4" gruda em "78" virando "784"). O texto digitado manda; o número sai
 * só quando fecha um valor válido. */
function NumberInput({
  field,
  value,
  onChange,
  colors,
  type,
}: {
  field: QuestionField;
  value: any;
  onChange: (v: any) => void;
  colors: any;
  type: any;
}) {
  const [texto, setTexto] = useState(value != null ? String(value) : "");

  function handleChange(v: string) {
    const limpo = v.replace(",", ".").replace(field.decimal ? /[^0-9.]/g : /[^0-9]/g, "");
    setTexto(limpo);
    if (limpo === "" || limpo === ".") {
      onChange(null);
      return;
    }
    const n = Number(limpo);
    if (!Number.isNaN(n)) onChange(n);
  }

  return (
    <TextInput
      value={texto}
      onChangeText={handleChange}
      keyboardType={field.decimal ? "decimal-pad" : "number-pad"}
      placeholder="—"
      placeholderTextColor={colors.textSecondary}
      style={[type.body, { flex: 1, color: colors.textPrimary, fontWeight: "600" }]}
    />
  );
}
