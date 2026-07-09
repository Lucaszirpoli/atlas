import React, { createContext, useContext, useState } from "react";

/** Um treino "em andamento": a pessoa iniciou uma rotina e ainda não concluiu.
 * Guardado globalmente pra mostrar um indicador em qualquer tela (mesmo fora
 * do módulo de treino) e deixar ela voltar pro treino num toque. */
export type ActiveWorkout = {
  sessionId: number;
  routineId: number;
  routineName: string;
  /** Params pra reabrir a tela de execução exatamente onde estava (valores
   * "anteriores" de cada série). As séries já concluídas ficam salvas no
   * backend; isto é só pra remontar a tela ao voltar pelo indicador. */
  prefill: unknown;
};

type Value = {
  active: ActiveWorkout | null;
  startWorkout: (w: ActiveWorkout) => void;
  endWorkout: () => void;
  /** True enquanto a própria tela de execução está em foco — o indicador
   * flutuante se esconde nela (não faz sentido "voltar pro treino" estando
   * nele). Setado pela WorkoutExecutionScreen via useFocusEffect. */
  onWorkoutScreen: boolean;
  setOnWorkoutScreen: (v: boolean) => void;
};

const Ctx = createContext<Value | null>(null);

export function ActiveWorkoutProvider({ children }: { children: React.ReactNode }) {
  const [active, setActive] = useState<ActiveWorkout | null>(null);
  const [onWorkoutScreen, setOnWorkoutScreen] = useState(false);
  return (
    <Ctx.Provider
      value={{
        active,
        startWorkout: setActive,
        endWorkout: () => setActive(null),
        onWorkoutScreen,
        setOnWorkoutScreen,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useActiveWorkout(): Value {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useActiveWorkout precisa estar dentro de um ActiveWorkoutProvider");
  return ctx;
}
