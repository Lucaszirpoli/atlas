import { api } from "./client";
import type { UserSummary } from "./friends";

export async function listBlockedUsers(): Promise<UserSummary[]> {
  const { data } = await api.get<UserSummary[]>("/blocks");
  return data;
}

export async function blockUser(handle: string): Promise<void> {
  await api.post("/blocks", { handle });
}

export async function unblockUser(userId: number): Promise<void> {
  await api.delete(`/blocks/${userId}`);
}

export async function reportContent(
  targetType: "user" | "feed_post",
  targetId: number,
  reason: string
): Promise<void> {
  await api.post("/reports", { target_type: targetType, target_id: targetId, reason });
}
