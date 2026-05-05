# Setup do pipeline cloud (GitHub Actions)

Instrucoes para colocar o `pipeline_cloud.py` rodando todo dia 18:30 BRT
no GitHub Actions sem depender do PC local.

## 1. Inicializar repo git local

```bash
cd c:/PYTHON/projeto_automacao_gerencial
git init
git add .
git commit -m "Inicial: pipeline cloud-ready (margem futura)"
```

## 2. Criar repo no GitHub

Opcao A (web): criar repo PRIVADO em `github.com/SEU_USUARIO/margem-futura`
(ou outro nome) e seguir as instrucoes pra "push existing repository".

Opcao B (gh CLI):
```bash
winget install GitHub.cli
gh auth login
gh repo create margem-futura --private --source=. --push
```

## 3. Configurar Secrets

No repo do GitHub, ir em **Settings -> Secrets and variables -> Actions**
e criar:

| Nome                    | Valor                                          |
|-------------------------|------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`    | token do bot (vide telegram_config.json local) |
| `TELEGRAM_CHAT_ID`      | chat_id (vide telegram_config.json local)      |

**Importante**: NUNCA commitar o `telegram_config.json`. Ele esta no `.gitignore`.

## 4. Validar o workflow

Apos primeiro push, ir em **Actions -> Margem Futura - pipeline cloud**
e clicar **Run workflow** pra testar manualmente antes de esperar o cron.

## 5. Cron

O workflow esta agendado para `30 21 * * *` (21:30 UTC = 18:30 BRT).
Brasil nao tem horario de verao, entao fica fixo o ano todo.

GitHub schedule tem delay tipico de 5-15min em horarios de pico —
se for critico ter o disparo exatamente em 18:30, considere antecipar
pra `15 21 * * *` (18:15 BRT) pra dar margem.

## 6. Coexistencia com pipeline local

- `atualizar_planilha.py` (local): continua escrevendo no `.xlsm`,
  rodando via Task Scheduler 19:30 BRT. Gera preview local mas
  **NAO envia mais Telegram** (pra evitar mensagem duplicada).
- `pipeline_cloud.py` (cloud): coleta + calcula tudo em Python,
  renderiza imagem custom (matplotlib), envia Telegram.

Telegram fica exclusivo do cloud.

## 7. Custos

- GitHub Actions: gratis pra repo privado ate 2000 min/mes
  (este pipeline usa ~30 segundos/dia = ~15 min/mes)
- Coletores: APIs publicas, sem custo

## 8. Troubleshooting

- **Falha de coleta**: ver logs do run no Actions UI
- **Telegram nao chega**: confirmar Secrets configurados; rodar manualmente
- **Cron nao disparou**: GitHub as vezes pula schedule em horarios de pico;
  o workflow_dispatch sempre funciona pra disparar na mao
- **Imagem feia**: rodar `python pipeline_cloud.py` localmente, ajustar
  `render_tabela_matplotlib.py`, commit + push, validar no proximo run
