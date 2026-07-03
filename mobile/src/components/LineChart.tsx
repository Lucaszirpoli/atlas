import React from "react";
import { View } from "react-native";
import Svg, { Circle, Path, Line as SvgLine, Text as SvgText } from "react-native-svg";

import { useTheme } from "../theme/ThemeProvider";

export type ChartPoint = { x: number; y: number; label?: string };

type Series = {
  data: ChartPoint[];
  color: string;
  showDots?: boolean;
  dashed?: boolean;
};

/** Gráfico de linha suave e leve (linhas retas entre pontos, sem 3D nem
 * grid pesado — segue a diretriz visual da espec. 7.5). Suporta uma série
 * secundária (ex: média móvel de peso). */
export function LineChart({
  series,
  height = 180,
  yLabelCount = 4,
  formatY = (v: number) => String(Math.round(v)),
}: {
  series: Series[];
  height?: number;
  yLabelCount?: number;
  formatY?: (v: number) => string;
}) {
  const { colors, type } = useTheme();
  const [width, setWidth] = React.useState(0);

  const padLeft = 38;
  const padRight = 12;
  const padTop = 12;
  const padBottom = 22;

  const allPoints = series.flatMap((s) => s.data);
  if (allPoints.length === 0 || width === 0) {
    return <View style={{ height }} onLayout={(e) => setWidth(e.nativeEvent.layout.width)} />;
  }

  const xs = allPoints.map((p) => p.x);
  const ys = allPoints.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  let minY = Math.min(...ys);
  let maxY = Math.max(...ys);
  if (minY === maxY) {
    minY -= 1;
    maxY += 1;
  }
  // folga vertical
  const range = maxY - minY;
  minY -= range * 0.1;
  maxY += range * 0.1;

  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const sx = (x: number) => padLeft + (maxX === minX ? plotW / 2 : ((x - minX) / (maxX - minX)) * plotW);
  const sy = (y: number) => padTop + (1 - (y - minY) / (maxY - minY)) * plotH;

  const yTicks = Array.from({ length: yLabelCount }, (_, i) => minY + ((maxY - minY) * i) / (yLabelCount - 1));

  return (
    <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
      <Svg width={width} height={height}>
        {/* linhas de grade horizontais + rótulos Y */}
        {yTicks.map((ty, i) => (
          <React.Fragment key={i}>
            <SvgLine x1={padLeft} y1={sy(ty)} x2={width - padRight} y2={sy(ty)} stroke={colors.border} strokeWidth={1} />
            <SvgText x={padLeft - 6} y={sy(ty) + 3} fontSize={9} fill={colors.textSecondary} textAnchor="end">
              {formatY(ty)}
            </SvgText>
          </React.Fragment>
        ))}

        {series.map((s, si) => {
          if (s.data.length === 0) return null;
          const d = s.data
            .map((p, i) => `${i === 0 ? "M" : "L"} ${sx(p.x)} ${sy(p.y)}`)
            .join(" ");
          return (
            <React.Fragment key={si}>
              <Path
                d={d}
                stroke={s.color}
                strokeWidth={s.dashed ? 2 : 2.5}
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={s.dashed ? "5 4" : undefined}
              />
              {s.showDots
                ? s.data.map((p, i) => (
                    <Circle key={i} cx={sx(p.x)} cy={sy(p.y)} r={3} fill={colors.surface} stroke={s.color} strokeWidth={2} />
                  ))
                : null}
            </React.Fragment>
          );
        })}
      </Svg>
    </View>
  );
}
