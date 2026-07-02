import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, FlatList, Text, TextInput, TouchableOpacity, View } from "react-native";

import { reportContent } from "../../api/blocksAndReports";
import { commentOnPost, getFeed, reactToPost, removeReaction, type FeedPost } from "../../api/feed";
import { Button } from "../../components/Button";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

function describePost(post: FeedPost): string {
  if (post.post_type === "workout") {
    const s = post.summary;
    return `Concluiu um treino — ${Math.round(s.volume_total_kg ?? 0)}kg de volume total`;
  }
  if (post.post_type === "meal") {
    const s = post.summary;
    return `Compartilhou uma refeição (${s.categoria ?? ""}) — ${Math.round(s.kcal_total ?? 0)} kcal`;
  }
  return "Compartilhou uma foto de progresso";
}

export function SocialFeedScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();

  const [posts, setPosts] = useState<FeedPost[]>([]);
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({});

  useFocusEffect(
    useCallback(() => {
      getFeed().then(setPosts);
    }, [])
  );

  async function handleReact(post: FeedPost) {
    if (post.my_reaction) {
      await removeReaction(post.id);
    } else {
      await reactToPost(post.id);
    }
    getFeed().then(setPosts);
  }

  async function handleComment(post: FeedPost) {
    const content = (commentDrafts[post.id] ?? "").trim();
    if (!content) return;
    await commentOnPost(post.id, content);
    setCommentDrafts((prev) => ({ ...prev, [post.id]: "" }));
    getFeed().then(setPosts);
  }

  function handleReport(post: FeedPost) {
    Alert.alert("Denunciar post", "Por que você está denunciando isso?", [
      {
        text: "Conteúdo inapropriado",
        onPress: () => reportContent("feed_post", post.id, "Conteúdo inapropriado"),
      },
      { text: "Assédio", onPress: () => reportContent("feed_post", post.id, "Assédio") },
      { text: "Cancelar", style: "cancel" },
    ]);
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View
        style={{
          flexDirection: "row",
          justifyContent: "space-between",
          padding: spacing.lg,
          paddingBottom: spacing.sm,
        }}
      >
        <Text style={[type.h1, { color: colors.textPrimary }]}>Social</Text>
        <View style={{ flexDirection: "row", gap: spacing.md }}>
          <TouchableOpacity onPress={() => navigation.navigate("Friends")}>
            <Text style={[type.body, { color: colors.primary }]}>Amigos</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => navigation.navigate("Challenges")}>
            <Text style={[type.body, { color: colors.primary }]}>Desafios</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={() => navigation.navigate("Privacy")}>
            <Text style={[type.body, { color: colors.primary }]}>⚙</Text>
          </TouchableOpacity>
        </View>
      </View>

      <FlatList
        data={posts}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={{ padding: spacing.lg, paddingTop: 0 }}
        ListEmptyComponent={
          <Text style={[type.body, { color: colors.textSecondary }]}>
            Nada por aqui ainda. Adicione amigos para ver o feed deles.
          </Text>
        }
        renderItem={({ item }) => (
          <View
            style={{
              backgroundColor: colors.surface,
              borderRadius: radius.card,
              borderWidth: 1,
              borderColor: colors.moduleSocial,
              padding: spacing.md,
              marginBottom: spacing.md,
            }}
          >
            <Text style={[type.bodySmall, { color: colors.textSecondary, marginBottom: spacing.xs }]}>
              {item.author.display_name} · @{item.author.handle}
            </Text>
            <Text style={[type.body, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
              {describePost(item)}
            </Text>
            {item.caption ? (
              <Text style={[type.bodySmall, { color: colors.textPrimary, marginBottom: spacing.xs }]}>
                {item.caption}
              </Text>
            ) : null}

            <View style={{ flexDirection: "row", alignItems: "center", marginTop: spacing.sm, gap: spacing.md }}>
              <TouchableOpacity onPress={() => handleReact(item)}>
                <Text style={[type.body, { color: item.my_reaction ? colors.secondary : colors.textSecondary }]}>
                  👍 {item.reaction_count}
                </Text>
              </TouchableOpacity>
              {item.author.id !== user?.id ? (
                <TouchableOpacity onPress={() => handleReport(item)}>
                  <Text style={[type.caption, { color: colors.textSecondary }]}>Denunciar</Text>
                </TouchableOpacity>
              ) : null}
            </View>

            {item.comments.map((c) => (
              <Text key={c.id} style={[type.caption, { color: colors.textSecondary, marginTop: spacing.xs }]}>
                <Text style={{ fontWeight: "600" }}>{c.author.display_name}: </Text>
                {c.content}
              </Text>
            ))}

            <View style={{ flexDirection: "row", marginTop: spacing.sm, alignItems: "center" }}>
              <TextInput
                value={commentDrafts[item.id] ?? ""}
                onChangeText={(v) => setCommentDrafts((prev) => ({ ...prev, [item.id]: v }))}
                placeholder="Comentar..."
                placeholderTextColor={colors.textSecondary}
                style={[
                  type.bodySmall,
                  {
                    flex: 1,
                    color: colors.textPrimary,
                    borderWidth: 1,
                    borderColor: colors.border,
                    borderRadius: radius.button,
                    paddingHorizontal: spacing.sm,
                    height: 36,
                  },
                ]}
              />
              <TouchableOpacity onPress={() => handleComment(item)} style={{ marginLeft: spacing.sm }}>
                <Text style={[type.bodySmall, { color: colors.primary }]}>Enviar</Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
      />
    </View>
  );
}
