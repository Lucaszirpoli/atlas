import { Ionicons } from "@expo/vector-icons";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useNavigation } from "@react-navigation/native";
import React, { useCallback, useEffect, useState } from "react";
import { ScrollView, Text, TouchableOpacity, View } from "react-native";

import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { useAuth } from "../../context/AuthContext";
import { voltarPara } from "../../navigation/voltarPara";
import { useTheme } from "../../theme/ThemeProvider";

/**
 * COMO USAR O ATLAS — o guia que faltava.
 *
 * O app tem muita coisa (dieta, treino, sono, peso, social, coach) e nada disso
 * se apresenta sozinho: quem abre pela primeira vez vê números e botões sem
 * saber por onde começar nem o que o produto promete. Este guia é a resposta —
 * e é uma TELA, não um texto: cada capítulo abre, explica o passo a passo com o
 * nome dos botões de verdade, e tem um atalho que leva pra tela onde aquilo
 * acontece. Ler e fazer no mesmo lugar.
 *
 * Duas decisões que valem registrar:
 *
 * 1. **Free vê o que o Pro faz.** Cada capítulo mostra os dois lados: o que dá
 *    pra fazer no plano gratuito (que é completo de propósito, regra 1 do
 *    projeto) e o que o coach faz por você no Pro. Não é pegadinha nem muro:
 *    é a diferença explicada em cima de uma tarefa concreta que a pessoa
 *    acabou de aprender a fazer.
 * 2. **O progresso fica no APARELHO.** Quais capítulos foram lidos é
 *    preferência de leitura, não dado de saúde — não precisa de tabela nem de
 *    sincronizar (mesma decisão do layout da home).
 */

const CHAVE_LIDOS = "@appfit/guia_capitulos_lidos";

/** O atalho do capítulo. Recebe `isPro` porque o mesmo assunto mora em lugares
 * diferentes nos dois planos — mandar quem é Free pra uma tela que só existe no
 * Pro seria um beco sem saída dentro do guia que existe pra tirar a pessoa do
 * beco sem saída. */
type Acao = {
  rotulo: string | ((isPro: boolean) => string);
  ir: (navegar: (tela: string, params?: object) => void, isPro: boolean) => void;
};

type Capitulo = {
  id: string;
  icone: keyof typeof Ionicons.glyphMap;
  cor: "primary" | "nutrition" | "training" | "sleep" | "social" | "secondary";
  titulo: string;
  resumo: string;
  /** O passo a passo com o NOME dos botões de verdade — é o que transforma
   * "existe uma tela de dieta" em "eu sei registrar meu almoço". */
  passos: string[];
  /** O que já é seu, de graça. */
  free: string[];
  /** O que o coach faz por você no Pro. */
  pro: string[];
  acao?: Acao;
};

const CAPITULOS: Capitulo[] = [
  {
    id: "visao",
    icone: "compass",
    cor: "primary",
    titulo: "Como o Atlas funciona",
    resumo:
      "Você registra o que fez; o app vira números; o coach lê esses números e ajusta seu plano. É esse ciclo o produto inteiro.",
    passos: [
      "Registre o básico do dia: o que comeu, o treino que fez, o peso e a noite de sono.",
      "Cada registro alimenta os gráficos e as médias — nada aqui é chute, tudo sai do que você anotou.",
      "Com o Pro, o coach lê essas médias toda semana e mexe no seu treino e nas suas calorias por causa delas.",
      "Quanto mais dias seguidos você registra, mais o app acerta — ele aprende o SEU gasto e o SEU ritmo.",
    ],
    free: [
      "Todos os registros e todos os gráficos",
      "Nenhum limite de tempo e nenhuma tela travada por anúncio",
    ],
    pro: [
      "O coach transforma os registros em decisões: carga, volume, calorias",
      "Ele te diz o que mudou e por quê — e dá pra desfazer",
    ],
  },
  {
    id: "objetivo",
    icone: "flag",
    cor: "primary",
    titulo: "Comece pelo objetivo",
    resumo:
      "Antes de registrar qualquer coisa, diga pra onde você quer ir. É daí que saem suas calorias e o desenho do treino.",
    passos: [
      "No Free: aba Dieta › toque no card de calorias › defina sua meta (automática pelos seus dados ou manual).",
      "No Pro: aba Objetivo › responda o questionário de 8 etapas (leva uns 3 minutos, tudo em toques).",
      "O Pro monta na hora: treino da semana, metas de caloria e macro, dieta em PDF e periodização.",
      "Mudou de ideia? Objetivo › 'Alterar meu objetivo' troca só o objetivo, sem refazer o questionário.",
    ],
    free: [
      "Meta de calorias e macros, automática ou manual",
      "Peso-alvo e acompanhamento do ritmo",
    ],
    pro: [
      "Questionário de 8 etapas vira um plano completo, gerado de uma vez",
      "Trocar de objetivo não vira a chave de uma vez: o coach caminha até a meta nova em degraus",
      "Histórico de versões do plano — dá pra ver o que mudou em cada uma",
    ],
    acao: {
      rotulo: (isPro) => (isPro ? "Abrir meu objetivo" : "Definir minha meta"),
      ir: (navegar, isPro) =>
        isPro
          ? navegar("Home", { section: "objetivo" })
          : navegar("NutritionModule", { screen: "GoalSettings" }),
    },
  },
  {
    id: "dieta",
    icone: "restaurant-outline",
    cor: "nutrition",
    titulo: "Dieta: registrar o que você come",
    resumo:
      "O diário do dia, refeição por refeição. A base de alimentos é brasileira (TACO) e ainda busca produtos de marca pelo nome ou pelo código de barras.",
    passos: [
      "Aba Dieta › toque no + da refeição (café, almoço, ceia...).",
      "Busque o alimento e MARQUE o quadradinho de quantos quiser — dá pra montar o prato inteiro de uma vez.",
      "Toque no alimento pra escolher a quantidade em gramas ou em medida caseira ('2 fatias', '1 colher de servir').",
      "Toque em 'Adicionar' na barra de baixo: entra tudo junto na refeição.",
      "Errou a quantidade? O lápis ao lado do alimento corrige; a lixeira remove.",
      "Repetiu o mesmo prato? Marque os itens e use 'Salvar receita' — na próxima é um toque só.",
    ],
    free: [
      "Base TACO + produtos de marca e código de barras",
      "Medidas caseiras, receitas salvas, dietas prontas e água",
      "Histórico de qualquer dia — dá pra corrigir dias passados",
    ],
    pro: [
      "Uma dieta montada pro SEU objetivo, respeitando restrições e o que você não come",
      "Cardápio em PDF pra levar ao mercado",
      "Registrar refeição por foto",
      "Suas calorias são reajustadas sozinhas quando o peso não anda como devia",
    ],
    acao: { rotulo: "Abrir a Dieta", ir: (navegar) => navegar("NutritionModule") },
  },
  {
    id: "treino",
    icone: "barbell-outline",
    cor: "training",
    titulo: "Treino: montar e executar",
    resumo:
      "Rotina é o molde que você guarda. Sessão é o treino de verdade, com os pesos que você pegou naquele dia — os dois são coisas diferentes aqui.",
    passos: [
      "Aba Treino › 'Nova rotina' pra montar do zero, ou 'Importar treino' se você já tem uma no Hevy ou no Strong.",
      "Na hora de treinar, toque no card pra ver a prévia (exercícios e os pesos da última vez) e depois em 'Treinar agora'.",
      "Peso e reps já vêm preenchidos com o que você fez da última vez — normalmente é só confirmar no ✓.",
      "Cada série tem uma letra: A = aquecimento, P = preparatória, T = série de trabalho, F = até a falha.",
      "Marcar RIR 0 (nenhuma repetição na reserva) já transforma a série em F sozinho.",
      "O ✓ registra a série e começa o descanso. No fim, 'Concluir treino' guarda tudo no histórico.",
    ],
    free: [
      "Rotinas ilimitadas, com séries, reps e descanso do seu jeito",
      "Execução completa, cronômetro de descanso e histórico",
      "Importar do Hevy/Strong e biblioteca de exercícios com imagem",
    ],
    pro: [
      "O coach monta sua semana inteira — divisão, exercícios, séries e reps — pelo seu equipamento, tempo e prioridades",
      "Ele sobe a carga quando VOCÊ está pronto, não no chute",
      "Troca um exercício que você não curtiu por outro do mesmo papel",
      "Semana de alívio (deload) na hora certa, técnicas avançadas quando cabem",
    ],
    acao: { rotulo: "Abrir o Treino", ir: (navegar) => navegar("TrainingModule") },
  },
  {
    id: "corpo",
    icone: "scale-outline",
    cor: "sleep",
    titulo: "Peso, medidas e sono",
    resumo:
      "O peso de um dia não quer dizer quase nada; a tendência de duas semanas diz tudo. E o sono é o que decide se o treino vira resultado.",
    passos: [
      "Peso: registre sempre no mesmo horário — de manhã, depois do banheiro, é o mais estável.",
      "Na mesma tela dá pra guardar medidas (cintura, braço...) e fotos de progresso.",
      "Sono: anote a hora que deitou e que levantou, e como foi a noite.",
      "Não precisa ser todo dia pra funcionar, mas quanto mais constante, mais o app enxerga o seu padrão.",
    ],
    free: ["Peso, medidas e fotos", "Registro de sono e gráficos de evolução"],
    pro: [
      "Média robusta em vez do número cru — o coach ignora o pico de sal do fim de semana",
      "Cruzamento sono × fome do dia seguinte, e sono × desempenho no treino",
      "Aviso quando seu ritmo de ganho/perda sai do que o objetivo pede",
    ],
    acao: { rotulo: "Registrar meu peso", ir: (navegar) => navegar("Weight") },
  },
  {
    id: "social",
    icone: "people-outline",
    cor: "social",
    titulo: "Amigos e desafios",
    resumo: "A parte que faz voltar amanhã: alguém vendo, e uma disputa boba pra não perder o dia.",
    passos: [
      "Home › 'Amigos e feed' pra seguir quem você conhece e ver o que rolou.",
      "Home › 'Desafios' pra entrar numa disputa (dias treinados, água, constância...).",
      "Você controla o que aparece pros outros nas configurações de privacidade.",
    ],
    free: ["Amigos, feed e todos os desafios"],
    pro: ["Nada aqui é pago — a parte social é igual pros dois planos"],
    acao: { rotulo: "Ver amigos e desafios", ir: (navegar) => navegar("Social") },
  },
  {
    id: "coach",
    icone: "sparkles",
    cor: "secondary",
    titulo: "O coach (Pro)",
    resumo:
      "É o que o Pro compra: um treinador que lê seus dados toda semana, decide o que mudar e explica por quê — em português, sem jargão.",
    passos: [
      "A home vira o painel dele: 'Missões da semana' é o que precisa de atenção agora.",
      "Cada ajuste vem com o motivo e um botão de desfazer — nada muda no seu plano sem você ver.",
      "'O que eu aprendi com você' mostra os números que ele mediu em VOCÊ: seu gasto real, seu ritmo, quanto treino você aguenta.",
      "'Pergunte ao coach' é o chat: dúvida de treino, dieta, sono ou do próprio plano.",
    ],
    free: [
      "O app manual inteiro continua funcionando sem isto — o Pro adiciona, não destrava o básico",
    ],
    pro: [
      "Plano completo gerado e mantido pra você",
      "Análises semanais e cruzamentos dos seus dados",
      "Chat ilimitado com o coach e registro de refeição por foto",
    ],
    acao: {
      rotulo: (isPro) => (isPro ? "Falar com o coach" : "Ver o que o Pro faz"),
      ir: (navegar, isPro) => (isPro ? navegar("CoachChat") : navegar("Paywall")),
    },
  },
];

export function GuiaScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();
  const isPro = user?.plan === "pro";

  const [aberto, setAberto] = useState<string | null>(CAPITULOS[0].id);
  const [lidos, setLidos] = useState<string[]>([]);

  useEffect(() => {
    AsyncStorage.getItem(CHAVE_LIDOS)
      .then((cru) => {
        if (!cru) return;
        const salvo = JSON.parse(cru);
        if (Array.isArray(salvo)) setLidos(salvo.filter((x) => typeof x === "string"));
      })
      .catch(() => {});
  }, []);

  const salvar = useCallback((proximos: string[]) => {
    setLidos(proximos);
    AsyncStorage.setItem(CHAVE_LIDOS, JSON.stringify(proximos)).catch(() => {});
  }, []);

  function alternarLido(id: string) {
    salvar(lidos.includes(id) ? lidos.filter((x) => x !== id) : [...lidos, id]);
  }

  /** Abre a tela do módulo a partir do guia. `voltarPara` e não `navigate`: no
   * React Navigation 7 o navigate EMPILHA, e sair do guia pra Dieta e voltar
   * deixaria duas Dietas na pilha (ver navigation/voltarPara.ts). */
  function navegar(tela: string, params?: object) {
    voltarPara(navigation, tela, params, true);
  }

  const corDe = (c: Capitulo["cor"]) =>
    c === "nutrition"
      ? colors.moduleNutrition
      : c === "training"
      ? colors.moduleTraining
      : c === "sleep"
      ? colors.moduleSleep
      : c === "social"
      ? colors.moduleSocial
      : c === "secondary"
      ? colors.secondary
      : colors.primary;

  const total = CAPITULOS.length;
  const feitos = CAPITULOS.filter((c) => lidos.includes(c.id)).length;

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {/* Abertura: o que o app é, em duas linhas. Quem chegou aqui perdido
          precisa da resposta antes de qualquer capítulo. */}
      <Card accent={colors.primary} style={{ marginBottom: spacing.md }}>
        <View
          style={{
            width: 48, height: 48, borderRadius: 16,
            backgroundColor: colors.primary + "1F",
            alignItems: "center", justifyContent: "center", marginBottom: spacing.sm,
          }}
        >
          <Ionicons name="book" size={24} color={colors.primary} />
        </View>
        <Text style={[type.h1, { color: colors.textPrimary, fontSize: 23 }]}>Como usar o Atlas</Text>
        <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 6, lineHeight: 21 }]}>
          Um app só pra treino, dieta, sono, peso e a turma que treina com você. Aqui embaixo, cada
          parte explicada com o passo a passo de verdade — e um atalho pra fazer agora.
        </Text>

        {/* Progresso da leitura: o guia também tem uma sensação de avanço. */}
        <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.md }}>
          <View style={{ flex: 1, height: 7, borderRadius: 4, backgroundColor: colors.surfaceAlt, overflow: "hidden" }}>
            <View
              style={{
                width: `${(feitos / total) * 100}%`,
                height: "100%",
                backgroundColor: colors.secondary,
              }}
            />
          </View>
          <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "700" }]}>
            {feitos}/{total}
          </Text>
        </View>
        {feitos === total ? (
          <Text style={[type.caption, { color: colors.success, fontWeight: "700", marginTop: 6 }]}>
            Guia completo — agora é registrar.
          </Text>
        ) : null}
      </Card>

      {CAPITULOS.map((c, i) => {
        const cor = corDe(c.cor);
        const abertoAgora = aberto === c.id;
        const lido = lidos.includes(c.id);
        return (
          <Card key={c.id} style={{ marginBottom: spacing.sm }} padded={false}>
            <TouchableOpacity
              activeOpacity={0.8}
              onPress={() => setAberto(abertoAgora ? null : c.id)}
              style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md }}
            >
              <View
                style={{
                  width: 40, height: 40, borderRadius: 13,
                  backgroundColor: cor + "1F",
                  alignItems: "center", justifyContent: "center",
                }}
              >
                <Ionicons name={c.icone} size={20} color={cor} />
              </View>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  <Text style={[type.caption, { color: colors.textSecondary, fontWeight: "800" }]}>
                    {i + 1}
                  </Text>
                  <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700", flex: 1 }]} numberOfLines={2}>
                    {c.titulo}
                  </Text>
                </View>
                {!abertoAgora ? (
                  <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2 }]} numberOfLines={2}>
                    {c.resumo}
                  </Text>
                ) : null}
              </View>
              {lido ? (
                <Ionicons name="checkmark-circle" size={19} color={colors.success} />
              ) : null}
              <Ionicons
                name={abertoAgora ? "chevron-up" : "chevron-down"}
                size={18}
                color={colors.textSecondary}
              />
            </TouchableOpacity>

            {abertoAgora ? (
              <View style={{ paddingHorizontal: spacing.md, paddingBottom: spacing.md }}>
                <Text style={[type.bodySmall, { color: colors.textSecondary, lineHeight: 21, marginBottom: spacing.md }]}>
                  {c.resumo}
                </Text>

                {/* Passo a passo com o nome dos botões de verdade. */}
                {c.passos.map((p, idx) => (
                  <View key={idx} style={{ flexDirection: "row", gap: 10, marginBottom: spacing.sm }}>
                    <View
                      style={{
                        width: 22, height: 22, borderRadius: 11,
                        backgroundColor: cor + "1F",
                        alignItems: "center", justifyContent: "center", marginTop: 1,
                      }}
                    >
                      <Text style={[type.caption, { color: cor, fontWeight: "800", fontSize: 11 }]}>{idx + 1}</Text>
                    </View>
                    <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1, lineHeight: 21 }]}>{p}</Text>
                  </View>
                ))}

                {/* Os dois planos, lado a lado. Pro Free isto é o convite; pro
                    Pro é o lembrete do que ele já tem funcionando. */}
                <View style={{ gap: spacing.sm, marginTop: spacing.sm }}>
                  <BlocoPlano
                    titulo={isPro ? "Sempre disponível" : "No seu plano (Free)"}
                    icone="checkmark-circle"
                    cor={colors.success}
                    itens={c.free}
                  />
                  <BlocoPlano
                    titulo={isPro ? "O que o coach faz por você" : "Com o ATLAS Pro"}
                    icone="sparkles"
                    cor={colors.primary}
                    itens={c.pro}
                    destaque={!isPro}
                  />
                </View>

                <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.md }}>
                  {c.acao ? (
                    <View style={{ flex: 1 }}>
                      <Button
                        title={typeof c.acao.rotulo === "function" ? c.acao.rotulo(isPro) : c.acao.rotulo}
                        variant="secondary"
                        compact
                        onPress={() => c.acao!.ir(navegar, isPro)}
                      />
                    </View>
                  ) : null}
                  <View style={{ flex: 1 }}>
                    <Button
                      title={lido ? "Lido ✓" : "Marcar como lido"}
                      variant="ghost"
                      compact
                      onPress={() => alternarLido(c.id)}
                    />
                  </View>
                </View>
              </View>
            ) : null}
          </Card>
        );
      })}

      {/* Convite ao Pro — só pra quem é Free, e só depois de ele ter visto o
          que o app já faz de graça. Vender antes de entregar é o caminho curto
          pra desinstalação. */}
      {!isPro ? (
        <TouchableOpacity
          activeOpacity={0.9}
          onPress={() => navigation.navigate("Paywall")}
          style={{
            flexDirection: "row", alignItems: "center", gap: spacing.md,
            backgroundColor: colors.primary + "14",
            borderWidth: 1, borderColor: colors.primary + "40",
            borderRadius: radius.card, padding: spacing.md, marginTop: spacing.sm,
          }}
        >
          <View
            style={{
              width: 42, height: 42, borderRadius: 14,
              backgroundColor: colors.primary + "22",
              alignItems: "center", justifyContent: "center",
            }}
          >
            <Ionicons name="sparkles" size={21} color={colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={[type.body, { color: colors.textPrimary, fontWeight: "800" }]}>Conhecer o ATLAS Pro</Text>
            <Text style={[type.caption, { color: colors.textSecondary, marginTop: 2, lineHeight: 17 }]}>
              Todo o app manual continua de graça. O Pro é o coach que lê seus números e mexe no plano
              por você.
            </Text>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
        </TouchableOpacity>
      ) : null}

      <Text
        style={[
          type.caption,
          { color: colors.textSecondary, textAlign: "center", marginTop: spacing.lg, lineHeight: 17 },
        ]}
      >
        Este guia fica sempre aqui: Início › Explorar › Como usar.{"\n"}
        O Atlas não substitui acompanhamento médico ou nutricional.
      </Text>
    </ScrollView>
  );
}

/** Uma lista de itens de um plano (Free ou Pro), com marcador colorido. */
function BlocoPlano({
  titulo,
  icone,
  cor,
  itens,
  destaque,
}: {
  titulo: string;
  icone: keyof typeof Ionicons.glyphMap;
  cor: string;
  itens: string[];
  destaque?: boolean;
}) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <View
      style={{
        backgroundColor: destaque ? cor + "12" : colors.surfaceAlt,
        borderWidth: destaque ? 1 : 0,
        borderColor: cor + "33",
        borderRadius: radius.card,
        padding: spacing.sm,
      }}
    >
      <View style={{ flexDirection: "row", alignItems: "center", gap: 6, marginBottom: 6 }}>
        <Ionicons name={icone} size={14} color={cor} />
        <Text style={[type.caption, { color: cor, fontWeight: "800", letterSpacing: 0.3 }]}>
          {titulo.toUpperCase()}
        </Text>
      </View>
      {itens.map((it, i) => (
        <View key={i} style={{ flexDirection: "row", gap: 7, marginTop: i === 0 ? 0 : 5 }}>
          <Text style={[type.caption, { color: cor }]}>•</Text>
          <Text style={[type.caption, { color: colors.textPrimary, flex: 1, lineHeight: 17 }]}>{it}</Text>
        </View>
      ))}
    </View>
  );
}
