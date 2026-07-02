import AsyncStorage from "@react-native-async-storage/async-storage";
import axios from "axios";

// Em dev, o Expo Go acessa a máquina host pelo IP local, não localhost.
// Ajuste EXPO_PUBLIC_API_URL no .env do mobile para o IP da sua máquina.
const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

export const TOKEN_STORAGE_KEY = "@appfit/access_token";

export const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem(TOKEN_STORAGE_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
