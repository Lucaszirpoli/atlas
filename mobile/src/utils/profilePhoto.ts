import AsyncStorage from "@react-native-async-storage/async-storage";
import { useCallback, useEffect, useState } from "react";

import { persistProgressPhoto, resolveProgressPhotoUri } from "./photoStorage";

/**
 * Foto de perfil, salva SÓ NO APARELHO por enquanto (não existe upload pra
 * nuvem em nenhum lugar do app ainda — nem as fotos de progresso têm isso).
 * Por isso ela aparece pro próprio usuário (Perfil, Home) mas NÃO pros amigos
 * no Social — lá o Avatar mostra as iniciais até o app ganhar armazenamento
 * em nuvem (R2) pra imagens compartilhadas entre usuários.
 */

const CHAVE = "@appfit/profile_photo_key";

async function loadKey(): Promise<string | null> {
  try {
    return await AsyncStorage.getItem(CHAVE);
  } catch {
    return null;
  }
}

/** Hook: uri pronta pra exibir + trocar/remover a foto de perfil. */
export function useProfilePhoto() {
  const [key, setKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    loadKey().then((k) => {
      setKey(k);
      setLoading(false);
    });
  }, []);

  useEffect(() => reload(), [reload]);

  async function escolher(sourceUri: string) {
    const k = await persistProgressPhoto(sourceUri);
    await AsyncStorage.setItem(CHAVE, k);
    setKey(k);
  }

  async function remover() {
    try {
      await AsyncStorage.removeItem(CHAVE);
    } catch {
      /* segue mesmo assim — a tela local já reflete a remoção */
    }
    setKey(null);
  }

  return {
    uri: key ? resolveProgressPhotoUri(key) : null,
    loading,
    escolher,
    remover,
    reload,
  };
}
