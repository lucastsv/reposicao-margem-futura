# Setup do CEPEA local runner

Por que: **CEPEA bloqueia IPs de datacenter** (GH Actions/Azure dao 403),
entao a coleta CEPEA precisa rodar de IP brasileiro residencial — no seu PC.

O runner faz: coleta -> serializa em `data/cepea_snapshot.json` -> commit+push
se mudou. O pipeline cloud le esse snapshot via `git checkout`.

## 1. Validar manualmente uma vez

```powershell
cd c:\PYTHON\projeto_automacao_gerencial
.\venv\Scripts\python.exe cepea_local_runner.py
```

Deve gerar/atualizar `data/cepea_snapshot.json`, commitar e pushar.
Verificar no GitHub se o commit chegou.

## 2. Configurar Task Scheduler (Windows)

Criar tarefa agendada que rode todo dia 11h **mesmo se o PC estiver desligado/dormindo**:

### Via Task Scheduler GUI
1. Abrir **Task Scheduler** (taskschd.msc)
2. **Create Task** (nao "Basic Task" — precisa de opcoes avancadas)
3. **General**:
   - Name: `CEPEA Local Runner`
   - Run only when user is logged on  -> **Run whether user is logged on or not** (usa sua senha do Windows)
   - **Run with highest privileges**
4. **Triggers**:
   - Trigger 1: **Daily** as 11:00:00
   - Trigger 2: **At startup** (cobre caso o PC tenha ficado desligado as 11h)
5. **Actions**:
   - Program: `C:\PYTHON\projeto_automacao_gerencial\venv\Scripts\python.exe`
   - Arguments: `cepea_local_runner.py`
   - Start in: `C:\PYTHON\projeto_automacao_gerencial`
6. **Conditions**:
   - **Wake the computer to run this task** (acorda do sleep)
   - Desmarcar "Start the task only if the computer is on AC power" se quiser rodar tb na bateria
7. **Settings**:
   - **Run task as soon as possible after a scheduled start is missed** (catchup quando volta de desligado)
   - If the task fails, **restart every 30 minutes**, attempt up to **3 times**

### Via PowerShell (alternativa em CLI)

```powershell
$action = New-ScheduledTaskAction `
    -Execute "C:\PYTHON\projeto_automacao_gerencial\venv\Scripts\python.exe" `
    -Argument "cepea_local_runner.py" `
    -WorkingDirectory "C:\PYTHON\projeto_automacao_gerencial"

$trigger1 = New-ScheduledTaskTrigger -Daily -At 11:00am
$trigger2 = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 30) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -RunLevel Highest

Register-ScheduledTask -TaskName "CEPEA Local Runner" `
    -Action $action -Trigger $trigger1, $trigger2 `
    -Settings $settings -Principal $principal -Description "Atualiza data/cepea_snapshot.json e push pro GitHub"
```

## 3. Verificar se ta rodando

- `Get-ScheduledTask -TaskName "CEPEA Local Runner" | Get-ScheduledTaskInfo`
- Logs em `c:\PYTHON\projeto_automacao_gerencial\logs\cepea_runner_YYYYMMDD.log`
- Commits aparecem em `https://github.com/lucastsv/reposicao-margem-futura/commits/main`
  com mensagem padrao: `data: cepea snapshot YYYY-MM-DD (coletado YYYY-MM-DD HH:MM)`

## 4. Tolerancia a atraso

O `pipeline_cloud.py`:
- Usa **sempre o ultimo snapshot disponivel** (nao falha se desatualizado)
- Loga a idade do snapshot
- Emite **aviso** se snapshot tem >3 dias (provavel problema no local runner)

Entao se o PC ficar desligado uns dias, o cloud continua rodando com o
ultimo snapshot — eventualmente alerta no log se ficar muito velho.
