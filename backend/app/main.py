from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import (
    ai,
    assistant,
    auth,
    billing,
    blocks,
    challenges,
    coaching,
    objective,
    diet_templates,
    evolution,
    exercises,
    feed,
    foods,
    friends,
    goals,
    gyms,
    meals,
    measurements,
    privacy,
    reports,
    routines,
    sleep,
    users,
    water,
    weight,
    workout_insights,
    workout_sessions,
)

app = FastAPI(title="appfit API", version="0.1.0")

# CORS: o app React Native na web (Expo Web) roda numa origem diferente da API
# e o navegador faz preflight OPTIONS. Sem isso, nenhuma chamada de browser
# passa. As origens permitidas são configuráveis por ambiente.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    # Autenticação é via Bearer token no header Authorization, não cookies —
    # então não precisamos de credentials, e isso mantém o wildcard "*" válido.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(assistant.router)
app.include_router(users.router)
app.include_router(foods.router)
app.include_router(meals.router)
app.include_router(diet_templates.router)
app.include_router(billing.router)
app.include_router(goals.router)
app.include_router(water.router)
app.include_router(weight.router)
app.include_router(measurements.router)
app.include_router(exercises.router)
app.include_router(routines.router)
app.include_router(workout_sessions.router)
app.include_router(ai.router)
app.include_router(friends.router)
app.include_router(blocks.router)
app.include_router(reports.router)
app.include_router(privacy.router)
app.include_router(feed.router)
app.include_router(challenges.router)
app.include_router(gyms.router)
app.include_router(sleep.router)
app.include_router(workout_insights.router)
app.include_router(evolution.router)
app.include_router(coaching.router)
app.include_router(objective.router)

# Imagens/GIFs dos exercícios: arquivos locais versionados no repo (a API do
# ExerciseDB foi aposentada). Ficam aqui até migrarmos pra um bucket
# S3-compatible (Cloudflare R2) em produção.
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


_PRIVACY_POLICY_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Politica de Privacidade - Atlas</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; max-width: 720px; margin: 0 auto; padding: 32px 20px 80px; line-height: 1.6; color: #1a1a1a; }
  h1 { font-size: 1.6rem; }
  h2 { font-size: 1.15rem; margin-top: 2rem; }
  a { color: #FF6B2C; }
  .muted { color: #666; font-size: 0.9rem; }
</style>
</head>
<body>
<h1>Politica de Privacidade - Atlas</h1>
<p class="muted">Ultima atualizacao: 29 de julho de 2026</p>

<p>O Atlas ("app", "nos") e um aplicativo de fitness e nutricao. Esta politica explica quais dados coletamos, para que usamos e quais direitos voce tem, em conformidade com a Lei Geral de Protecao de Dados (LGPD - Lei 13.709/2018).</p>

<h2>1. Quem e o controlador dos dados</h2>
<p>Lucas Zirpoli, desenvolvedor do Atlas. Contato: <a href="mailto:lucaszirpoli@gmail.com">lucaszirpoli@gmail.com</a>.</p>

<h2>2. Dados que coletamos</h2>
<ul>
<li><strong>Dados de conta:</strong> nome, e-mail, nome de usuario, senha (armazenada de forma criptografada).</li>
<li><strong>Dados de saude e bem-estar:</strong> peso, medidas corporais, refeicoes e macronutrientes registrados, treinos e series executadas, horas e qualidade do sono, ingestao de agua. Esses dados sao sensiveis nos termos da LGPD e so sao coletados com o seu consentimento explicito, dado no cadastro/onboarding do app.</li>
<li><strong>Dados de uso:</strong> interacoes com o app para fins de funcionamento e melhoria do produto (ex.: quais telas voce usa).</li>
<li><strong>Conteudo social opcional:</strong> se voce usar os recursos sociais (amigos, desafios, feed), o conteudo que voce publicar e visivel para as pessoas que voce conectar.</li>
<li><strong>Conversas com o assistente de IA (apenas plano Pro):</strong> mensagens trocadas com o assistente, usadas para gerar respostas e sugestoes de treino/dieta.</li>
</ul>

<h2>3. Para que usamos seus dados</h2>
<ul>
<li>Fornecer as funcionalidades do app: registro de dieta, treino, sono, agua, evolucao e a camada social.</li>
<li>Gerar recomendacoes de treino/dieta e respostas do assistente de IA (apenas assinantes Pro), via API da Anthropic.</li>
<li>Processar assinaturas do plano Pro, via RevenueCat (repassamos apenas os identificadores necessarios para validar a compra - nao compartilhamos seus dados de saude com essa plataforma).</li>
<li>Buscar informacoes publicas de produtos alimenticios (nome, marca, tabela nutricional) na base publica Open Food Facts - essa consulta nao envia seus dados pessoais para o Open Food Facts.</li>
<li>Melhorar a seguranca e o funcionamento do app.</li>
</ul>

<h2>4. Compartilhamento de dados</h2>
<p>Nos <strong>nao vendemos</strong> seus dados pessoais. Compartilhamos dados apenas com prestadores de servico estritamente necessarios para operar o app (processamento de pagamento/assinatura via RevenueCat e Google Play, e o provedor de IA Anthropic para as funcionalidades exclusivas do plano Pro), sempre limitado ao necessario para a funcao de cada servico.</p>

<h2>5. Retencao e exclusao</h2>
<p>Seu historico (refeicoes, treinos, peso, sono) e mantido para que voce possa acompanhar sua evolucao ao longo do tempo. Voce pode solicitar a exclusao da sua conta e dos seus dados a qualquer momento pelo e-mail <a href="mailto:lucaszirpoli@gmail.com">lucaszirpoli@gmail.com</a>.</p>

<h2>6. Seus direitos (LGPD)</h2>
<p>Voce pode solicitar, a qualquer momento: confirmacao de tratamento, acesso aos dados, correcao de dados incompletos ou desatualizados, anonimizacao/eliminacao de dados desnecessarios, portabilidade, eliminacao dos dados tratados com consentimento, e revogacao do consentimento. Basta entrar em contato pelo e-mail acima.</p>

<h2>7. Publico infantil</h2>
<p>O Atlas nao e direcionado a criancas e nao foi desenhado para o publico infantil.</p>

<h2>8. Seguranca</h2>
<p>Adotamos medidas tecnicas razoaveis para proteger seus dados, incluindo senhas criptografadas e comunicacao via HTTPS.</p>

<h2>9. Alteracoes desta politica</h2>
<p>Podemos atualizar esta politica periodicamente. Mudancas relevantes serao comunicadas dentro do app.</p>

<h2>10. Contato</h2>
<p>Duvidas sobre privacidade e dados: <a href="mailto:lucaszirpoli@gmail.com">lucaszirpoli@gmail.com</a>.</p>
</body>
</html>
"""


@app.get("/legal/privacidade", response_class=HTMLResponse)
def privacy_policy() -> str:
    return _PRIVACY_POLICY_HTML


_DELETE_ACCOUNT_HTML = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Excluir conta - Atlas</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, Arial, sans-serif; max-width: 720px; margin: 0 auto; padding: 32px 20px 80px; line-height: 1.6; color: #1a1a1a; }
  h1 { font-size: 1.6rem; }
  h2 { font-size: 1.15rem; margin-top: 2rem; }
  a { color: #FF6B2C; }
  .muted { color: #666; font-size: 0.9rem; }
  ol { padding-left: 1.2rem; }
</style>
</head>
<body>
<h1>Como excluir sua conta do Atlas</h1>
<p class="muted">Atlas - aplicativo de fitness e nutricao (desenvolvedor: Lucas Zirpoli)</p>

<h2>Direto pelo app (imediato)</h2>
<p>Abra o Atlas, va em <strong>Perfil &gt; Excluir minha conta</strong> e confirme. A exclusao acontece na hora, sem precisar esperar nem entrar em contato com ninguem.</p>

<h2>Sem acesso ao app? Pelo e-mail</h2>
<ol>
<li>Envie um e-mail para <a href="mailto:lucaszirpoli@gmail.com?subject=Excluir%20minha%20conta%20Atlas">lucaszirpoli@gmail.com</a> a partir do endereco de e-mail cadastrado no app, com o assunto "Excluir minha conta".</li>
<li>Confirmaremos a identidade pelo e-mail cadastrado e processaremos o pedido em ate 15 dias.</li>
<li>Voce recebe uma confirmacao por e-mail quando a exclusao for concluida.</li>
</ol>

<h2>O que e excluido</h2>
<p>Dados de conta (nome, e-mail, senha), perfil, e todo o historico de saude registrado no app: refeicoes, treinos, peso, medidas, sono e agua. Posts, comentarios e conexoes sociais tambem sao removidos.</p>

<h2>O que pode ser mantido</h2>
<p>Registros que a lei exige manter (por exemplo, dados de faturamento de assinaturas, quando aplicavel) sao retidos apenas pelo prazo minimo exigido por lei, de forma isolada do restante do perfil, e depois eliminados.</p>

<p>Para mais detalhes sobre como tratamos dados, veja a <a href="/legal/privacidade">Politica de Privacidade</a>.</p>
</body>
</html>
"""


@app.get("/legal/exclusao-de-conta", response_class=HTMLResponse)
def delete_account_page() -> str:
    return _DELETE_ACCOUNT_HTML
