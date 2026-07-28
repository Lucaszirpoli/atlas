import { api } from "./client";

/** Tipos de campo que a tela do questionário sabe desenhar. */
export type FieldType = "text" | "number" | "single" | "multi" | "bool";

export type QuestionOption = { value: string; label: string; desc?: string };

export type QuestionField = {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  help?: string;
  placeholder?: string;
  options?: QuestionOption[];
  max_selected?: number;
  multiline?: boolean;
  suffix?: string;
  min?: number;
  max?: number;
  decimal?: boolean;
  /** Só aparece/entra na conta de obrigatório quando outro campo tem um
   * certo valor (ex.: os campos da meta manual só valem com calorie_goal_mode
   * = "manual"). Sem isto, o campo sempre vale. */
  shows_if?: { field: string; equals: string };
};

export type QuestionStep = {
  key: string;
  title: string;
  subtitle: string;
  fields: QuestionField[];
};

export type Questionnaire = { steps: QuestionStep[]; required: string[] };

export type Answers = Record<string, any>;

export type PendingChange = {
  field: string;
  label: string;
  section: string;
  from: any;
  to: any;
};

export type PlanSummary = {
  id: number;
  version: number;
  status: "active" | "archived" | "failed";
  reason: string;
  changes: PendingChange[];
  components: {
    calorie_goal_id?: number;
    workout?: { method_name: string; days: number; total_exercises: number; routines: string[] };
    periodizacao?: string;
    dieta_pdf?: boolean;
    gerados?: string[];
  };
  created_at: string;
  activated_at: string | null;
  archived_at: string | null;
  error: string | null;
};

/** Tudo que a aba Objetivo precisa, numa chamada — é o que decide qual tela
 * mostrar: apresentação + questionário, ou painel-resumo (com ou sem
 * pendências). */
export type ObjectiveState = {
  has_plan: boolean;
  active_plan: PlanSummary | null;
  /** Respostas VALENDO agora (as que geraram o plano ativo). */
  active_answers: Answers;
  /** O que está sendo editado. Igual às ativas = sem pendência. */
  draft_answers: Answers;
  draft_step: number;
  pending_changes: PendingChange[];
  impacted_components: string[];
  missing_required: string[];
  history: PlanSummary[];
};

export async function getQuestionnaire(): Promise<Questionnaire> {
  const { data } = await api.get<Questionnaire>("/objective/questionnaire");
  return data;
}

export async function getObjectiveState(): Promise<ObjectiveState> {
  const { data } = await api.get<ObjectiveState>("/objective");
  return data;
}

/** Salva o progresso ao avançar, voltar, minimizar ou fechar o app. NÃO
 * substitui as respostas ativas — isso só acontece na ativação. */
export async function saveObjectiveDraft(answers: Answers, step: number): Promise<ObjectiveState> {
  const { data } = await api.put<ObjectiveState>("/objective/draft", { answers, step });
  return data;
}

/** "Descartar alterações": o rascunho volta a ser igual às respostas ativas. */
export async function discardObjectiveDraft(): Promise<ObjectiveState> {
  const { data } = await api.post<ObjectiveState>("/objective/draft/discard", {});
  return data;
}

/** "Finalizar e gerar meu plano" / "Atualizar meu plano". Tudo ou nada: se
 * algum componente falhar, o plano atual continua valendo. */
export async function activateObjectivePlan(): Promise<ObjectiveState> {
  const { data } = await api.post<ObjectiveState>("/objective/activate", {});
  return data;
}

/** Rótulo humano de um componente do plano, pro aviso de pendências. */
export const COMPONENT_LABEL: Record<string, string> = {
  treino: "seu treino",
  metas: "suas metas nutricionais",
  dieta: "sua dieta em PDF",
  periodizacao: "sua periodização",
  analise: "a análise do coach",
};

/** Formata o valor de uma resposta pra leitura ("seg, ter" em vez de array). */
export function formatAnswer(field: QuestionField | undefined, value: any): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  if (Array.isArray(value)) {
    if (value.length === 0) return "—";
    return value
      .map((v) => field?.options?.find((o) => o.value === String(v))?.label ?? String(v))
      .join(", ");
  }
  const opt = field?.options?.find((o) => o.value === String(value));
  if (opt) return opt.label;
  return field?.suffix ? `${value} ${field.suffix}` : String(value);
}
