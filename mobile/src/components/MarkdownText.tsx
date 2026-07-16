import React from "react";
import { Text, View, type TextStyle } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

/**
 * Renderiza o markdown simples que a IA usa (## título, **negrito**, *itálico*,
 * `código`, listas com - / 1.). Antes os símbolos apareciam crus na tela ("##
 * Treino A", "**Supino**"), o que além de feio atrapalhava a leitura — a IA
 * estava formatando pra ninguém.
 *
 * É um renderizador PROPOSITALMENTE pequeno: cobre o que a IA realmente usa,
 * sem dependência nova. Nada de HTML/links/imagens — o assistente não gera isso.
 */

type Seg = { text: string; bold?: boolean; italic?: boolean; code?: boolean };

/** Quebra uma linha em pedaços com/sem negrito/itálico/código. */
function parseInline(line: string): Seg[] {
  const segs: Seg[] = [];
  // **negrito** | *itálico* | `código`
  const re = /(\*\*[^*]+\*\*|`[^`]+`|(?<![*\w])\*[^*\n]+\*(?![*\w]))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line)) !== null) {
    if (m.index > last) segs.push({ text: line.slice(last, m.index) });
    const tok = m[0];
    if (tok.startsWith("**")) segs.push({ text: tok.slice(2, -2), bold: true });
    else if (tok.startsWith("`")) segs.push({ text: tok.slice(1, -1), code: true });
    else segs.push({ text: tok.slice(1, -1), italic: true });
    last = m.index + tok.length;
  }
  if (last < line.length) segs.push({ text: line.slice(last) });
  return segs.length ? segs : [{ text: line }];
}

export function MarkdownText({ content, color }: { content: string; color: string }) {
  const { colors, type, spacing } = useTheme();

  const lines = (content ?? "").split("\n");

  return (
    <View>
      {lines.map((raw, i) => {
        const line = raw.trimEnd();

        // Linha em branco = respiro entre blocos
        if (!line.trim()) return <View key={i} style={{ height: spacing.xs }} />;

        // Títulos (#, ##, ###)
        const h = /^(#{1,3})\s+(.*)$/.exec(line);
        if (h) {
          const level = h[1].length;
          const size = level === 1 ? 18 : level === 2 ? 16 : 15;
          return (
            <Text
              key={i}
              style={[
                type.body,
                { color, fontWeight: "800", fontSize: size, marginTop: i === 0 ? 0 : spacing.sm, marginBottom: 2 },
              ]}
            >
              {h[2]}
            </Text>
          );
        }

        // Listas: "- item", "* item", "1. item"
        const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
        const numbered = /^\s*(\d+)[.)]\s+(.*)$/.exec(line);
        if (bullet || numbered) {
          const marker = bullet ? "•" : `${numbered![1]}.`;
          const rest = bullet ? bullet[1] : numbered![2];
          return (
            <View key={i} style={{ flexDirection: "row", marginBottom: 2 }}>
              <Text style={[type.body, { color, marginRight: 6, lineHeight: 21 }]}>{marker}</Text>
              <Text style={[type.body, { color, flex: 1, lineHeight: 21 }]}>
                {parseInline(rest).map((s, j) => (
                  <Text key={j} style={styleFor(s, colors.textSecondary)}>
                    {s.text}
                  </Text>
                ))}
              </Text>
            </View>
          );
        }

        // Parágrafo normal
        return (
          <Text key={i} style={[type.body, { color, lineHeight: 21 }]}>
            {parseInline(line).map((s, j) => (
              <Text key={j} style={styleFor(s, colors.textSecondary)}>
                {s.text}
              </Text>
            ))}
          </Text>
        );
      })}
    </View>
  );
}

function styleFor(s: Seg, codeColor: string): TextStyle {
  if (s.bold) return { fontWeight: "800" };
  if (s.italic) return { fontStyle: "italic" };
  if (s.code) return { fontFamily: "monospace", color: codeColor };
  return {};
}
