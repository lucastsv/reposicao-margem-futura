# Projeto Automacao Gerencial

Silo de automacoes que alimentam planilhas gerenciais a partir de sistemas
financeiros/operacionais externos.

Este repo agrupa subprojetos distintos. Cada subprojeto tem sua propria
fonte de dados, seu proprio destino (planilha ou notificacao), e seu
proprio agendamento.

## Subprojetos

### Margem Futura / Custos de Reposicao  *(em producao)*

Calibra agios da aba `Preco Reposicao` da planilha
`Tres Marias - Calculo de Margem Futura.xlsm` a partir de cotacoes
publicas (CEPEA, DATAGRO, SCOT) e envia tabela diaria pelo Telegram.

Arquitetura **hibrida local + cloud**:

- **Local** (Task Scheduler 19:30): coleta + escrita no `.xlsm`
  preservando historico Excel. Disparado por `atualizar_planilha.py`.
- **Local** (Task Scheduler "CEPEA Local Runner", 11:00 + AtLogOn):
  coleta CEPEA e da push do snapshot pro repo
  `github.com/lucastsv/reposicao-margem-futura`. Existe porque CEPEA
  bloqueia IPs Azure/datacenter.
- **Cloud** (GitHub Actions, cron 18:30 BRT): le snapshot CEPEA + coleta
  DATAGRO/SCOT direto, calibra, gera PNG (matplotlib puro, sem Excel) e
  envia pelo Telegram. Disparado por `pipeline_cloud.py`.

Detalhes em `docs/SETUP_CLOUD.md` e `docs/SETUP_LOCAL_CEPEA.md`.

### Boviplan / Fluxo de Caixa  *(em desenvolvimento)*

Vive em `Claude Cowork/`. Pasta no `.gitignore` por conter dados
financeiros sensiveis. Sem integracao com o pipeline da Margem Futura.

## Estrutura de pastas

```
projeto_automacao_gerencial/
|
| --- subprojeto Margem Futura ---
|
+-- atualizar_planilha.py        Local 19:30: escreve no .xlsm
+-- cepea_local_runner.py        Local 11:00: snapshot CEPEA -> GitHub
+-- pipeline_cloud.py            GitHub Actions 18:30: render + Telegram
+-- pipeline_core.py             Modulo neutro (sem Excel) compartilhado
+-- calibracao.py                Algoritmo de calibracao geometrica
+-- excel_runner.py              Entry point chamado pelo VBA da planilha
+-- cepea_collector.py           Coletor CEPEA (XLS publico)
+-- cepea_snapshot.py            Persistencia do snapshot CEPEA
+-- datagro_collector.py         Coletor DATAGRO (parse SVG)
+-- scot_collector.py            Coletor SCOT (parse HTML)
+-- render_tabela_matplotlib.py  Render PNG do range B4:L30 (cloud)
+-- gerar_imagem.py              Render PNG via Excel COM (local; preview)
+-- telegram_notify.py           Envio de PNG via Bot Telegram
+-- requirements.txt             Deps locais (xlwings, openpyxl, etc)
+-- requirements-cloud.txt       Deps cloud (matplotlib + xlrd)
|
+-- planilha/                    Planilha .xlsm + VBA_macro.bas
+-- docs/                        SETUP_CLOUD.md, SETUP_LOCAL_CEPEA.md
+-- tools/                       Scripts auxiliares (setup, diagnostico)
|   +-- setup_botao.py             Setup one-time: injeta VBA + botao
|   +-- obter_chat_id.py           Helper Telegram (chat_id)
|   +-- validar_calibracao.py      Valida calibrate() vs estado da planilha
|   +-- verificar_saude.py         Relatorio semanal de logs
|
+-- data/                        Snapshots versionados (CEPEA)
+-- logs/                        Logs e PNGs gerados
+-- cepea_cache/                 Cache do coletor CEPEA
+-- venv/                        Virtualenv Python local
+-- .github/workflows/           Workflow do pipeline cloud
|
| --- subprojeto Boviplan ---
|
+-- Claude Cowork/               Boviplan / fluxo de caixa (gitignored)
```

## Por que tudo da Margem Futura na raiz?

Por motivos historicos, os scripts da Margem Futura ocupam a raiz. Eles
**nao** podem ser movidos pra subpasta `margem_futura/` sem refatorar
varios pontos de integracao:

- `xlwings.conf` (aba oculta da planilha) tem `PYTHONPATH` apontando pra
  raiz. O VBA chama `import excel_runner`. Mover quebra o botao
  `Recalibrar Agios`.
- Task Scheduler `AutomacaoGerencial-MargemFutura` e `CEPEA Local Runner`
  tem `Iniciar em: C:\PYTHON\projeto_automacao_gerencial`.
- Workflow `.github/workflows/cloud_pipeline.yml` chama
  `python pipeline_cloud.py` na raiz do repo `reposicao-margem-futura`.

**Quando o subprojeto Boviplan ganhar scripts Python proprios**, vale
fazer o refactor maior: criar `margem_futura/` e `boviplan/` lado a
lado, atualizar workflow + scheduler + xlwings.conf de uma vez.

## Tarefas agendadas (Task Scheduler)

| Nome                              | Agendamento           | Acao                                      |
|-----------------------------------|-----------------------|-------------------------------------------|
| AutomacaoGerencial-MargemFutura   | Diaria 19:30          | `python atualizar_planilha.py`            |
| CEPEA Local Runner                | Diaria 11:00 + AtLogOn | `python cepea_local_runner.py`            |

Ambas com `Iniciar em: C:\PYTHON\projeto_automacao_gerencial`.

## Repositorio cloud

`github.com/lucastsv/reposicao-margem-futura` (publico). Workflow
`cloud_pipeline.yml` roda diariamente as 18:30 BRT. Secrets
`TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID` configurados via
`gh secret set`.
