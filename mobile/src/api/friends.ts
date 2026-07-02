import { api } from "./client";

export type UserSummary = {
  id: number;
  handle: string;
  display_name: string;
};

export type FriendRequest = {
  id: number;
  status: "pending" | "accepted" | "declined";
  created_at: string;
  other_user: UserSummary;
  direction: "sent" | "received";
};

export async function listFriends(): Promise<UserSummary[]> {
  const { data } = await api.get<UserSummary[]>("/friends");
  return data;
}

export async function listFriendRequests(): Promise<FriendRequest[]> {
  const { data } = await api.get<FriendRequest[]>("/friends/requests");
  return data;
}

export async function sendFriendRequest(handle: string): Promise<FriendRequest> {
  const { data } = await api.post<FriendRequest>("/friends/request", { handle });
  return data;
}

export async function acceptFriendRequest(id: number): Promise<FriendRequest> {
  const { data } = await api.post<FriendRequest>(`/friends/requests/${id}/accept`);
  return data;
}

export async function declineFriendRequest(id: number): Promise<void> {
  await api.post(`/friends/requests/${id}/decline`);
}
