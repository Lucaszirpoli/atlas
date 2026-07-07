import React from "react";
import { View } from "react-native";
import Svg, { Circle, Defs, LinearGradient, Path, Stop, Line as SvgLine, Text as SvgText } from "react-native-svg";

import { useTheme } from "../theme/ThemeProvider";

export type ChartPoint = { x: number; y: number; label?: string };

type Series = {
  data: ChartPoint[];
  color: string;
  showDots?: boolean;
  dashed?: boolean;
  /** Preenche a área embaixo da linha com um gradiente (estilo "gráfico de
   * clima") — some perto da base. Use na série principal. */
  area?: boolean;
};

/** Gráfico de linha suave e leve (linhas retas entre pontos, sem 3D nem
 * grid pesado — segue a diretriz visual da espec. 7.5). Suporta uma série
 * secundária (ex: média móvel de peso).
 *
 * `showMinMax`: destaca o ponto mais alto e mais baixo da primeira série
 * com uma linha guia tracejada + rótulo (estilo gráfico de clima/tempo). */
export function LineChart({
  series,
  height = 180,
  yLabelCount = 4,
  formatY = (v: number) => String(Math.round(v)),
  showMinMax = false,
}: {
  series: Series[];
  height?: number;
  yLabelCount?: number;
  formatY?: (v: number) => string;
  showMinMax?: boolean;
}) {
  const { colors, type } = useTheme();
  const [width, setWidth] = React.useState(0);
  const gradientId = React.useId().replace(/:/g, "");

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

  // MIN/MAX da primeira série (estilo gráfico de clima: linha guia tracejada
  // + rótulo no ponto mais alto e mais baixo).
  const primary = series[0]?.data ?? [];
  let minPoint: ChartPoint | null = null;
  let maxPoint: ChartPoint | null = null;
  if (showMinMax && primary.length > 0) {
    minPoint = primary.reduce((a, b) => (b.y < a.y ? b : a), primary[0]);
    maxPoint = primary.reduce((a, b) => (b.y > a.y ? b : a), primary[0]);
  }

  return (
    <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
      <Svg width={width} height={height}>
        <Defs>
          {series.map((s, si) =>
            s.area ? (
              <LinearGradient key={si} id={`${gradientId}-${si}`} x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor={s.color} stopOpacity={0.35} />
                <Stop offset="1" stopColor={s.color} stopOpacity={0} />
              </LinearGradient>
            ) : null
          )}
        </Defs>

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
          const areaD = s.area
            ? `${d} L ${sx(s.data[s.data.length - 1].x)} ${padTop + plotH} L ${sx(s.data[0].x)} ${padTop + plotH} Z`
            : null;
          return (
            <React.Fragment key={si}>
              {areaD ? <Path d={areaD} fill={`url(#${gradientId}-${si})`} stroke="none" /> : null}
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

        {/* Callouts de MIN/MAX — linha guia tracejada horizontal + rótulo */}
        {maxPoint ? (
          <React.Fragment>
            <SvgLine
              x1={padLeft}
              y1={sy(maxPoint.y)}
              x2={width - padRight}
              y2={sy(maxPoint.y)}
              stroke={series[0].color}
              strokeWidth={1}
              strokeDasharray="3 4"
              opacity={0.5}
            />
            <SvgText x={sx(maxPoint.x)} y={sy(maxPoint.y) - 8} fontSize={10} fontWeight="700" fill={series[0].color} textAnchor="middle">
              {formatY(maxPoint.y)}
            </SvgText>
          </React.Fragment>
        ) : null}
        {minPoint && minPoint !== maxPoint ? (
          <React.Fragment>
            <SvgLine
              x1={padLeft}
              y1={sy(minPoint.y)}
              x2={width - padRight}
              y2={sy(minPoint.y)}
              stroke={series[0].color}
              strokeWidth={1}
              strokeDasharray="3 4"
              opacity={0.5}
            />
            <SvgText x={sx(minPoint.x)} y={sy(minPoint.y) + 14} fontSize={10} fontWeight="700" fill={series[0].color} textAnchor="middle">
              {formatY(minPoint.y)}
            </SvgText>
          </React.Fragment>
        ) : null}
      </Svg>
    </View>
  );
}
