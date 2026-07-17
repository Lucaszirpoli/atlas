import React from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";

/**
 * Rede de segurança de último recurso. Sem isto, qualquer erro de render não
 * capturado desmontava a árvore INTEIRA do React e deixava a tela BRANCA —
 * sem tema, sem nada, sem pista da causa (foi o que um amigo do usuário viu
 * ao criar conta nova). Um ErrorBoundary transforma esse "branco misterioso"
 * numa mensagem legível com o erro real, e mantém o app utilizável.
 *
 * Precisa ser classe: só componentes de classe têm getDerivedStateFromError /
 * componentDidCatch. E precisa ser AUTOSSUFICIENTE em estilo (cores fixas, sem
 * useTheme) — se o ThemeProvider for justamente o que quebrou, um boundary que
 * depende dele quebraria junto.
 */
type Props = { children: React.ReactNode };
type State = { erro: Error | null };

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { erro: null };

  static getDerivedStateFromError(erro: Error): State {
    return { erro };
  }

  componentDidCatch(erro: Error, info: React.ErrorInfo) {
    // Fica no log do dispositivo (adb logcat / console do dev client) além da
    // tela — útil quando dá pra plugar o aparelho.
    console.error("ErrorBoundary capturou:", erro, info.componentStack);
  }

  render() {
    const { erro } = this.state;
    if (!erro) return this.props.children;

    return (
      <View style={{ flex: 1, backgroundColor: "#0A0A0B", padding: 24, justifyContent: "center" }}>
        <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center" }}>
          <Text style={{ color: "#FF6B2C", fontSize: 22, fontWeight: "700", marginBottom: 8 }}>
            Algo quebrou nesta tela
          </Text>
          <Text style={{ color: "#AAA", fontSize: 14, marginBottom: 16, lineHeight: 20 }}>
            O app não fechou — mas esta parte teve um erro. Manda esse texto pro suporte que a gente
            corrige rápido:
          </Text>
          <View style={{ backgroundColor: "#1A1A1C", borderRadius: 10, padding: 14, marginBottom: 20 }}>
            <Text style={{ color: "#FF8A5C", fontSize: 13, fontFamily: "monospace" }}>
              {erro.name}: {erro.message}
            </Text>
          </View>
          <TouchableOpacity
            onPress={() => this.setState({ erro: null })}
            style={{
              backgroundColor: "#FF6B2C",
              borderRadius: 999,
              paddingVertical: 14,
              alignItems: "center",
            }}
          >
            <Text style={{ color: "#0A0A0B", fontWeight: "700", fontSize: 16 }}>Tentar de novo</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>
    );
  }
}
