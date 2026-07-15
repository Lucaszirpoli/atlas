import React, { useEffect, useRef } from "react";
import { Animated } from "react-native";
import Svg, { Circle, Line } from "react-native-svg";

import type { MovementPattern } from "../utils/exercisePattern";
import { useTheme } from "../theme/ThemeProvider";

type Pose = {
  /** 0 = tronco ereto, + = inclinado pra frente (quadril/dobradiça) */
  torsoAngle: number;
  /** 0 = altura de pé, + = agachado/sentado (abaixa o quadril) */
  hipDrop: number;
  /** braço (ombro): 0 = pendurado pra baixo, 90 = horizontal à frente, 180 = reto pra cima */
  armAngle: number;
  /** antebraço (cotovelo), mesma convenção do braço, ângulo absoluto */
  forearmAngle: number;
  /** coxa (quadril): 0 = reta pra baixo (em pé), + = à frente/elevada */
  legAngle: number;
  /** canela (joelho), mesma convenção da coxa, ângulo absoluto */
  shinAngle: number;
};

const BASE: Pose = { torsoAngle: 0, hipDrop: 0, armAngle: 12, forearmAngle: 12, legAngle: 0, shinAngle: 0 };

function pose(overrides: Partial<Pose>): Pose {
  return { ...BASE, ...overrides };
}

const POSES: Record<MovementPattern, { start: Pose; end: Pose }> = {
  horizontal_push: {
    start: pose({ armAngle: 95, forearmAngle: 155 }),
    end: pose({ armAngle: 95, forearmAngle: 95 }),
  },
  vertical_push: {
    start: pose({ armAngle: 90, forearmAngle: 150 }),
    end: pose({ armAngle: 175, forearmAngle: 175 }),
  },
  horizontal_pull: {
    start: pose({ torsoAngle: 25, armAngle: 100, forearmAngle: 100 }),
    end: pose({ torsoAngle: 25, armAngle: 35, forearmAngle: 5 }),
  },
  vertical_pull: {
    start: pose({ armAngle: 175, forearmAngle: 175 }),
    end: pose({ armAngle: 60, forearmAngle: 100 }),
  },
  squat: {
    start: pose({}),
    end: pose({ torsoAngle: 22, hipDrop: 26, legAngle: 70, shinAngle: 25 }),
  },
  hinge: {
    start: pose({ armAngle: 20, forearmAngle: 20 }),
    end: pose({ torsoAngle: 68, armAngle: 15, forearmAngle: 15, legAngle: 8, shinAngle: 5 }),
  },
  lunge: {
    start: pose({}),
    end: pose({ torsoAngle: 10, hipDrop: 18, legAngle: 55, shinAngle: 15 }),
  },
  curl: {
    start: pose({ armAngle: 15, forearmAngle: 12 }),
    end: pose({ armAngle: 15, forearmAngle: 155 }),
  },
  triceps_extension: {
    start: pose({ armAngle: 172, forearmAngle: 65 }),
    end: pose({ armAngle: 172, forearmAngle: 172 }),
  },
  lateral_raise: {
    start: pose({ armAngle: 10, forearmAngle: 10 }),
    end: pose({ armAngle: 92, forearmAngle: 92 }),
  },
  calf_raise: {
    start: pose({}),
    end: pose({ hipDrop: -8 }),
  },
  core: {
    start: pose({
      torsoAngle: 35,
      hipDrop: 40,
      legAngle: 80,
      shinAngle: 90,
      armAngle: 90,
      forearmAngle: 150,
    }),
    end: pose({
      torsoAngle: 78,
      hipDrop: 40,
      legAngle: 80,
      shinAngle: 90,
      armAngle: 90,
      forearmAngle: 150,
    }),
  },
  cardio: {
    start: pose({ torsoAngle: 10, armAngle: 30, forearmAngle: 100, legAngle: -20, shinAngle: 10 }),
    end: pose({ torsoAngle: 10, armAngle: 120, forearmAngle: 200, legAngle: 60, shinAngle: 100 }),
  },
  carry: {
    start: pose({}),
    end: pose({ legAngle: 15 }),
  },
};

/** Converte um ângulo na convenção do boneco (0 = reto pra baixo, 90 = horizontal
 * à frente, 180 = reto pra cima) num deslocamento (dx, dy) em coordenadas de tela
 * (y cresce pra baixo). */
function polar(len: number, angleDeg: number): { dx: number; dy: number } {
  const rad = (angleDeg * Math.PI) / 180;
  return { dx: len * Math.sin(rad), dy: len * Math.cos(rad) };
}

const HIP_Y = 88;
const CX = 50;
const TORSO_LEN = 26;
const HEAD_R = 8;
const UPPER_ARM = 17;
const FOREARM = 15;
const UPPER_LEG = 27;
const SHIN = 24;

function StickFigure({ p, color, strokeWidth }: { p: Pose; color: string; strokeWidth: number }) {
  const hip = { x: CX, y: HIP_Y - p.hipDrop };
  const torso = polar(TORSO_LEN, 180 + p.torsoAngle);
  const shoulder = { x: hip.x + torso.dx, y: hip.y + torso.dy };
  const neck = polar(HEAD_R * 1.6, 180 + p.torsoAngle);
  const head = { x: shoulder.x + neck.dx, y: shoulder.y + neck.dy };

  const arm = polar(UPPER_ARM, p.armAngle);
  const elbow = { x: shoulder.x + arm.dx, y: shoulder.y + arm.dy };
  const fore = polar(FOREARM, p.forearmAngle);
  const hand = { x: elbow.x + fore.dx, y: elbow.y + fore.dy };

  const leg = polar(UPPER_LEG, p.legAngle);
  const knee = { x: hip.x + leg.dx, y: hip.y + leg.dy };
  const shin = polar(SHIN, p.shinAngle);
  const ankle = { x: knee.x + shin.dx, y: knee.y + shin.dy };

  const lineProps = { stroke: color, strokeWidth, strokeLinecap: "round" as const };

  return (
    <>
      <Circle cx={head.x} cy={head.y} r={HEAD_R} fill={color} />
      <Line x1={shoulder.x} y1={shoulder.y} x2={hip.x} y2={hip.y} {...lineProps} />
      <Line x1={shoulder.x} y1={shoulder.y} x2={elbow.x} y2={elbow.y} {...lineProps} />
      <Line x1={elbow.x} y1={elbow.y} x2={hand.x} y2={hand.y} {...lineProps} />
      <Line x1={hip.x} y1={hip.y} x2={knee.x} y2={knee.y} {...lineProps} />
      <Line x1={knee.x} y1={knee.y} x2={ankle.x} y2={ankle.y} {...lineProps} />
    </>
  );
}

/** Boneco vetorial ilustrando a execução de um exercício, a partir só do
 * padrão de movimento (ver exercisePattern.ts) — não depende de imagem
 * externa. Alterna entre a pose inicial e final pra sugerir o movimento. */
export function ExerciseFigure({
  pattern,
  size = 44,
  animated = true,
}: {
  pattern: MovementPattern;
  size?: number;
  animated?: boolean;
}) {
  const { colors } = useTheme();
  const t = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!animated) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(t, { toValue: 1, duration: 700, useNativeDriver: true, delay: 500 }),
        Animated.timing(t, { toValue: 0, duration: 700, useNativeDriver: true, delay: 500 }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [animated, t]);

  const { start, end } = POSES[pattern];
  const startOpacity = t.interpolate({ inputRange: [0, 1], outputRange: [1, 0] });
  const endOpacity = t;

  if (!animated) {
    return (
      <Svg viewBox="0 0 100 140" width={size} height={size}>
        <StickFigure p={end} color={colors.textSecondary} strokeWidth={6} />
      </Svg>
    );
  }

  return (
    <Animated.View style={{ width: size, height: size }}>
      <Animated.View style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, opacity: startOpacity }}>
        <Svg viewBox="0 0 100 140" width={size} height={size}>
          <StickFigure p={start} color={colors.textSecondary} strokeWidth={6} />
        </Svg>
      </Animated.View>
      <Animated.View style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, opacity: endOpacity }}>
        <Svg viewBox="0 0 100 140" width={size} height={size}>
          <StickFigure p={end} color={colors.textSecondary} strokeWidth={6} />
        </Svg>
      </Animated.View>
    </Animated.View>
  );
}
