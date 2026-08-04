import { Ionicons } from "@expo/vector-icons";
import React, { useEffect, useState } from "react";
import { Modal, Text, TouchableOpacity, View } from "react-native";

import { checkHandleAvailability } from "../api/auth";
import { Button } from "./Button";
import { TextField } from "./TextField";
import { useTheme } from "../theme/ThemeProvider";

const HANDLE_PATTERN = /^[a-z0-9_]{3,30}$/;

/** Só aparece no PRIMEIRO login com uma conta Google — o backend cria a conta
 * na hora, mas precisa de um @handle único (o Google não dá um). O nome de
 * exibição já vem preenchido do perfil do Google; a pessoa só escolhe o
 * @handle e confirma. */
export function GoogleHandleModal({
  visible,
  defaultName,
  submitting,
  onCancel,
  onConfirm,
}: {
  visible: boolean;
  defaultName: string;
  submitting: boolean;
  onCancel: () => void;
  onConfirm: (handle: string, displayName: string) => void;
}) {
  const { colors, type, spacing, radius } = useTheme();
  const [displayName, setDisplayName] = useState(defaultName);
  const [handle, setHandle] = useState("");
  const [status, setStatus] = useState<"idle" | "checking" | "available" | "taken" | "invalid">("idle");

  useEffect(() => {
    if (visible) setDisplayName(defaultName);
  }, [visible, defaultName]);

  useEffect(() => {
    if (handle.length === 0) {
      setStatus("idle");
      return;
    }
    if (!HANDLE_PATTERN.test(handle)) {
      setStatus("invalid");
      return;
    }
    setStatus("checking");
    const timeout = setTimeout(async () => {
      try {
        const result = await checkHandleAvailability(handle);
        setStatus(result.available ? "available" : "taken");
      } catch {
        setStatus("idle");
      }
    }, 400);
    return () => clearTimeout(timeout);
  }, [handle]);

  const hint =
    status === "invalid"
      ? "3-30 caracteres: letras minúsculas, números ou _"
      : status === "taken"
        ? "Esse @handle já está em uso"
        : undefined;

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancel}>
      <View style={{ flex: 1, backgroundColor: "#000000AA", justifyContent: "center", padding: spacing.lg }}>
        <View style={{ backgroundColor: colors.surface, borderRadius: radius.card, padding: spacing.lg }}>
          <Text style={[type.h2, { color: colors.textPrimary, marginBottom: 4 }]}>Só mais um passo</Text>
          <Text style={[type.body, { color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 21 }]}>
            Escolha um @handle único pra sua conta — o resto o Google já preencheu.
          </Text>

          <TextField
            label="Nome de exibição"
            placeholder="Como quer ser chamado"
            value={displayName}
            onChangeText={setDisplayName}
          />
          <View>
            <TextField
              label="@handle (nome de usuário único)"
              autoCapitalize="none"
              placeholder="seu_handle"
              value={handle}
              onChangeText={(v) => setHandle(v.toLowerCase())}
              error={hint}
            />
            {status === "available" ? (
              <View style={{ flexDirection: "row", alignItems: "center", gap: 4, marginTop: -spacing.sm, marginBottom: spacing.sm, marginLeft: spacing.xs }}>
                <Ionicons name="checkmark-circle" size={14} color={colors.success} />
                <Text style={[type.caption, { color: colors.success }]}>Disponível!</Text>
              </View>
            ) : null}
          </View>

          <View style={{ marginTop: spacing.sm }}>
            <Button
              title="Continuar"
              onPress={() => onConfirm(handle, displayName.trim())}
              loading={submitting}
              disabled={status !== "available" || !displayName.trim()}
            />
          </View>
          <TouchableOpacity onPress={onCancel} disabled={submitting} style={{ marginTop: spacing.sm, alignItems: "center" }}>
            <Text style={[type.body, { color: colors.textSecondary }]}>Cancelar</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}
