const { withAndroidManifest } = require("@expo/config-plugins");

// O Android bloqueia tráfego HTTP "sem criptografia" por padrão em builds de
// verdade (não no Expo Go/dev) — silenciosamente, sem erro nenhum pro app ver.
// Foi exatamente isso que fez o login "não acontecer nada": o pedido nem saía
// do aparelho. Enquanto o backend não tiver HTTPS, isto libera HTTP mesmo.
function withCleartextTraffic(config) {
  return withAndroidManifest(config, (config) => {
    const app = config.modResults.manifest.application?.[0];
    if (app) {
      app.$["android:usesCleartextTraffic"] = "true";
    }
    return config;
  });
}

module.exports = withCleartextTraffic;
