import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import React, { useCallback, useState } from "react";
import { Alert, FlatList, Text, TextInput, TouchableOpacity, View } from "react-native";

import { reportContent } from "../../api/blocksAndReports";
import {
  commentOnPost,
  deleteFeedPost,
  getFeed,
  reactToPost,
  removeReaction,
  type FeedPost,
} from "../../api/feed";
import { Avatar } from "../../components/Avatar";
import { Card } from "../../components/Card";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { useAuth } from "../../context/AuthContext";
import { useTheme } from "../../theme/ThemeProvider";

const POST_META: Record<FeedPost["post_type"], { icon: keyof typeof Ionicons.glyphMap; color: string }> = {
  workout: { icon: "barbell", color: "#FF6B35" },
  meal: { icon: "restaurant", color: "#1F7A5C" },
  progress_photo: { icon: "camera", color: "#E8637A" },
};

function describePost(post: FeedPost): string {
  if (post.post_type === "workout") {
    return `Concluiu um treino · ${Math.round(post.summary.volume_total_kg ?? 0)}kg de volume`;
  }
  if (post.post_type === "meal") {
    return `Compartilhou uma refeição${post.summary.categoria ? ` (${post.summary.categoria})` : ""} · ${Math.round(post.summary.kcal_total ?? 0)} kcal`;
  }
  return "Compartilhou uma foto de progresso";
}

function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 60) return `${Math.max(mins, 1)}min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

export function SocialFeedScreen() {
  const { colors, type, spacing, radius } = useTheme();
  const navigation = useNavigation<any>();
  const { user } = useAuth();

  const [posts, setPosts] = useState<FeedPost[]>([]);
  const [commentDrafts, setCommentDrafts] = useState<Record<number, string>>({});
  const [deleteTarget, setDeleteTarget] = useState<FeedPost | null>(null);

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
      { text: "Conteúdo inapropriado", onPress: () => reportContent("feed_post", post.id, "Conteúdo inapropriado") },
      { text: "Assédio", onPress: () => reportContent("feed_post", post.id, "Assédio") },
      { text: "Cancelar", style: "cancel" },
    ]);
  }

  async function confirmDeletePost() {
    if (!deleteTarget) return;
    const id = deleteTarget.id;
    setDeleteTarget(null);
    setPosts((prev) => prev.filter((p) => p.id !== id)); // some na hora
    try {
      await deleteFeedPost(id);
    } catch {
      getFeed().then(setPosts).catch(() => {}); // falhou: recarrega a verdade
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {/* Header */}
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          justifyContent: "space-between",
          paddingHorizontal: spacing.lg,
          paddingTop: spacing.xl,
          paddingBottom: spacing.md,
        }}
      >
        <View style={{ flexDirection: "row", alignItems: "center" }}>
          <TouchableOpacity onPress={() => navigation.goBack()} hitSlop={10} style={{ marginRight: spacing.sm }}>
            <Ionicons name="chevron-back" size={26} color={colors.textPrimary} />
          </TouchableOpacity>
          <Text style={[type.h1, { color: colors.textPrimary, fontSize: 26 }]}>Social</Text>
        </View>
        <View style={{ flexDirection: "row", gap: spacing.sm }}>
          <HeaderIcon icon="people" onPress={() => navigation.navigate("Friends")} />
          <HeaderIcon icon="trophy" onPress={() => navigation.navigate("Challenges")} />
          <HeaderIcon icon="shield-checkmark" onPress={() => navigation.navigate("Privacy")} />
        </View>
      </View>

      <FlatList
        data={posts}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={{ padding: spacing.lg, paddingTop: 0, paddingBottom: spacing.xxl }}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={<ChallengesBanner onPress={() => navigation.navigate("Challenges")} />}
        ListEmptyComponent={
          <Card>
            <View style={{ alignItems: "center", paddingVertical: spacing.lg }}>
              <View
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: 22,
                  backgroundColor: colors.moduleSocial + "22",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: spacing.md,
                }}
              >
                <Ionicons name="people" size={30} color={colors.moduleSocial} />
              </View>
              <Text style={[type.h2, { color: colors.textPrimary, marginBottom: 4 }]}>Seu feed está vazio</Text>
              <Text style={[type.bodySmall, { color: colors.textSecondary, textAlign: "center" }]}>
                Adicione amigos pelo @handle para{"\n"}acompanhar os treinos deles.
              </Text>
            </View>
          </Card>
        }
        renderItem={({ item }) => {
          const meta = POST_META[item.post_type];
          return (
            <Card style={{ marginBottom: spacing.md }}>
              {/* Autor */}
              <View style={{ flexDirection: "row", alignItems: "center", marginBottom: spacing.sm }}>
                <Avatar name={item.author.display_name} handle={item.author.handle} />
                <View style={{ flex: 1, marginLeft: spacing.sm }}>
                  <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>
                    {item.author.display_name}
                  </Text>
                  <Text style={[type.caption, { color: colors.textSecondary }]}>
                    @{item.author.handle} · {timeAgo(item.created_at)}
                  </Text>
                </View>
                {item.author.id !== user?.id ? (
                  <TouchableOpacity onPress={() => handleReport(item)} hitSlop={10}>
                    <Ionicons name="ellipsis-horizontal" size={18} color={colors.textSecondary} />
                  </TouchableOpacity>
                ) : (
                  // No próprio post: apagar. O post de treino é criado sozinho
                  // ao concluir a sessão, então a pessoa precisa poder tirar do
                  // ar o que não queria ter mostrado.
                  <TouchableOpacity onPress={() => setDeleteTarget(item)} hitSlop={10}>
                    <Ionicons name="trash-outline" size={18} color={colors.textSecondary} />
                  </TouchableOpacity>
                )}
              </View>

              {/* Conteúdo */}
              <View
                style={{
                  flexDirection: "row",
                  alignItems: "center",
                  backgroundColor: meta.color + "12",
                  borderRadius: radius.button,
                  padding: spacing.md,
                }}
              >
                <Ionicons name={meta.icon} size={22} color={meta.color} style={{ marginRight: spacing.sm }} />
                <Text style={[type.bodySmall, { color: colors.textPrimary, flex: 1, fontWeight: "500" }]}>
                  {describePost(item)}
                </Text>
              </View>
              {item.caption ? (
                <Text style={[type.bodySmall, { color: colors.textPrimary, marginTop: spacing.sm }]}>
                  {item.caption}
                </Text>
              ) : null}

              {/* Reações */}
              <View style={{ flexDirection: "row", alignItems: "center", marginTop: spacing.md, gap: spacing.md }}>
                <TouchableOpacity
                  onPress={() => handleReact(item)}
                  style={{
                    flexDirection: "row",
                    alignItems: "center",
                    gap: 5,
                    backgroundColor: item.my_reaction ? colors.secondarySoft : colors.surfaceAlt,
                    borderRadius: radius.pill,
                    paddingVertical: 6,
                    paddingHorizontal: 14,
                  }}
                >
                  <Ionicons
                    name={item.my_reaction ? "heart" : "heart-outline"}
                    size={16}
                    color={item.my_reaction ? colors.secondary : colors.textSecondary}
                  />
                  <Text style={[type.caption, { color: item.my_reaction ? colors.secondary : colors.textSecondary, fontWeight: "700" }]}>
                    {item.reaction_count}
                  </Text>
                </TouchableOpacity>
                <View style={{ flexDirection: "row", alignItems: "center", gap: 5 }}>
                  <Ionicons name="chatbubble-outline" size={15} color={colors.textSecondary} />
                  <Text style={[type.caption, { color: colors.textSecondary }]}>{item.comments.length}</Text>
                </View>
              </View>

              {/* Comentários */}
              {item.comments.map((c) => (
                <View key={c.id} style={{ flexDirection: "row", marginTop: spacing.sm }}>
                  <Text style={[type.caption, { color: colors.textPrimary, flex: 1 }]}>
                    <Text style={{ fontWeight: "700" }}>{c.author.display_name}</Text> {c.content}
                  </Text>
                </View>
              ))}

              <View style={{ flexDirection: "row", marginTop: spacing.sm, alignItems: "center", gap: spacing.sm }}>
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
                      backgroundColor: colors.surfaceAlt,
                      borderRadius: radius.pill,
                      paddingHorizontal: spacing.md,
                      height: 38,
                    },
                  ]}
                />
                <TouchableOpacity onPress={() => handleComment(item)} hitSlop={8}>
                  <Ionicons name="send" size={18} color={colors.primary} />
                </TouchableOpacity>
              </View>
            </Card>
          );
        }}
      />

      <ConfirmDialog
        visible={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Apagar post"
        message="Este post sai do feed pra todo mundo. Seu treino/refeição continua salvo normalmente — só a publicação é removida."
        confirmLabel="Apagar"
        destructive
        onConfirm={confirmDeletePost}
      />
    </View>
  );
}

function ChallengesBanner({ onPress }: { onPress: () => void }) {
  const { colors, type, spacing, radius } = useTheme();
  return (
    <Card style={{ marginBottom: spacing.md }}>
      <TouchableOpacity
        onPress={onPress}
        activeOpacity={0.7}
        style={{ flexDirection: "row", alignItems: "center" }}
      >
        <View
          style={{
            width: 48,
            height: 48,
            borderRadius: 16,
            backgroundColor: colors.moduleSocial + "22",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Ionicons name="trophy" size={24} color={colors.moduleSocial} />
        </View>
        <View style={{ flex: 1, marginLeft: spacing.sm }}>
          <Text style={[type.body, { color: colors.textPrimary, fontWeight: "700" }]}>Desafios</Text>
          <Text style={[type.bodySmall, { color: colors.textSecondary }]}>
            Compita com amigos por streak, treinos e volume
          </Text>
        </View>
        <View
          style={{
            width: 32,
            height: 32,
            borderRadius: radius.pill,
            backgroundColor: colors.surfaceAlt,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Ionicons name="chevron-forward" size={18} color={colors.textSecondary} />
        </View>
      </TouchableOpacity>
    </Card>
  );
}

function HeaderIcon({ icon, onPress }: { icon: keyof typeof Ionicons.glyphMap; onPress: () => void }) {
  const { colors } = useTheme();
  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.7}
      hitSlop={8}
      style={{
        width: 44,
        height: 44,
        borderRadius: 16,
        backgroundColor: colors.surface,
        borderWidth: 1,
        borderColor: colors.border,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <Ionicons name={icon} size={22} color={colors.textPrimary} />
    </TouchableOpacity>
  );
}
