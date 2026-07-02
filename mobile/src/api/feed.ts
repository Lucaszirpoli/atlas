import { api } from "./client";
import type { UserSummary } from "./friends";

export type FeedComment = {
  id: number;
  author: UserSummary;
  content: string;
  created_at: string;
};

export type FeedPost = {
  id: number;
  author: UserSummary;
  post_type: "workout" | "meal" | "progress_photo";
  reference_id: number;
  caption: string | null;
  created_at: string;
  summary: Record<string, any>;
  reaction_count: number;
  my_reaction: string | null;
  comments: FeedComment[];
};

export async function getFeed(): Promise<FeedPost[]> {
  const { data } = await api.get<FeedPost[]>("/feed");
  return data;
}

export async function shareMeal(mealLogId: number, caption?: string): Promise<FeedPost> {
  const { data } = await api.post<FeedPost>("/feed/share-meal", { meal_log_id: mealLogId, caption });
  return data;
}

export async function shareProgressPhoto(
  progressPhotoId: number,
  caption?: string
): Promise<FeedPost> {
  const { data } = await api.post<FeedPost>("/feed/share-progress-photo", {
    progress_photo_id: progressPhotoId,
    caption,
  });
  return data;
}

export async function reactToPost(postId: number, emoji = "👍"): Promise<void> {
  await api.post(`/feed/${postId}/react`, { emoji });
}

export async function removeReaction(postId: number): Promise<void> {
  await api.delete(`/feed/${postId}/react`);
}

export async function commentOnPost(postId: number, content: string): Promise<FeedComment> {
  const { data } = await api.post<FeedComment>(`/feed/${postId}/comments`, { content });
  return data;
}
