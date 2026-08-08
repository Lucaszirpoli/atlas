import AsyncStorage from "@react-native-async-storage/async-storage";
import React, { createContext, useContext, useEffect, useState } from "react";

import { getActiveWorkoutSession } from "../api/workoutSessions";
import { useAuth } from "./AuthContext";

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
  /** Início da sessão (ms epoch, do started_at do backend) — pra medir a
   * duração real e detectar um treino anormalmente longo ao concluir. */
  startedAt?: number;
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

const CHAVE = "@appfit/treino_em_andamento";

/**
 * POR QUE ISTO É GRAVADO EM DISCO (2026-08-07):
 *
 * O treino em andamento vivia só num useState. Bastava o processo do app
 * morrer — crash, Android matando o app em segundo plano, celular
 * reiniciando — pra ele evaporar: o indicador flutuante sumia e não sobrava
 * NENHUM caminho de volta. A sessão continuava aberta no servidor, com todas
 * as séries já registradas, mas invisível pro app (o Histórico só lista
 * treino concluído). Foi exatamente isso que o usuário viveu: "o app fechou
 * sozinho e eu perdi até o treino que eu tava fazendo".
 *
 * Agora há duas redes: o registro local (instantâneo, funciona sem internet)
 * e, se ele faltar, o servidor — que sabe qual sessão ficou aberta mesmo se o
 * app foi reinstalado ou o armazenamento local se perdeu.
 */
async function gravar(w: ActiveWorkout | null): Promise<void> {
  try {
    if (w) await AsyncStorage.setItem(CHAVE, JSON.stringify(w));
    else await AsyncStorage.removeItem(CHAVE);
  } catch {
    // Sem armazenamento não dá pra atrapalhar o treino: o app segue com o
    // estado em memória, que é o comportamento antigo.
  }
}

async function ler(): Promise<ActiveWorkout | null> {
  try {
    const cru = await AsyncStorage.getItem(CHAVE);
    if (!cru) return null;
    const w = JSON.parse(cru) as ActiveWorkout;
    return typeof w?.sessionId === "number" && typeof w?.routineId === "number" ? w : null;
  } catch {
    return null;
  }
}

export function ActiveWorkoutProvider({ children }: { children: React.ReactNode }) {
  const [active, setActive] = useState<ActiveWorkout | null>(null);
  const [onWorkoutScreen, setOnWorkoutScreen] = useState(false);
  const { user } = useAuth();

  // Recupera um treino aberto — mas só com alguém logado, e refazendo a conta
  // a cada troca de usuário: um treino é de UMA pessoa, e ressuscitar no
  // celular emprestado o treino de quem usou antes seria pior que o bug que
  // isto conserta.
  useEffect(() => {
    if (!user) {
      setActive(null);
      gravar(null);
      return;
    }
    let cancelado = false;
    (async () => {
      const local = await ler();
      if (cancelado) return;
      if (local) setActive(local);

      // O servidor é a fonte da verdade sobre "esta sessão ainda está aberta".
      // Ele resolve os dois lados: confirma (ou descarta) o registro local que
      // pode ter ficado velho, e ACHA a sessão aberta quando não há registro
      // local nenhum — o caso de quem já perdeu o treino antes desta correção.
      try {
        const remoto = await getActiveWorkoutSession();
        if (cancelado) return;
        if (!remoto) {
          // Nada aberto no servidor: se havia registro local, ele é lixo de um
          // treino já concluído/descartado. Some com ele (senão o indicador
          // flutuante ficaria pra sempre apontando pro nada).
          if (local) {
            setActive(null);
            gravar(null);
          }
          return;
        }
        const recuperado: ActiveWorkout = {
          sessionId: remoto.session.id,
          routineId: remoto.routine_id,
          routineName: remoto.routine_name,
          prefill: remoto.prefill,
          startedAt: new Date(remoto.session.started_at).getTime(),
        };
        setActive(recuperado);
        gravar(recuperado);
      } catch {
        // Sem internet na abertura: fica com o registro local, que já é bem
        // melhor que perder o treino. A próxima abertura confere de novo.
      }
    })();
    return () => {
      cancelado = true;
    };
  }, [user?.id]);

  return (
    <Ctx.Provider
      value={{
        active,
        startWorkout: (w) => {
          setActive(w);
          gravar(w);
        },
        endWorkout: () => {
          setActive(null);
          gravar(null);
        },
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
