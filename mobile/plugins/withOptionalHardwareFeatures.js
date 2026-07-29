const { withAndroidManifest } = require("@expo/config-plugins");

// As permissões de CAMERA e LOCATION (expo-camera, expo-location) fazem o
// Android inferir automaticamente <uses-feature required="true"> pra câmera
// e GPS, mesmo sem nenhuma lib declarar isso explicitamente. Isso faz a Play
// Store excluir aparelhos que ela julga não ter esse hardware (ex.: Galaxy
// A14 apareceu como "não compatível" mesmo tendo câmera e GPS normais).
// Como scanner de código de barras e check-in de academia são recursos
// opcionais no Atlas, declaramos os dois como não-obrigatórios.
const OPTIONAL_FEATURES = [
  "android.hardware.camera",
  "android.hardware.camera.autofocus",
  "android.hardware.camera.any",
  "android.hardware.location",
  "android.hardware.location.gps",
  "android.hardware.location.network",
];

function withOptionalHardwareFeatures(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;
    if (!manifest["uses-feature"]) {
      manifest["uses-feature"] = [];
    }

    for (const name of OPTIONAL_FEATURES) {
      const existing = manifest["uses-feature"].find(
        (f) => f.$["android:name"] === name
      );
      if (existing) {
        existing.$["android:required"] = "false";
      } else {
        manifest["uses-feature"].push({
          $: { "android:name": name, "android:required": "false" },
        });
      }
    }

    return config;
  });
}

module.exports = withOptionalHardwareFeatures;
