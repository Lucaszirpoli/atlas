import React from "react";
import { useWindowDimensions, View } from "react-native";
import Svg, { Circle, Defs, LinearGradient, Path, Stop, Line as SvgLine, Text as SvgText } from "react-native-svg";

import { useTheme } from "../theme/ThemeProvider";

export type ChartPoint = { x: number; y: number; label?: string };

type Series = {
  data: ChartPoint[];
  color: string;
  showDots?: boolean;
  dashed?: boolean;
  /** Preenche a área embaixo da linha com um gradiente que some perto da
   * base (estilo "gráfico de clima"). Use na série principal. */
  area?: boolean;
};

function defaultFormatX(x: number): string {
  const d = new Date(x);
  return `${d.getDate()}/${d.getMonth() + 1}`;
}

/** Gráfico de linha leve (linhas retas entre pontos, sem 3D nem grid pesado —
 * espec. 7.5). Uma ou mais séries sobrepostas no mesmo plano. */
export function LineChart({
  series,
  height = 200,
  yLabelCount = 3,
  formatY = (v: number) => String(Math.round(v)),
  formatX = defaultFormatX,
  showYAxis = true,
  showXAxis = true,
}: {
  series: Series[];
  height?: number;
  yLabelCount?: number;
  formatY?: (v: number) => string;
  formatX?: (v: number) => string;
  /** Rótulos numéricos no eixo Y — só faz sentido com UMA métrica (com
   * várias, cada uma tem unidade diferente e tudo é normalizado 0-1). */
  showYAxis?: boolean;
  /** Rótulos de data no eixo X. */
  showXAxis?: boolean;
}) {
  const { colors, type } = useTheme();
  const window = useWindowDimensions();
  const [measured, setMeasured] = React.useState(0);

  // Largura de fallback: o gráfico fica dentro de Card(pad) + ScrollView(pad),
  // ~96px de recuo total num celular. Sem isso, enquanto o onLayout não
  // dispara (ou em ambientes headless onde ele nunca dispara) a largura ficava
  // 0 e o gráfico não desenhava. Agora sempre há uma largura sensata.
  const width = measured > 0 ? measured : Math.max(window.width - 96, 240);

  const padLeft = showYAxis ? 36 : 8;
  const padRight = 10;
  const padTop = 12;
  const padBottom = showXAxis ? 22 : 10;

  const allPoints = series.flatMap((s) => s.data);
  if (allPoints.length === 0) {
    return <View style={{ height }} onLayout={(e) => setMeasured(e.nativeEvent.layout.width)} />;
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
  minY -= range * 0.12;
  maxY += range * 0.12;

  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const sx = (x: number) => padLeft + (maxX === minX ? plotW / 2 : ((x - minX) / (maxX - minX)) * plotW);
  const sy = (y: number) => padTop + (1 - (y - minY) / (maxY - minY)) * plotH;

  const yTicks = Array.from({ length: yLabelCount }, (_, i) => minY + ((maxY - minY) * i) / (yLabelCount - 1));

  // Rótulos de data no eixo X: ~4 marcas igualmente espaçadas no tempo.
  const xTickCount = Math.min(4, Math.max(2, Math.round(plotW / 90)));
  const xTicks = Array.from({ length: xTickCount }, (_, i) =>
    xTickCount === 1 ? minX : minX + ((maxX - minX) * i) / (xTickCount - 1)
  );

  return (
    <View onLayout={(e) => setMeasured(e.nativeEvent.layout.width)}>
      <Svg width={width} height={height}>
        <Defs>
          {series.map((s, si) =>
            s.area ? (
              <LinearGradient key={si} id={`${gradId(si)}`} x1="0" y1="0" x2="0" y2="1">
                <Stop offset="0" stopColor={s.color} stopOpacity={0.28} />
                <Stop offset="1" stopColor={s.color} stopOpacity={0} />
              </LinearGradient>
            ) : null
          )}
        </Defs>

        {/* Grade horizontal + rótulos Y (só com uma métrica) */}
        {showYAxis
          ? yTicks.map((ty, i) => (
              <React.Fragment key={`y${i}`}>
                <SvgLine
                  x1={padLeft}
                  y1={sy(ty)}
                  x2={width - padRight}
                  y2={sy(ty)}
                  stroke={colors.border}
                  strokeWidth={1}
                />
                <SvgText x={padLeft - 6} y={sy(ty) + 3} fontSize={9} fill={colors.textSecondary} textAnchor="end">
                  {formatY(ty)}
                </SvgText>
              </React.Fragment>
            ))
          : null}

        {/* Rótulos X (datas) */}
        {showXAxis
          ? xTicks.map((tx, i) => {
              const anchor = i === 0 ? "start" : i === xTicks.length - 1 ? "end" : "middle";
              return (
                <SvgText
                  key={`x${i}`}
                  x={sx(tx)}
                  y={height - 6}
                  fontSize={9}
                  fill={colors.textSecondary}
                  textAnchor={anchor as "start" | "middle" | "end"}
                >
                  {formatX(tx)}
                </SvgText>
              );
            })
          : null}

        {series.map((s, si) => {
          if (s.data.length === 0) return null;
          // Ponto único: só um pontinho (sem linha) — evita "sumir" quando a
          // pessoa só tem um registro daquela métrica.
          if (s.data.length === 1) {
            const p = s.data[0];
            return <Circle key={si} cx={sx(p.x)} cy={sy(p.y)} r={4} fill={s.color} />;
          }
          const d = s.data.map((p, i) => `${i === 0 ? "M" : "L"} ${sx(p.x)} ${sy(p.y)}`).join(" ");
          const areaD = s.area
            ? `${d} L ${sx(s.data[s.data.length - 1].x)} ${padTop + plotH} L ${sx(s.data[0].x)} ${padTop + plotH} Z`
            : null;
          return (
            <React.Fragment key={si}>
              {areaD ? <Path d={areaD} fill={`url(#${gradId(si)})`} stroke="none" /> : null}
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

// Ids de gradiente estáveis por série (não usam Math.random/useId, que
// geram atributos inválidos ou instáveis entre renders na web).
function gradId(index: number): string {
  return `lc-grad-${index}`;
}
