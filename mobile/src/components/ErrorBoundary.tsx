import React from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";

import { limparUltimoCrash, lerUltimoCrash } from "../utils/crashLog";

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
type State = { erro: Error | null; crashAnterior: string | null };

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { erro: null, crashAnterior: null };

  static getDerivedStateFromError(erro: Error): State {
    return { erro, crashAnterior: null };
  }

  componentDidMount() {
    // Um crash NATIVO/async da sessão anterior (que o boundary não pega em
    // tempo real) foi gravado pelo crashLog. Mostra agora, na abertura seguinte
    // — é o que revela a causa da tela branca sem precisar plugar o aparelho.
    lerUltimoCrash().then((c) => {
      if (c) this.setState({ crashAnterior: `${c.mensagem}\n\n(em ${c.quando})` });
    });
  }

  componentDidCatch(erro: Error, info: React.ErrorInfo) {
    console.error("ErrorBoundary capturou:", erro, info.componentStack);
  }

  render() {
    const { erro, crashAnterior } = this.state;
    // Esta tela é a rede de segurança de TUDO — ela existe justamente pra
    // aparecer quando algo abaixo dela quebrou, então ela não pode depender do
    // ThemeProvider (que pode ser exatamente o que quebrou). As cores são as do
    // tema escuro, copiadas na mão de propósito. Se a paleta mudar, mudar aqui
    // também: ficar pra trás é como ela continuou laranja depois da identidade
    // nova, e um erro fora da marca parece um app de outra pessoa.
    const C = {
      bg: "#081020",
      surface: "#1B2233",
      accent: "#4F7CFF",
      textMuted: "#94A3B8",
      code: "#89A6FF",
      onAccent: "#FFFFFF",
    };

    // Crash da sessão passada (nativo/async): mostra por cima, mas deixa
    // continuar pro app — pode ter sido pontual.
    if (crashAnterior && !erro) {
      return (
        <View style={{ flex: 1, backgroundColor: C.bg, padding: 24, justifyContent: "center" }}>
          <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center" }}>
            <Text style={{ color: C.accent, fontSize: 22, fontWeight: "700", marginBottom: 8 }}>
              O app fechou sozinho da última vez
            </Text>
            <Text style={{ color: C.textMuted, fontSize: 14, marginBottom: 16, lineHeight: 20 }}>
              Guardamos o que aconteceu. Manda esse texto pro suporte:
            </Text>
            <View style={{ backgroundColor: C.surface, borderRadius: 10, padding: 14, marginBottom: 20 }}>
              <Text style={{ color: C.code, fontSize: 12, fontFamily: "monospace" }}>{crashAnterior}</Text>
            </View>
            <TouchableOpacity
              onPress={() => {
                limparUltimoCrash();
                this.setState({ crashAnterior: null });
              }}
              style={{ backgroundColor: C.accent, borderRadius: 999, paddingVertical: 14, alignItems: "center" }}
            >
              <Text style={{ color: C.onAccent, fontWeight: "700", fontSize: 16 }}>Continuar</Text>
            </TouchableOpacity>
          </ScrollView>
        </View>
      );
    }

    if (!erro) return this.props.children;

    return (
      <View style={{ flex: 1, backgroundColor: C.bg, padding: 24, justifyContent: "center" }}>
        <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: "center" }}>
          <Text style={{ color: C.accent, fontSize: 22, fontWeight: "700", marginBottom: 8 }}>
            Algo quebrou nesta tela
          </Text>
          <Text style={{ color: C.textMuted, fontSize: 14, marginBottom: 16, lineHeight: 20 }}>
            O app não fechou — mas esta parte teve um erro. Manda esse texto pro suporte que a gente
            corrige rápido:
          </Text>
          <View style={{ backgroundColor: C.surface, borderRadius: 10, padding: 14, marginBottom: 20 }}>
            <Text style={{ color: C.code, fontSize: 13, fontFamily: "monospace" }}>
              {erro.name}: {erro.message}
            </Text>
          </View>
          <TouchableOpacity
            onPress={() => this.setState({ erro: null })}
            style={{
              backgroundColor: C.accent,
              borderRadius: 999,
              paddingVertical: 14,
              alignItems: "center",
            }}
          >
            <Text style={{ color: C.onAccent, fontWeight: "700", fontSize: 16 }}>Tentar de novo</Text>
          </TouchableOpacity>
        </ScrollView>
      </View>
    );
  }
}
