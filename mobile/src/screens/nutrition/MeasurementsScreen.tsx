import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";
import React, { useEffect, useState } from "react";
import { Alert, Image, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";

import { shareProgressPhoto } from "../../api/feed";
import {
  createMeasurement,
  createProgressPhoto,
  listMeasurements,
  listProgressPhotos,
  type BodyMeasurement,
  type MeasurementType,
  type ProgressPhoto,
} from "../../api/measurements";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";
import { persistProgressPhoto, resolveProgressPhotoUri } from "../../utils/photoStorage";

const MEASUREMENT_LABELS: Record<MeasurementType, string> = {
  waist: "Cintura",
  hip: "Quadril",
  chest: "Peito",
  arm_left: "Braço esq.",
  arm_right: "Braço dir.",
  thigh_left: "Coxa esq.",
  thigh_right: "Coxa dir.",
  neck: "Pescoço",
};

export function MeasurementsScreen() {
  const { colors, type, spacing, radius } = useTheme();

  const [measurements, setMeasurements] = useState<BodyMeasurement[]>([]);
  const [photos, setPhotos] = useState<ProgressPhoto[]>([]);
  const [selectedType, setSelectedType] = useState<MeasurementType>("waist");
  const [valueCm, setValueCm] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function load() {
    const [m, p] = await Promise.all([listMeasurements(), listProgressPhotos()]);
    setMeasurements(m);
    setPhotos(p);
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAddMeasurement() {
    const value = Number(valueCm);
    if (!value) {
      Alert.alert("Valor inválido", "Informe a medida em centímetros.");
      return;
    }
    setIsSubmitting(true);
    try {
      await createMeasurement(selectedType, value);
      setValueCm("");
      await load();
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleAddPhoto() {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Permissão necessária", "Precisamos acessar suas fotos para isso.");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({ quality: 0.8 });
    if (result.canceled || !result.assets[0]) return;
    // copia pra pasta permanente do app antes de salvar (a URI do picker é
    // temporária — some quando o sistema limpa o cache).
    const persistedKey = await persistProgressPhoto(result.assets[0].uri);
    await createProgressPhoto(persistedKey);
    await load();
  }

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl }}
      showsVerticalScrollIndicator={false}
    >
      {/* Nova medida */}
      <Card style={{ marginBottom: spacing.lg }}>
        <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.md }]}>Nova medida</Text>
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.xs }}>
          {(Object.keys(MEASUREMENT_LABELS) as MeasurementType[]).map((key) => (
            <OptionButton
              key={key}
              compact
              label={MEASUREMENT_LABELS[key]}
              selected={selectedType === key}
              onPress={() => setSelectedType(key)}
            />
          ))}
        </View>
        <View style={{ flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm, alignItems: "center" }}>
          <TextInput
            value={valueCm}
            onChangeText={(v) => setValueCm(v.replace(/[^0-9.]/g, ""))}
            placeholder="0.0"
            placeholderTextColor={colors.textSecondary}
            keyboardType="decimal-pad"
            style={[
              type.h1,
              {
                flex: 1,
                color: colors.textPrimary,
                borderRadius: radius.button,
                paddingHorizontal: spacing.md,
                height: 56,
                backgroundColor: colors.surfaceAlt,
                textAlign: "center",
              },
            ]}
          />
          <Text style={[type.h2, { color: colors.textSecondary }]}>cm</Text>
          <Button title="Registrar" onPress={handleAddMeasurement} loading={isSubmitting} />
        </View>
      </Card>

      {/* Histórico */}
      {measurements.length > 0 ? (
        <>
          <Text style={[type.caption, { color: colors.textSecondary, marginBottom: spacing.sm, letterSpacing: 1, textTransform: "uppercase" }]}>
            Histórico
          </Text>
          <Card padded={false} style={{ marginBottom: spacing.lg }}>
            {measurements.map((m, i) => (
              <View
                key={m.id}
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: spacing.md,
                  borderTopWidth: i === 0 ? 0 : 1,
                  borderTopColor: colors.border,
                }}
              >
                <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "600" }]}>
                  {MEASUREMENT_LABELS[m.type]}
                </Text>
                <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
                  <Text style={{ color: colors.primary, fontWeight: "700" }}>{m.value_cm} cm</Text>
                  {"  ·  "}
                  {new Date(m.recorded_at).toLocaleDateString("pt-BR")}
                </Text>
              </View>
            ))}
          </Card>
        </>
      ) : null}

      {/* Fotos */}
      <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.sm }}>
        <Text style={[type.caption, { color: colors.textSecondary, letterSpacing: 1, textTransform: "uppercase" }]}>
          Fotos de progresso
        </Text>
        <TouchableOpacity onPress={handleAddPhoto} style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
          <Ionicons name="add-circle" size={18} color={colors.primary} />
          <Text style={[type.caption, { color: colors.primary, fontWeight: "700" }]}>Adicionar</Text>
        </TouchableOpacity>
      </View>
      {photos.length === 0 ? (
        <Card>
          <View style={{ alignItems: "center", paddingVertical: spacing.md }}>
            <Ionicons name="images-outline" size={34} color={colors.textSecondary} />
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.sm, textAlign: "center" }]}>
              Fotos motivam mais que a balança:{"\n"}a mudança visual aparece antes do peso mudar.
            </Text>
          </View>
        </Card>
      ) : (
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {photos.map((photo) => (
            <View key={photo.id} style={{ marginRight: spacing.sm, alignItems: "center" }}>
              <Image
                source={{ uri: resolveProgressPhotoUri(photo.photo_url) }}
                style={{ width: 110, height: 145, borderRadius: radius.card }}
              />
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: 4 }]}>
                {new Date(photo.recorded_at).toLocaleDateString("pt-BR")}
              </Text>
              <Text
                style={[type.caption, { color: colors.primary, fontWeight: "700" }]}
                onPress={async () => {
                  await shareProgressPhoto(photo.id);
                  Alert.alert("Compartilhado", "A foto foi para o seu feed social.");
                }}
              >
                Compartilhar
              </Text>
            </View>
          ))}
        </ScrollView>
      )}
    </ScrollView>
  );
}
