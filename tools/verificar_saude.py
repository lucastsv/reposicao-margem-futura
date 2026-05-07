"""
Relatorio semanal de saude do pipeline AutomacaoGerencial-MargemFutura.

Le `logs/atualizar_*.log` dos ultimos 7 dias e gera `logs/saude_<YYYYMMDD>.md`
com status verde/amarelo/vermelho.

Considera apenas runs do scheduler (janela 19:00-20:30) para o calculo de
saude. Runs manuais fora dessa janela sao listados a parte como informativo
e NAO afetam o status. A task agendada roda seg-sex apenas; sabados e
domingos nao contam como dias esperados.

Status:
- VERDE   : todo dia util esperado teve run scheduler bem-sucedido
- AMARELO : ao menos 1 dia util sem run (PC desligado / scheduler skipou)
- VERMELHO: ao menos 1 run scheduler com ERRO

Uso direto: python tools/verificar_saude.py
"""

from __future__ import annotations
import re
import sys
from datetime import datetime, timedelta, time, date
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
PADRAO_FILENAME = re.compile(r"atualizar_(\d{8})_(\d{6})\.log")
JANELA_DIAS = 7

# Task agendada 19:30 seg-sex. Janela aceita atrasos do scheduler.
JANELA_INICIO = time(19, 0)
JANELA_FIM = time(20, 30)
HORARIO_AGENDADO = time(19, 30)


def dias_uteis_esperados(hoje: datetime) -> list[date]:
    """Dias uteis (seg-sex) nos ultimos JANELA_DIAS dias.
    Exclui hoje se ainda nao chegou em HORARIO_AGENDADO."""
    cutoff = (hoje - timedelta(days=JANELA_DIAS)).date()
    dias: list[date] = []
    d = cutoff + timedelta(days=1)
    while d <= hoje.date():
        if d.weekday() < 5:
            dias.append(d)
        d += timedelta(days=1)
    if dias and dias[-1] == hoje.date() and hoje.time() < HORARIO_AGENDADO:
        dias.pop()
    return dias


def parse_log(path: Path) -> tuple[str, str]:
    """Retorna (status, detalhe) de um log. status in {'ok', 'falha'}."""
    content = path.read_text(encoding="utf-8", errors="replace")
    erro_match = re.search(r"ERRO[:\s]\s*([^\n]+)", content)
    finalizado = "[" in content and " Fim." in content
    if erro_match:
        return "falha", erro_match.group(1).strip()
    if not finalizado:
        return "falha", "log incompleto (sem 'Fim.')"
    r_match = re.search(r"Escrito R(\d+)\s*=\s*([\d,.]+)", content)
    valor_r = r_match.group(2) if r_match else "(R nao registrado)"
    return "ok", valor_r


def main() -> int:
    if not LOG_DIR.exists():
        print(f"ERRO: diretorio de logs nao existe: {LOG_DIR}")
        return 2

    hoje = datetime.now()
    cutoff = hoje - timedelta(days=JANELA_DIAS)
    dias_esperados = dias_uteis_esperados(hoje)

    # Por dia, mantem apenas o ultimo run scheduler (caso raro de duplicata).
    runs_scheduler: dict[date, tuple[datetime, str, str]] = {}
    runs_manuais: list[tuple[datetime, str, str]] = []

    for f in sorted(LOG_DIR.glob("atualizar_*.log")):
        m = PADRAO_FILENAME.match(f.name)
        if not m:
            continue
        try:
            ts = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        except ValueError:
            continue
        if ts < cutoff:
            continue

        status, detalhe = parse_log(f)
        is_scheduler = JANELA_INICIO <= ts.time() <= JANELA_FIM
        if is_scheduler:
            runs_scheduler[ts.date()] = (ts, status, detalhe)
        else:
            runs_manuais.append((ts, status, detalhe))

    sucessos = sum(1 for _, s, _ in runs_scheduler.values() if s == "ok")
    falhas = sum(1 for _, s, _ in runs_scheduler.values() if s == "falha")
    dias_com_run = set(runs_scheduler.keys())
    dias_faltando = [d for d in dias_esperados if d not in dias_com_run]

    if falhas > 0:
        status_global = "VERMELHO"
    elif dias_faltando:
        status_global = "AMARELO"
    else:
        status_global = "VERDE"

    hoje_str = hoje.strftime("%Y%m%d")
    relatorio = LOG_DIR / f"saude_{hoje_str}.md"

    DIA_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]

    with relatorio.open("w", encoding="utf-8") as fp:
        fp.write("# Saude do pipeline Margem Futura\n\n")
        fp.write(f"Gerado em {hoje:%Y-%m-%d %H:%M}\n\n")
        fp.write(f"## Status: **{status_global}**\n\n")
        fp.write(f"Janela: ultimos {JANELA_DIAS} dias. ")
        fp.write(f"Considera apenas runs do scheduler "
                 f"({JANELA_INICIO:%H:%M}-{JANELA_FIM:%H:%M}); ")
        fp.write("runs manuais sao informativos.\n\n")
        fp.write(f"- Dias uteis esperados: **{len(dias_esperados)}**\n")
        fp.write(f"- Runs scheduler: **{len(runs_scheduler)}** "
                 f"(sucessos: {sucessos}, falhas: {falhas})\n")
        fp.write(f"- Dias sem run: **{len(dias_faltando)}**\n\n")

        ok_list = sorted(
            (ts, det) for ts, s, det in runs_scheduler.values() if s == "ok"
        )
        falha_list = sorted(
            (ts, det) for ts, s, det in runs_scheduler.values() if s == "falha"
        )

        if ok_list:
            fp.write("## Sucessos (scheduler)\n\n")
            fp.write("| Data | Hora | R escrito |\n")
            fp.write("|------|------|-----------|\n")
            for ts, valor in ok_list:
                fp.write(f"| {ts:%Y-%m-%d} | {ts:%H:%M:%S} | {valor} |\n")
            fp.write("\n")

        if falha_list:
            fp.write("## Falhas (scheduler)\n\n")
            fp.write("| Data | Hora | Mensagem |\n")
            fp.write("|------|------|----------|\n")
            for ts, msg in falha_list:
                fp.write(f"| {ts:%Y-%m-%d} | {ts:%H:%M:%S} | `{msg}` |\n")
            fp.write("\n")

        if dias_faltando:
            fp.write("## Dias uteis sem run scheduler\n\n")
            for d in dias_faltando:
                fp.write(f"- {d:%Y-%m-%d} ({DIA_SEMANA[d.weekday()]})\n")
            fp.write("\n")

        if runs_manuais:
            fp.write("## Runs manuais (informativo, nao afeta status)\n\n")
            fp.write("| Data | Hora | Status | Detalhe |\n")
            fp.write("|------|------|--------|---------|\n")
            for ts, s, det in sorted(runs_manuais):
                fp.write(f"| {ts:%Y-%m-%d} | {ts:%H:%M:%S} | {s} | `{det}` |\n")
            fp.write("\n")

        if not dias_esperados:
            fp.write("> Janela sem dias uteis. Status trivialmente verde.\n")

    print(f"Relatorio: {relatorio}")
    print(f"Status: {status_global}  "
          f"(esperados: {len(dias_esperados)} dias uteis, "
          f"runs scheduler: {len(runs_scheduler)} [ok={sucessos} falha={falhas}], "
          f"manuais: {len(runs_manuais)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
