import { Ionicons } from "@expo/vector-icons";
import * as Location from "expo-location";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, Text, TextInput, TouchableOpacity, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  checkInGym,
  getMyGym,
  listMyCheckins,
  searchGyms,
  setMyGym,
  type Gym,
  type GymCheckIn,
  type GymSearchResult,
} from "../../api/gyms";
import { Button } from "../../components/Button";
import { Card } from "../../components/Card";
import { InfoDialog } from "../../components/InfoDialog";
import { useTheme } from "../../theme/ThemeProvider";
import { mensagemDeErro } from "../../utils/errorMessage";

/** Academia da pessoa + check-in com prova de localização (base do desafio
 * "quem vai mais à academia"). Na primeira vez ela busca a academia no mapa;
 * depois é só tocar em "Cheguei na academia" estando lá. Se treinou em outro
 * lugar, dá pra registrar informando o nome — conta, mas marcado como "fora". */
export function GymScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const insets = useSafeAreaInsets();

  const [gym, setGym] = useState<Gym | null>(null);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GymSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [checkins, setCheckins] = useState<GymCheckIn[]>([]);
  const [checkingIn, setCheckingIn] = useState(false);
  const [awayName, setAwayName] = useState("");
  const [showAway, setShowAway] = useState(false);
  const [info, setInfo] = useState<{ title: string; message: string } | null>(null);

  useEffect(() => {
    Promise.all([getMyGym(), listMyCheckins()])
      .then(([g, c]) => {
        setGym(g);
        setCheckins(c);
        // Sem academia cadastrada: já mostra as da região, sem precisar digitar.
        if (!g) loadNearby();
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  /** Lista as academias da região (busca vazia = todas por perto). */
  async function loadNearby() {
    setSearching(true);
    try {
      const pos = await currentPosition();
      if (!pos) return;
      setResults(await searchGyms("", pos.lat, pos.lng));
    } catch {
      // silencioso: a pessoa ainda pode buscar pelo nome
    } finally {
      setSearching(false);
    }
  }

  /** Pede permissão e devolve a posição atual (ou null se negada/falhou). */
  async function currentPosition(): Promise<{ lat: number; lng: number } | null> {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") {
      setInfo({
        title: "Precisa da localização",
        message:
          "O check-in usa sua localização pra provar que você está na academia. Libere o acesso à localização nas permissões do app.",
      });
      return null;
    }
    const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
    return { lat: pos.coords.latitude, lng: pos.coords.longitude };
  }

  async function handleSearch() {
    setSearching(true);
    setResults(null);
    try {
      const pos = await currentPosition();
      if (!pos) return;
      const found = await searchGyms(query.trim(), pos.lat, pos.lng);
      setResults(found);
    } catch (err: any) {
      setInfo({ title: "Não consegui buscar", message: mensagemDeErro(err, "Tente novamente.") });
    } finally {
      setSearching(false);
    }
  }

  async function handlePick(g: GymSearchResult) {
    try {
      const saved = await setMyGym({ name: g.name, address: g.address, lat: g.lat, lng: g.lng, osm_id: g.osm_id });
      setGym(saved);
      setResults(null);
      setQuery("");
    } catch (err: any) {
      setInfo({ title: "Não consegui salvar", message: mensagemDeErro(err, "Tente novamente.") });
    }
  }

  async function handleCheckIn(awayGymName?: string) {
    setCheckingIn(true);
    try {
      const pos = await currentPosition();
      if (!pos) return;
      const ci = await checkInGym(pos.lat, pos.lng, awayGymName);
      setCheckins((prev) => [ci, ...prev.filter((c) => c.day !== ci.day)]);
      setShowAway(false);
      setAwayName("");
      setInfo({
        title: ci.at_home_gym ? "Check-in feito! 💪" : "Check-in registrado (fora)",
        message: ci.at_home_gym
          ? "Presença confirmada na sua academia. Já conta nos seus desafios."
          : `Registrado como treino fora da sua academia${ci.gym_name ? ` (${ci.gym_name})` : ""}. Conta no desafio, marcado como "fora".`,
      });
    } catch (err: any) {
      const detail: string = mensagemDeErro(err, "Tente novamente.");
      // Longe da academia: o backend pede o nome do lugar onde treinou.
      if (detail.includes("longe da sua academia")) {
        setShowAway(true);
        setInfo({ title: "Você está longe da sua academia", message: detail });
      } else {
        setInfo({ title: "Não consegui fazer check-in", message: detail });
      }
    } finally {
      setCheckingIn(false);
    }
  }

  const todayIso = new Date().toISOString().slice(0, 10);
  const checkedInToday = checkins.some((c) => c.day === todayIso);

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxl + insets.bottom }}
      showsVerticalScrollIndicator={false}
    >
      {gym ? (
        <>
          <Card accent={colors.moduleSocial}>
            <View style={{ flexDirection: "row", alignItems: "center" }}>
              <View
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 15,
                  backgroundColor: colors.moduleSocial + "1E",
                  alignItems: "center",
                  justifyContent: "center",
                  marginRight: spacing.sm,
                }}
              >
                <Ionicons name="location" size={22} color={colors.moduleSocial} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[type.caption, { color: colors.textSecondary }]}>Sua academia</Text>
                <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>{gym.name}</Text>
                {gym.address ? (
                  <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
                    {gym.address}
                  </Text>
                ) : null}
              </View>
            </View>
          </Card>

          {checkedInToday ? (
            <View
              style={{
                flexDirection: "row",
                alignItems: "center",
                gap: 8,
                backgroundColor: colors.success + "22",
                borderRadius: radius.card,
                padding: spacing.md,
                marginTop: spacing.md,
              }}
            >
              <Ionicons name="checkmark-circle" size={20} color={colors.success} />
              <Text style={[type.body, { color: colors.textPrimary, flex: 1 }]}>Check-in de hoje já registrado.</Text>
            </View>
          ) : (
            <Button
              title="Cheguei na academia"
              onPress={() => handleCheckIn()}
              loading={checkingIn}
              style={{ marginTop: spacing.md }}
            />
          )}

          {/* Treinou em outro lugar */}
          {showAway && !checkedInToday ? (
            <Card style={{ marginTop: spacing.md }}>
              <Text style={[type.bodySmall, { color: colors.textPrimary, fontWeight: "700", marginBottom: spacing.xs }]}>
                Treinou em outra academia?
              </Text>
              <TextInput
                value={awayName}
                onChangeText={setAwayName}
                placeholder="Nome do lugar onde treinou"
                placeholderTextColor={colors.textSecondary}
                numberOfLines={1}
                style={[
                  type.body,
                  {
                    color: colors.textPrimary,
                    backgroundColor: colors.surfaceAlt,
                    borderRadius: radius.button,
                    height: 48,
                    paddingHorizontal: spacing.md,
                    marginBottom: spacing.sm,
                  },
                ]}
              />
              <Button
                title="Registrar treino fora"
                variant="secondary"
                disabled={!awayName.trim()}
                loading={checkingIn}
                onPress={() => handleCheckIn(awayName.trim())}
              />
            </Card>
          ) : null}

          <TouchableOpacity onPress={() => setGym(null)} style={{ alignItems: "center", marginTop: spacing.lg }}>
            <Text style={[type.bodySmall, { color: colors.textSecondary, fontWeight: "700" }]}>Trocar academia</Text>
          </TouchableOpacity>

          {checkins.length > 0 ? (
            <>
              <Text style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xl, marginBottom: spacing.sm }]}>
                SEUS CHECK-INS
              </Text>
              {checkins.slice(0, 10).map((c) => (
                <View
                  key={c.day}
                  style={{ flexDirection: "row", alignItems: "center", paddingVertical: spacing.sm, gap: spacing.sm }}
                >
                  <Ionicons
                    name={c.at_home_gym ? "checkmark-circle" : "airplane"}
                    size={18}
                    color={c.at_home_gym ? colors.success : colors.warning}
                  />
                  <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1 }]}>
                    {new Date(c.day + "T00:00:00").toLocaleDateString("pt-BR")}
                  </Text>
                  <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
                    {c.at_home_gym ? "na sua academia" : `fora${c.gym_name ? ` · ${c.gym_name}` : ""}`}
                  </Text>
                </View>
              ))}
            </>
          ) : null}
        </>
      ) : (
        <>
          <Text style={[type.h2, { color: colors.textPrimary }]}>Qual é a sua academia?</Text>
          <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: 4, marginBottom: spacing.md }]}>
            Estas são as academias perto de você. Não achou a sua? Busque pelo nome. Usamos sua localização só pra
            isso e, depois, pra confirmar sua presença nos check-ins.
          </Text>

          <View style={{ flexDirection: "row", gap: spacing.sm }}>
            <TextInput
              value={query}
              onChangeText={setQuery}
              placeholder="Ex: Smart Fit"
              placeholderTextColor={colors.textSecondary}
              numberOfLines={1}
              onSubmitEditing={handleSearch}
              style={[
                type.body,
                {
                  flex: 1,
                  color: colors.textPrimary,
                  backgroundColor: colors.surfaceAlt,
                  borderRadius: radius.button,
                  height: 50,
                  paddingHorizontal: spacing.md,
                },
              ]}
            />
            <TouchableOpacity
              onPress={handleSearch}
              disabled={searching || !query.trim()}
              style={{
                width: 50,
                height: 50,
                borderRadius: radius.button,
                backgroundColor: query.trim() ? colors.primary : colors.surfaceAlt,
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Ionicons name="search" size={20} color={query.trim() ? colors.textOnPrimary : colors.textSecondary} />
            </TouchableOpacity>
          </View>

          {searching ? <ActivityIndicator color={colors.primary} style={{ marginTop: spacing.lg }} /> : null}

          {results != null && results.length === 0 && !searching ? (
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginTop: spacing.lg }]}>
              Não achei academias mapeadas perto de você. Tente buscar pelo nome — ou confira se a localização está
              ligada.
            </Text>
          ) : null}

          {(results ?? []).map((g, i) => (
            <TouchableOpacity key={`${g.osm_id}-${i}`} activeOpacity={0.8} onPress={() => handlePick(g)}>
              <Card style={{ marginTop: spacing.sm }}>
                <View style={{ flexDirection: "row", alignItems: "center" }}>
                  <View style={{ flex: 1 }}>
                    <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>{g.name}</Text>
                    <Text style={[type.caption, { color: colors.textSecondary }]} numberOfLines={1}>
                      {g.address}
                    </Text>
                  </View>
                  <Text style={[type.caption, { color: colors.textSecondary, marginLeft: spacing.sm }]}>
                    {g.distance_m >= 1000 ? `${(g.distance_m / 1000).toFixed(1)} km` : `${Math.round(g.distance_m)} m`}
                  </Text>
                </View>
              </Card>
            </TouchableOpacity>
          ))}
        </>
      )}

      <InfoDialog visible={info != null} onClose={() => setInfo(null)} title={info?.title ?? ""} message={info?.message} />
    </ScrollView>
  );
}
