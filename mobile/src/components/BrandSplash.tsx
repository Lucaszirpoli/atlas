import React, { useEffect, useRef } from "react";
import { Animated, Easing, Text, View } from "react-native";

import { ATLAS_SLOGAN, AtlasLogo } from "./AtlasLogo";
import { useTheme } from "../theme/ThemeProvider";

/** Quanto tempo a abertura fica na tela DEPOIS que o app já está pronto.
 *
 * Curto o bastante pra nunca virar espera (a marca não vale o tempo de
 * ninguém), longo o bastante pra a animação ser lida como intenção e não como
 * travamento. A abertura NÃO segura o app: ela roda por cima e sai; se o app
 * demorar mais que ela pra carregar, ela espera — quem some por último é ela. */
const ENTRADA_MS = 900;
const PERMANENCIA_MS = 550;
const SAIDA_MS = 380;

/**
 * A abertura da marca — logo ATLAS ao centro, em câmera lenta, com o slogan
 * surgindo embaixo.
 *
 * Existe porque abrir o app era um corte seco: a pessoa tocava no ícone e caía
 * direto na tela, sem nada entre uma coisa e outra. O splash NATIVO (app.json)
 * cobre só o tempo até o JS subir e é uma imagem parada; esta camada continua a
 * partir dele com o MESMO fundo, então a passagem não tem pisca de cor no meio.
 *
 * Roda em TODA abertura — primeira e recorrentes.
 */
export function BrandSplash({ pronto, onDone }: { pronto: boolean; onDone: () => void }) {
  const { colors, type, spacing } = useTheme();

  // Um valor só conduz a cena inteira (0 -> 1): logo e slogan leem posições
  // diferentes dele. Com Animated separados por elemento, cada um chegava no seu
  // tempo e a composição perdia o eixo.
  const entrada = useRef(new Animated.Value(0)).current;
  const saida = useRef(new Animated.Value(0)).current;
  const entrouRef = useRef(false);
  const [entrou, setEntrou] = React.useState(false);

  // 1) A ENTRADA roda sempre, uma vez, assim que a cena monta.
  useEffect(() => {
    Animated.sequence([
      Animated.timing(entrada, {
        toValue: 1,
        duration: ENTRADA_MS,
        // Desacelera no fim: a logo CHEGA em vez de parar de repente. É o que
        // faz o movimento parecer lento sem ser demorado.
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
      Animated.delay(PERMANENCIA_MS),
    ]).start(({ finished }) => {
      if (!finished) return;
      entrouRef.current = true;
      setEntrou(true);
    });
    // Uma vez só: relançar a animação porque o pai re-renderizou faria a
    // abertura recomeçar sozinha no meio.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2) A SAÍDA espera as DUAS coisas: a animação ter terminado e o app estar
  // pronto. Num boot lento (rede ruim verificando a sessão), a abertura ficava
  // e o app aparecia atrás dela; agora ela segura a cena até ter o que revelar,
  // em vez de sair pra um spinner.
  useEffect(() => {
    if (!entrou || !pronto) return;
    Animated.timing(saida, {
      toValue: 1,
      duration: SAIDA_MS,
      easing: Easing.in(Easing.quad),
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (finished) onDone();
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entrou, pronto]);

  const opacidadeDaCena = saida.interpolate({ inputRange: [0, 1], outputRange: [1, 0] });

  return (
    <Animated.View
      pointerEvents="none"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: colors.bg,
        alignItems: "center",
        justifyContent: "center",
        padding: spacing.xl,
        opacity: opacidadeDaCena,
      }}
    >
      <Animated.View
        style={{
          opacity: entrada,
          transform: [
            // Entra levemente MENOR e cresce até o tamanho natural. O contrário
            // (grande encolhendo) lê como o app se afastando da pessoa.
            { scale: entrada.interpolate({ inputRange: [0, 1], outputRange: [0.84, 1] }) },
          ],
        }}
      >
        <AtlasLogo size={84} color={colors.primary} seam={colors.bg} />
      </Animated.View>

      <Animated.Text
        style={[
          type.h1,
          {
            color: colors.textPrimary,
            fontSize: 34,
            letterSpacing: 8,
            fontWeight: "800",
            marginTop: spacing.lg,
            opacity: entrada,
          },
        ]}
      >
        ATLAS
      </Animated.Text>

      {/* O slogan chega DEPOIS da logo, subindo — a marca se apresenta e então
          diz o que faz. Os dois juntos no mesmo instante viram um bloco só e a
          frase passa despercebida. */}
      <Animated.View
        style={{
          opacity: entrada.interpolate({ inputRange: [0, 0.55, 1], outputRange: [0, 0, 1] }),
          transform: [
            { translateY: entrada.interpolate({ inputRange: [0, 1], outputRange: [14, 0] }) },
          ],
        }}
      >
        <Text
          style={[
            type.bodySmall,
            {
              color: colors.textSecondary,
              textAlign: "center",
              marginTop: spacing.sm,
              maxWidth: 300,
              lineHeight: 22,
            },
          ]}
        >
          {ATLAS_SLOGAN}
        </Text>
      </Animated.View>
    </Animated.View>
  );
}
