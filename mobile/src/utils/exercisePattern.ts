import type { Equipment, MuscleGroup } from "../api/exercises";

/** Padrão de movimento usado só pra escolher a pose do boneco ilustrativo —
 * não é um dado de negócio, é puramente visual. Cobre os movimentos mais
 * comuns da base de exercícios (ver backend/app/data/exercise_seed.csv). */
export type MovementPattern =
  | "horizontal_push"
  | "vertical_push"
  | "horizontal_pull"
  | "vertical_pull"
  | "squat"
  | "hinge"
  | "lunge"
  | "curl"
  | "triceps_extension"
  | "lateral_raise"
  | "calf_raise"
  | "core"
  | "cardio"
  | "carry";

const NAME_KEYWORDS: Array<[RegExp, MovementPattern]> = [
  [/agachamento|leg press|hack/i, "squat"],
  [/afundo|passada|b[uú]lgaro/i, "lunge"],
  [/terra|stiff|hip thrust|elevação pélvica|good morning/i, "hinge"],
  [/panturrilha/i, "calf_raise"],
  [/rosca/i, "curl"],
  [/tr[ií]ceps|tr[íi]ceps|mergulho|paralelas/i, "triceps_extension"],
  [/elevação lateral|elevação frontal|voador inverso|crucifixo inverso/i, "lateral_raise"],
  [/puxada|barra fixa|pull.?up/i, "vertical_pull"],
  [/remada/i, "horizontal_pull"],
  [/desenvolvimento|militar|arnold/i, "vertical_push"],
  [/supino|flex[ãa]o de bra[çc]o|crucifixo|peck deck|voador(?! inverso)/i, "horizontal_push"],
  [/abdominal|prancha|abd[uô]men/i, "core"],
  [/esteira|bike|el[íi]ptico|corrida|pular corda/i, "cardio"],
  [/carreg|farmer/i, "carry"],
];

function classifyByName(name: string): MovementPattern | null {
  for (const [re, pattern] of NAME_KEYWORDS) {
    if (re.test(name)) return pattern;
  }
  return null;
}

function classifyByMuscleGroup(muscleGroup: MuscleGroup, equipment: Equipment): MovementPattern {
  switch (muscleGroup) {
    case "chest":
      return "horizontal_push";
    case "back":
      return "horizontal_pull";
    case "shoulders":
      return "vertical_push";
    case "biceps":
      return "curl";
    case "triceps":
      return "triceps_extension";
    case "quads":
      return "squat";
    case "hamstrings":
    case "glutes":
      return "hinge";
    case "calves":
      return "calf_raise";
    case "abs":
      return "core";
    case "forearms":
      return "curl";
    case "traps":
      return "vertical_pull";
    case "cardio":
      return "cardio";
    case "full_body":
      return equipment === "bodyweight" ? "core" : "hinge";
    default:
      return "carry";
  }
}

export function classifyMovementPattern(
  name: string,
  muscleGroup: MuscleGroup,
  equipment: Equipment
): MovementPattern {
  return classifyByName(name) ?? classifyByMuscleGroup(muscleGroup, equipment);
}
