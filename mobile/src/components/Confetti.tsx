import React, { useEffect, useRef } from "react";
import { Animated, Dimensions, Easing, StyleSheet, View } from "react-native";

const COLORS = ["#1F7A5C", "#FF6B35", "#4A5B8C", "#E8637A", "#3B82C4", "#E8A33D", "#2FA37A"];

/** Chuva de confete leve e discreta, disparada uma vez ao montar. Usada em
 * momentos de celebração (ex: novo recorde pessoal). Puro Animated, sem
 * dependência extra — funciona em iOS, Android e web. */
export function Confetti({ count = 26 }: { count?: number }) {
  const { width, height } = Dimensions.get("window");
  const pieces = useRef(
    Array.from({ length: count }, (_, i) => ({
      key: i,
      left: Math.random() * width,
      color: COLORS[i % COLORS.length],
      size: 6 + Math.random() * 7,
      delay: Math.random() * 400,
      duration: 1600 + Math.random() * 1400,
      drift: (Math.random() - 0.5) * 120,
      rotateTo: Math.random() * 6,
      fall: new Animated.Value(0),
    }))
  ).current;

  useEffect(() => {
    Animated.parallel(
      pieces.map((p) =>
        Animated.timing(p.fall, {
          toValue: 1,
          duration: p.duration,
          delay: p.delay,
          easing: Easing.linear,
          useNativeDriver: true,
        })
      )
    ).start();
  }, []);

  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      {pieces.map((p) => {
        const translateY = p.fall.interpolate({ inputRange: [0, 1], outputRange: [-40, height + 40] });
        const translateX = p.fall.interpolate({ inputRange: [0, 1], outputRange: [0, p.drift] });
        const rotate = p.fall.interpolate({ inputRange: [0, 1], outputRange: ["0deg", `${p.rotateTo * 360}deg`] });
        const opacity = p.fall.interpolate({ inputRange: [0, 0.85, 1], outputRange: [1, 1, 0] });
        return (
          <Animated.View
            key={p.key}
            style={{
              position: "absolute",
              left: p.left,
              top: 0,
              width: p.size,
              height: p.size * 1.4,
              borderRadius: 2,
              backgroundColor: p.color,
              opacity,
              transform: [{ translateY }, { translateX }, { rotate }],
            }}
          />
        );
      })}
    </View>
  );
}
