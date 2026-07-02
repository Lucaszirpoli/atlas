import { api } from "./client";

export type MeasurementType =
  | "waist"
  | "hip"
  | "chest"
  | "arm_left"
  | "arm_right"
  | "thigh_left"
  | "thigh_right"
  | "neck";

export type BodyMeasurement = {
  id: number;
  type: MeasurementType;
  value_cm: number;
  recorded_at: string;
};

export type ProgressPhoto = {
  id: number;
  photo_url: string;
  recorded_at: string;
};

export async function listMeasurements(): Promise<BodyMeasurement[]> {
  const { data } = await api.get<BodyMeasurement[]>("/measurements");
  return data;
}

export async function createMeasurement(
  type: MeasurementType,
  valueCm: number
): Promise<BodyMeasurement> {
  const { data } = await api.post<BodyMeasurement>("/measurements", {
    type,
    value_cm: valueCm,
  });
  return data;
}

export async function listProgressPhotos(): Promise<ProgressPhoto[]> {
  const { data } = await api.get<ProgressPhoto[]>("/progress-photos");
  return data;
}

export async function createProgressPhoto(photoUrl: string): Promise<ProgressPhoto> {
  const { data } = await api.post<ProgressPhoto>("/progress-photos", { photo_url: photoUrl });
  return data;
}
