import * as ImagePicker from "expo-image-picker";
import React, { useEffect, useState } from "react";
import { Alert, Image, ScrollView, Text, TextInput, View } from "react-native";

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
import { OptionButton } from "../../components/OptionButton";
import { useTheme } from "../../theme/ThemeProvider";

const MEASUREMENT_LABELS: Record<MeasurementType, string> = {
  waist: "Cintura",
  hip: "Quadril",
  chest: "Peito",
  arm_left: "Braço esquerdo",
  arm_right: "Braço direito",
  thigh_left: "Coxa esquerda",
  thigh_right: "Coxa direita",
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

    // Nota: sem storage S3/R2 configurado ainda, salvamos a URI local do
    // dispositivo. Quando o upload para Cloudflare R2 for implementado, essa
    // URI vira a URL remota retornada pelo upload.
    await createProgressPhoto(result.assets[0].uri);
    await load();
  }

  return (
    <ScrollView contentContainerStyle={{ padding: spacing.lg, backgroundColor: colors.bg, flexGrow: 1 }}>
      <Text style={[type.h1, { color: colors.textPrimary, marginBottom: spacing.md }]}>
        Medidas e fotos
      </Text>

      <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.sm }]}>
        Nova medida
      </Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap" }}>
        {(Object.keys(MEASUREMENT_LABELS) as MeasurementType[]).map((key) => (
          <View key={key} style={{ marginRight: spacing.xs }}>
            <OptionButton
              label={MEASUREMENT_LABELS[key]}
              selected={selectedType === key}
              onPress={() => setSelectedType(key)}
            />
          </View>
        ))}
      </View>
      <TextInput
        value={valueCm}
        onChangeText={(v) => setValueCm(v.replace(/[^0-9.]/g, ""))}
        placeholder="Valor em cm"
        placeholderTextColor={colors.textSecondary}
        keyboardType="decimal-pad"
        style={[
          type.body,
          {
            color: colors.textPrimary,
            borderWidth: 1,
            borderColor: colors.border,
            borderRadius: radius.button,
            paddingHorizontal: spacing.md,
            height: 44,
            marginVertical: spacing.sm,
            backgroundColor: colors.surface,
          },
        ]}
      />
      <Button title="Registrar medida" onPress={handleAddMeasurement} loading={isSubmitting} />

      <View style={{ marginTop: spacing.lg, marginBottom: spacing.lg }}>
        {measurements.map((m) => (
          <View
            key={m.id}
            style={{ flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.xs }}
          >
            <Text style={[type.bodySmall, { color: colors.textPrimary }]}>
              {MEASUREMENT_LABELS[m.type]}
            </Text>
            <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
              {m.value_cm} cm · {new Date(m.recorded_at).toLocaleDateString("pt-BR")}
            </Text>
          </View>
        ))}
      </View>

      <Text style={[type.h2, { color: colors.textPrimary, marginBottom: spacing.sm }]}>
        Fotos de progresso
      </Text>
      <Button title="Adicionar foto" variant="ghost" onPress={handleAddPhoto} />
      <ScrollView horizontal style={{ marginTop: spacing.sm }}>
        {photos.map((photo) => (
          <View key={photo.id} style={{ marginRight: spacing.sm, alignItems: "center" }}>
            <Image
              source={{ uri: photo.photo_url }}
              style={{ width: 100, height: 130, borderRadius: radius.card }}
            />
            <Text
              style={[type.caption, { color: colors.primary, marginTop: spacing.xs }]}
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
    </ScrollView>
  );
}
