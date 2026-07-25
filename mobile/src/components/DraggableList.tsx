import { Ionicons } from "@expo/vector-icons";
import React, { useMemo, useRef, useState } from "react";
import { Animated, PanResponder, View } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

/** Lista vertical de blocos de altura variável, reordenável segurando e
 * arrastando uma alcinha acima de cada bloco. Sem biblioteca nativa nova (só
 * PanResponder/Animated do próprio React Native) — implementado assim de
 * propósito pra não exigir um novo build nativo (EAS) só pra isso.
 *
 * Cada bloco fica com a alcinha um pouco acima; segurar E arrastar ali
 * reordena — toque simples não faz nada, então não conflita com os toques
 * normais dentro do bloco. */
export function DraggableList<T extends string>({
  items,
  onReorder,
  onDragStateChange,
}: {
  items: { id: T; node: React.ReactNode }[];
  onReorder: (newOrder: T[]) => void;
  onDragStateChange?: (dragging: boolean) => void;
}) {
  const order = items.map((i) => i.id);
  const [heights, setHeights] = useState<Record<string, number>>({});
  const [dragId, setDragId] = useState<T | null>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const dragY = useRef(new Animated.Value(0)).current;
  const dragStartIndex = useRef(0);

  const offsets = useMemo(() => {
    let y = 0;
    const map: Record<string, number> = {};
    order.forEach((id) => {
      map[id] = y;
      y += heights[id] ?? 0;
    });
    return map;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, heights]);

  function handleLayout(id: T, h: number) {
    setHeights((prev) => (Math.round(prev[id] ?? 0) === Math.round(h) ? prev : { ...prev, [id]: h }));
  }

  function handleDragStart(id: T) {
    dragStartIndex.current = order.indexOf(id);
    setDragId(id);
    setHoverIndex(dragStartIndex.current);
    dragY.setValue(0);
    onDragStateChange?.(true);
  }

  function handleDragMove(id: T, dy: number) {
    dragY.setValue(dy);
    const draggedH = heights[id] ?? 0;
    const draggedMid = (offsets[id] ?? 0) + dy + draggedH / 2;
    let idx = order.length - 1;
    let acc = 0;
    for (let i = 0; i < order.length; i++) {
      const h = heights[order[i]] ?? 0;
      if (draggedMid < acc + h) {
        idx = i;
        break;
      }
      acc += h;
    }
    setHoverIndex((prev) => (prev === idx ? prev : idx));
  }

  function handleDragEnd() {
    if (dragId != null && hoverIndex != null && hoverIndex !== dragStartIndex.current) {
      const newOrder = [...order];
      const [moved] = newOrder.splice(dragStartIndex.current, 1);
      newOrder.splice(hoverIndex, 0, moved);
      onReorder(newOrder);
    }
    Animated.spring(dragY, { toValue: 0, useNativeDriver: true, friction: 8 }).start();
    setDragId(null);
    setHoverIndex(null);
    onDragStateChange?.(false);
  }

  return (
    <View>
      {items.map((item, idx) => {
        const isDragging = item.id === dragId;
        let shift = 0;
        if (dragId != null && !isDragging && hoverIndex != null) {
          const draggedH = heights[dragId] ?? 0;
          const from = dragStartIndex.current;
          const to = hoverIndex;
          if (from < to && idx > from && idx <= to) shift = -draggedH;
          else if (from > to && idx >= to && idx < from) shift = draggedH;
        }
        return (
          <DraggableRow
            key={item.id}
            onLayout={(h) => handleLayout(item.id, h)}
            liveTranslateY={isDragging ? dragY : undefined}
            shift={shift}
            isDragging={isDragging}
            onDragStart={() => handleDragStart(item.id)}
            onDragMove={(dy) => handleDragMove(item.id, dy)}
            onDragEnd={handleDragEnd}
          >
            {item.node}
          </DraggableRow>
        );
      })}
    </View>
  );
}

function DraggableRow({
  children,
  onLayout,
  liveTranslateY,
  shift,
  isDragging,
  onDragStart,
  onDragMove,
  onDragEnd,
}: {
  children: React.ReactNode;
  onLayout: (height: number) => void;
  liveTranslateY?: Animated.Value;
  shift: number;
  isDragging: boolean;
  onDragStart: () => void;
  onDragMove: (dy: number) => void;
  onDragEnd: () => void;
}) {
  const { colors } = useTheme();
  const localShift = useRef(new Animated.Value(0)).current;
  const scale = useRef(new Animated.Value(1)).current;

  React.useEffect(() => {
    if (!isDragging) {
      Animated.spring(localShift, { toValue: shift, useNativeDriver: true, friction: 9, tension: 60 }).start();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shift, isDragging]);

  // PanResponder.create roda só UMA vez (dentro do useRef) — sem esta
  // indireção por ref, os callbacks (onPanResponderMove etc.) ficariam presos
  // nos onDragStart/onDragMove/onDragEnd da PRIMEIRA renderização pra sempre
  // (closure velha), e o arrastar nunca enxergaria as alturas/ordem atuais.
  const onDragStartRef = useRef(onDragStart);
  const onDragMoveRef = useRef(onDragMove);
  const onDragEndRef = useRef(onDragEnd);
  onDragStartRef.current = onDragStart;
  onDragMoveRef.current = onDragMove;
  onDragEndRef.current = onDragEnd;

  const pan = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: (_, g) => Math.abs(g.dy) > 2 || Math.abs(g.dx) > 2,
      onPanResponderGrant: () => {
        onDragStartRef.current();
        Animated.spring(scale, { toValue: 1.02, useNativeDriver: true }).start();
      },
      onPanResponderMove: (_, g) => onDragMoveRef.current(g.dy),
      onPanResponderRelease: () => {
        Animated.spring(scale, { toValue: 1, useNativeDriver: true }).start();
        onDragEndRef.current();
      },
      onPanResponderTerminate: () => {
        Animated.spring(scale, { toValue: 1, useNativeDriver: true }).start();
        onDragEndRef.current();
      },
    })
  ).current;

  return (
    <Animated.View
      onLayout={(e) => onLayout(e.nativeEvent.layout.height)}
      style={{
        transform: [{ translateY: isDragging ? liveTranslateY! : localShift }, { scale }],
        zIndex: isDragging ? 10 : 0,
        elevation: isDragging ? 10 : 0,
        opacity: isDragging ? 0.96 : 1,
      }}
    >
      {/* Alcinha: segurar e arrastar aqui reordena. Toque simples não faz
          nada — assim não conflita com os toques normais dentro do bloco. */}
      <View {...pan.panHandlers} style={{ alignItems: "center", paddingVertical: 6 }} hitSlop={{ top: 4, bottom: 4 }}>
        <View
          style={{
            width: 40,
            height: 20,
            borderRadius: 10,
            backgroundColor: isDragging ? colors.primary + "26" : colors.surfaceAlt,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Ionicons name="reorder-three" size={16} color={isDragging ? colors.primary : colors.textSecondary} />
        </View>
      </View>
      {children}
    </Animated.View>
  );
}
