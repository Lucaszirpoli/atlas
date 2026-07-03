import type { Exercise } from "../../api/exercises";

/** Canal simples para o ExercisePicker devolver o exercício escolhido ao
 * RoutineBuilder. Substitui o padrão de params+useEffect, que na prática
 * perdia adições (só entrava um exercício). Aqui a cada escolha o handler
 * registrado pelo builder é chamado direto e de forma síncrona. */
type Handler = (exercise: Exercise) => void;

let handler: Handler | null = null;

export const exercisePickBus = {
  setHandler(h: Handler | null) {
    handler = h;
  },
  pick(exercise: Exercise) {
    handler?.(exercise);
  },
};
