# appfit mobile (Fase 0)

## Rodar localmente

```bash
cp .env.example .env
# ajuste EXPO_PUBLIC_API_URL para o IP local da sua máquina (não localhost) se for testar no Expo Go
npm install
npm run start
```

## Estrutura

- `src/theme` — design system (cores, tipografia, espaçamento) da Parte 7 da especificação
- `src/context/AuthContext.tsx` — sessão do usuário (token em AsyncStorage)
- `src/navigation` — auth stack / onboarding / bottom tabs (Início, Nutrição, Treino, Social, Perfil) + FAB de IA
- `src/screens/auth` — cadastro e login
- `src/screens/onboarding` — fluxo conversacional de onboarding + consentimento LGPD + disclaimer médico
- `src/screens/main` — telas do app (placeholders além de Início e Perfil, que chegam nas próximas fases)
