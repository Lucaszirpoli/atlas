import * as FileSystem from "expo-file-system/legacy";
import { Platform } from "react-native";

// Armazenamento PERMANENTE das fotos de progresso no próprio celular.
//
// Bug que isto corrige (crítica #4): o ImagePicker devolve uma URI de CACHE
// (que o sistema apaga pra liberar espaço) e, no iOS, o caminho absoluto da
// pasta do app muda a cada atualização — então a foto "sumia".
//
// Solução sem nuvem: copiamos a foto pra pasta de DOCUMENTOS do app (que o
// sistema não apaga) e guardamos só o caminho RELATIVO. Na hora de exibir,
// remontamos com o documentDirectory ATUAL — assim sobrevive a fechar/reabrir
// e a atualizações do app. (Trocar de celular / desinstalar ainda exige nuvem.)

const PHOTO_DIR = "progress_photos";

/** Copia a foto escolhida pra pasta permanente e devolve a CHAVE relativa
 * (ex: "progress_photos/169....jpg"). Na web (sem documentDirectory) devolve a
 * própria uri. */
export async function persistProgressPhoto(sourceUri: string): Promise<string> {
  const docDir = FileSystem.documentDirectory;
  if (Platform.OS === "web" || !docDir) return sourceUri;

  const dir = docDir + PHOTO_DIR;
  const info = await FileSystem.getInfoAsync(dir);
  if (!info.exists) {
    await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
  }
  const ext = (sourceUri.split(".").pop() || "jpg").split("?")[0].slice(0, 4) || "jpg";
  const filename = `${Date.now()}.${ext}`;
  const dest = `${dir}/${filename}`;
  await FileSystem.copyAsync({ from: sourceUri, to: dest });
  return `${PHOTO_DIR}/${filename}`; // chave relativa (remontada no resolve)
}

/** Remonta a URI exibível a partir do que foi salvo. Chave relativa ->
 * documentDirectory atual; URLs completas (http/https/file/blob) passam direto
 * (compat com o comportamento antigo e futura nuvem). */
export function resolveProgressPhotoUri(stored: string): string {
  if (!stored) return stored;
  if (/^(https?:|file:|blob:|data:|content:)/.test(stored)) return stored;
  const docDir = FileSystem.documentDirectory;
  if (!docDir) return stored;
  return docDir + stored;
}
