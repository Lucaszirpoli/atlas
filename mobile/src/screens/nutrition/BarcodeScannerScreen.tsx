import { CameraView, useCameraPermissions } from "expo-camera";
import { useNavigation, useRoute } from "@react-navigation/native";
import React, { useState } from "react";
import { Alert, Text, View } from "react-native";

import { getFoodByBarcode } from "../../api/foods";
import { Button } from "../../components/Button";
import { useTheme } from "../../theme/ThemeProvider";

export function BarcodeScannerScreen() {
  const { colors, type, spacing } = useTheme();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { categoryId } = route.params ?? {};

  const [permission, requestPermission] = useCameraPermissions();
  const [isProcessing, setIsProcessing] = useState(false);

  async function handleScanned({ data }: { data: string }) {
    if (isProcessing) return;
    setIsProcessing(true);
    try {
      const food = await getFoodByBarcode(data);
      if (!food) {
        Alert.alert(
          "Produto não encontrado",
          "Não achamos esse código de barras. Você pode cadastrá-lo manualmente buscando pelo nome.",
          [{ text: "OK", onPress: () => navigation.goBack() }]
        );
        return;
      }
      navigation.navigate("AddFood", { categoryId, barcodeResult: food });
    } finally {
      setIsProcessing(false);
    }
  }

  if (!permission) {
    return <View style={{ flex: 1, backgroundColor: colors.bg }} />;
  }

  if (!permission.granted) {
    return (
      <View
        style={{
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          padding: spacing.lg,
          backgroundColor: colors.bg,
        }}
      >
        <Text style={[type.body, { color: colors.textPrimary, textAlign: "center", marginBottom: spacing.md }]}>
          Precisamos da câmera para escanear o código de barras.
        </Text>
        <Button title="Permitir câmera" onPress={requestPermission} />
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      <CameraView
        style={{ flex: 1 }}
        barcodeScannerSettings={{
          barcodeTypes: ["ean13", "ean8", "upc_a", "upc_e"],
        }}
        onBarcodeScanned={isProcessing ? undefined : handleScanned}
      />
    </View>
  );
}
