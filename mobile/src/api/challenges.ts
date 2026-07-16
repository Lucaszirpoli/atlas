import { api } from "./client";
import type { UserSummary } from "./friends";

export type Challenge = {
  id: number;
  name: string;
  metric: "workout_count" | "total_volume" | "streak_days" | "gym_checkin";
  start_date: string;
  end_date: string;
  creator_id: number;
  created_at: string;
};

export type LeaderboardEntry = {
  user: UserSummary;
  value: number;
};

export async function listMyChallenges(): Promise<Challenge[]> {
  const { data } = await api.get<Challenge[]>("/challenges");
  return data;
}

export async function createChallenge(payload: {
  name: string;
  metric: Challenge["metric"];
  start_date: string;
  end_date: string;
  invite_handles: string[];
}): Promise<Challenge> {
  const { data } = await api.post<Challenge>("/challenges", payload);
  return data;
}

export async function joinChallenge(id: number): Promise<void> {
  await api.post(`/challenges/${id}/join`);
}

export async function getLeaderboard(
  id: number
): Promise<{ challenge: Challenge; entries: LeaderboardEntry[] }> {
  const { data } = await api.get(`/challenges/${id}/leaderboard`);
  return data;
}
