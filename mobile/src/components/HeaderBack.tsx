import { Ionicons } from "@expo/vector-icons";
import { useNavigation } from "@react-navigation/native";
import React from "react";
import { TouchableOpacity } from "react-native";

import { useTheme } from "../theme/ThemeProvider";

/** Botão de voltar para header. Em telas iniciais de um stack aninhado,
 * goBack() sobe para o navegador pai (volta ao Dashboard). */
export function HeaderBack({ color }: { color?: string }) {
  const { colors } = useTheme();
  const navigation = useNavigation<any>();
  return (
    <TouchableOpacity onPress={() => navigation.goBack()} hitSlop={12} style={{ paddingRight: 8 }}>
      <Ionicons name="chevron-back" size={26} color={color ?? colors.textPrimary} />
    </TouchableOpacity>
  );
}
