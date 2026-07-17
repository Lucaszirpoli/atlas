import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system";
import React, { useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import {
  createRoutinesBulk,
  previewRoutineImport,
  type ImportPreview,
  type ImportedExercise,
} from "../../api/routines";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { useTheme } from "../../theme/ThemeProvider";
import { exercisePickBus } from "./exercisePickBus";

/**
 * Importa as rotinas de outro app (Hevy, Strong, Jefit) a partir do CSV que
 * eles exportam.
 *
 * A tela existe por causa do risco de casar nome errado: "Bench Press
 * (Barbell)" e "Supino reto com barra" não têm quase nenhuma letra em comum, e
 * um palpite errado trocaria o treino da pessoa em silêncio. Então o backend
 * PROPÕE (não grava), aqui a pessoa confere o que ficou duvidoso, e só então
 * salvamos.
 */
export function ImportRoutinesScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();

  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [saving, setSaving] = useState(false);
  const [info, setInfo] = useState<{ title: string; message: string } | null>(null);

  async function escolherArquivo() {
    // Fora do try: se o próprio seletor falhar (ex: permissão do Android
    // negada), a pessoa via a tela travar sem explicação nenhuma — nem esse
    // catch existia antes.
    let res: DocumentPicker.DocumentPickerResult;
    try {
      res = await DocumentPicker.getDocumentAsync({
        // text/comma-separated-values e text/plain entram porque vários apps
        // exportam com o MIME errado; filtrar só por text/csv perde arquivo bom.
        type: ["text/csv", "text/comma-separated-values", "text/plain", "*/*"],
        copyToCacheDirectory: true,
      });
    } catch (err: any) {
      setInfo({
        title: "Não consegui abrir o seletor de arquivo",
        message: String(err?.message ?? err),
      });
      return;
    }
    if (res.canceled || !res.assets?.[0]) return;

    setLoading(true);

    // Ler o arquivo e chamar o servidor eram o MESMO try/catch, com UMA
    // mensagem genérica pros dois — não dava pra saber qual dos dois
    // realmente falhou (a pessoa via "não consegui ler o arquivo" mesmo
    // quando o arquivo tinha sido lido certo e o problema era na rede, ou
    // vice-versa). Agora cada passo tem seu próprio erro, mostrando a causa
    // real em vez de um texto fixo — é o que vai apontar exatamente onde
    // quebra na próxima tentativa.
    let conteudo: string;
    try {
      conteudo = await FileSystem.readAsStringAsync(res.assets[0].uri);
    } catch (err: any) {
      setInfo({
        title: "Não consegui ler o arquivo",
        message: `Erro ao abrir "${res.assets[0].name}": ${String(err?.message ?? err)}`,
      });
      setLoading(false);
      return;
    }
    if (!conteudo.trim()) {
      setInfo({
        title: "Arquivo vazio",
        message: `"${res.assets[0].name}" não tem conteúdo. Exporte de novo no outro app.`,
      });
      setLoading(false);
      return;
    }

    try {
      const p = await previewRoutineImport(conteudo);
      setPreview(p);
    } catch (err: any) {
      setInfo({
        title: "Não consegui enviar pro servidor",
        message:
          err?.response?.data?.detail ??
          `Erro de conexão: ${String(err?.message ?? err)}. Tente de novo.`,
      });
    } finally {
      setLoading(false);
    }
  }

  /** Troca o exercício de uma linha usando o seletor normal do app. */
  function corrigir(rotinaIdx: number, exIdx: number) {
    // O bus guarda UM handler só. Registramos o nosso, e ele se desregistra na
    // primeira escolha — senão o próximo exercício escolhido em qualquer outra
    // tela cairia aqui dentro.
    exercisePickBus.setHandler((ex) => {
      exercisePickBus.setHandler(null);
      setPreview((p) => {
        if (!p) return p;
        const rotinas = p.rotinas.map((r, i) =>
          i !== rotinaIdx
            ? r
            : {
                ...r,
                exercicios: r.exercicios.map((e, j) =>
                  j !== exIdx
                    ? e
                    : { ...e, exercise_id: ex.id, exercise_nome: ex.name, confianca: 1, revisar: false }
                ),
              }
        );
        return { ...p, rotinas };
      });
    });
    navigation.navigate("ExercisePicker");
  }

  async function salvar() {
    if (!preview) return;
    setSaving(true);
    try {
      // Só o que tem par vai. O que a pessoa deixou sem exercício fica de fora
      // — melhor faltar um do que gravar o errado.
      const rotinas = preview.rotinas
        .map((r) => ({
          nome: r.nome,
          exercicios: r.exercicios
            .filter((e) => e.exercise_id != null)
            .map((e) => ({
              exercise_id: e.exercise_id as number,
              target_sets: e.series,
              target_reps_min: e.reps_min,
              target_reps_max: e.reps_max,
              rest_seconds: 90,
            })),
        }))
        .filter((r) => r.exercicios.length > 0);

      if (rotinas.length === 0) {
        setInfo({ title: "Nada pra importar", message: "Nenhum exercício ficou com par." });
        setSaving(false);
        return;
      }
      const res = await createRoutinesBulk({ rotinas });
      setSaving(false);
      setInfo({
        title: "Treinos importados!",
        message: `${res.created} ${res.created === 1 ? "rotina criada" : "rotinas criadas"}. Bom treino!`,
      });
      setPreview(null);
    } catch (err: any) {
      setSaving(false);
      setInfo({
        title: "Não consegui importar",
        message: err?.response?.data?.detail ?? "Tente novamente.",
      });
    }
  }

  // --- Passo 1: escolher o arquivo ------------------------------------------
  if (!preview) {
    return (
      <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg }}>
        <Text style={[type.h1, { color: colors.textPrimary }]}>Importar treinos</Text>
        <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 20 }]}>
          Já treina em outro app? Traga suas rotinas — sem redigitar tudo.
        </Text>

        <Card style={{ marginTop: spacing.lg }}>
          <Text style={[type.h2, { color: colors.textPrimary, fontSize: 15, marginBottom: spacing.sm }]}>
            Como exportar
          </Text>
          <Passo n={1} texto="Hevy: Perfil → Configurações → Exportar dados" />
          <Passo n={2} texto="Strong / Jefit: Configurações → Exportar (CSV)" />
          <Passo n={3} texto="Salve o arquivo no celular e escolha ele aqui" />
        </Card>

        <View style={{ marginTop: spacing.lg }}>
          <Button title="Escolher arquivo CSV" onPress={escolherArquivo} loading={loading} />
        </View>

        <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.md, lineHeight: 18 }]}>
          Trazemos as rotinas (os moldes). O histórico de cargas fica no outro app — aqui você
          recomeça o registro, mas sem perder o treino montado.
        </Text>
        <InfoDialog
          visible={info != null}
          onClose={() => setInfo(null)}
          title={info?.title ?? ""}
          message={info?.message}
        />
      </ScrollView>
    );
  }

  // --- Passo 2: conferir antes de salvar ------------------------------------
  return (
    <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}>
      <Pressable
        onPress={() => setPreview(null)}
        style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.md }}
      >
        <Ionicons name="chevron-back" size={20} color={colors.primary} />
        <Text style={[type.body, { color: colors.primary, fontWeight: "600" }]}>Escolher outro arquivo</Text>
      </Pressable>

      <Text style={[type.h1, { color: colors.textPrimary }]}>Confira antes de salvar</Text>
      <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.xs, lineHeight: 20 }]}>
        {preview.casados} de {preview.total_exercicios} exercícios casaram com certeza.
        {preview.para_revisar + preview.sem_par > 0
          ? ` ${preview.para_revisar + preview.sem_par} precisam do seu olho — toque pra corrigir.`
          : " Tudo certo!"}
      </Text>

      {preview.rotinas.map((r, ri) => (
        <View key={ri} style={{ marginTop: spacing.lg }}>
          <Text style={[type.h2, { color: colors.textPrimary, fontSize: 16, marginBottom: spacing.sm }]}>
            {r.nome}
          </Text>
          {r.exercicios.map((e, ei) => (
            <LinhaExercicio key={ei} ex={e} onPress={() => corrigir(ri, ei)} />
          ))}
        </View>
      ))}

      <View style={{ marginTop: spacing.xl }}>
        <Button title="Importar treinos" onPress={salvar} loading={saving} />
      </View>
      <InfoDialog
        visible={info != null}
        onClose={() => {
          setInfo(null);
          if (info?.title === "Treinos importados!") navigation.goBack();
        }}
        title={info?.title ?? ""}
        message={info?.message}
      />
    </ScrollView>
  );
}

function Passo({ n, texto }: { n: number; texto: string }) {
  const { colors, type, spacing } = useTheme();
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-start", marginBottom: spacing.xs }}>
      <Text style={[type.caption, { color: colors.primary, fontWeight: "700", width: 16 }]}>{n}.</Text>
      <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1, lineHeight: 19 }]}>{texto}</Text>
    </View>
  );
}

/** Uma linha da conferência. O que casou com certeza fica discreto; o duvidoso
 *  e o sem par chamam atenção — é onde o erro se esconderia. */
function LinhaExercicio({ ex, onPress }: { ex: ImportedExercise; onPress: () => void }) {
  const { colors, type, spacing, radius } = useTheme();
  const semPar = ex.exercise_id == null;
  const atencao = semPar || ex.revisar;
  return (
    <Pressable
      onPress={onPress}
      style={{
        flexDirection: "row",
        alignItems: "center",
        backgroundColor: colors.surface,
        borderRadius: radius.button,
        borderWidth: 1,
        borderColor: atencao ? colors.warning : colors.border,
        padding: spacing.md,
        marginBottom: spacing.sm,
      }}
    >
      <Ionicons
        name={semPar ? "help-circle" : atencao ? "alert-circle" : "checkmark-circle"}
        size={20}
        color={semPar || atencao ? colors.warning : colors.primary}
        style={{ marginRight: spacing.sm }}
      />
      <View style={{ flex: 1 }}>
        <Text style={[type.bodySmall, { color: colors.textSecondary }]} numberOfLines={1}>
          {ex.nome_original}
        </Text>
        <Text style={[type.body, { color: semPar ? colors.warning : colors.textPrimary, fontWeight: "600" }]} numberOfLines={1}>
          {semPar ? "Escolher exercício" : ex.exercise_nome}
        </Text>
        <Text style={[type.caption, { color: colors.textSecondary, marginTop: 1 }]}>
          {ex.series}x{ex.reps_max ? `${ex.reps_min}-${ex.reps_max}` : ex.reps_min}
        </Text>
      </View>
      <Ionicons name="swap-horizontal" size={18} color={colors.textSecondary} />
    </Pressable>
  );
}
