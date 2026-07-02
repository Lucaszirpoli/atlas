import { api } from "./client";

export type PrivacySettings = {
  profile_visibility: "private" | "public";
  share_workouts: boolean;
  share_meals: boolean;
  share_progress_photos: boolean;
};

export async function getPrivacySettings(): Promise<PrivacySettings> {
  const { data } = await api.get<PrivacySettings>("/privacy");
  return data;
}

export async function updatePrivacySettings(
  patch: Partial<PrivacySettings>
): Promise<PrivacySettings> {
  const { data } = await api.patch<PrivacySettings>("/privacy", patch);
  return data;
}
