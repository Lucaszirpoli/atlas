import { api } from "./client";

export type GymSearchResult = {
  name: string;
  address: string | null;
  lat: number;
  lng: number;
  osm_id: string | null;
  distance_m: number;
};

export type Gym = {
  name: string;
  address: string | null;
  lat: number;
  lng: number;
  osm_id: string | null;
};

export type GymCheckIn = {
  day: string;
  at_home_gym: boolean;
  distance_m: number | null;
  gym_name: string | null;
};

/** Busca academias pelo nome perto de você (OpenStreetMap, via backend).
 * A busca externa pode demorar — timeout maior que o padrão. */
export async function searchGyms(q: string, lat: number, lng: number): Promise<GymSearchResult[]> {
  const { data } = await api.get<GymSearchResult[]>("/gyms/search", {
    params: { q, lat, lng },
    timeout: 30000,
  });
  return data;
}

export async function getMyGym(): Promise<Gym | null> {
  const { data } = await api.get<Gym | null>("/gyms/me");
  return data;
}

export async function setMyGym(gym: Gym): Promise<Gym> {
  const { data } = await api.put<Gym>("/gyms/me", gym);
  return data;
}

/** Check-in de hoje. `gymName` só quando treinou FORA da academia cadastrada. */
export async function checkInGym(lat: number, lng: number, gymName?: string): Promise<GymCheckIn> {
  const { data } = await api.post<GymCheckIn>("/gyms/checkin", { lat, lng, gym_name: gymName });
  return data;
}

export async function listMyCheckins(days = 30): Promise<GymCheckIn[]> {
  const { data } = await api.get<GymCheckIn[]>("/gyms/checkins", { params: { days } });
  return data;
}
