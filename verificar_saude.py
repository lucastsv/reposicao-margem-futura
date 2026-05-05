"""
Relatorio semanal de saude do pipeline AutomacaoGerencial-MargemFutura.

Le `logs/atualizar_*.log` dos ultimos 7 dias, conta sucessos/falhas, e
gera `logs/saude_<YYYYMMDD>.md` com status verde/amarelo/vermelho.

Status:
- VERDE   : 7/7 runs concluidos sem erro nos ultimos 7 dias
- AMARELO : runs faltando (script nao executou em algum dia)
- VERMELHO: ao menos 1 run com ERRO

Uso direto: python verificar_saude.py
"""

from __future__ import annotations
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
PADRAO_FILENAME = re.compile(r"atualizar_(\d{8})_(\d{6})\.log")
ESPERADO_RUNS = 7  # 1 por dia, todos os dias (CEPEA repete em fim de semana sem erro)


def main() -> int:
    if not LOG_DIR.exists():
        print(f"ERRO: diretorio de logs nao existe: {LOG_DIR}")
        return 2

    cutoff = datetime.now() - timedelta(days=7)
    runs: list[tuple[datetime, Path, str]] = []  # (timestamp, path, "ok"/"falha")
    detalhes_ok: list[tuple[datetime, str]] = []  # (ts, valor R escrito)
    detalhes_falha: list[tuple[datetime, str]] = []  # (ts, mensagem de erro)

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

        content = f.read_text(encoding="utf-8", errors="replace")
        erro_match = re.search(r"ERRO[:\s]\s*([^\n]+)", content)
        finalizado = "[" in content and " Fim." in content

        if erro_match:
            runs.append((ts, f, "falha"))
            detalhes_falha.append((ts, erro_match.group(1).strip()))
        elif not finalizado:
            runs.append((ts, f, "falha"))
            detalhes_falha.append((ts, "log incompleto (sem 'Fim.')"))
        else:
            r_match = re.search(r"Escrito R(\d+)\s*=\s*([\d,.]+)", content)
            valor_r = r_match.group(2) if r_match else "(R nao registrado)"
            runs.append((ts, f, "ok"))
            detalhes_ok.append((ts, valor_r))

    sucessos = sum(1 for _, _, s in runs if s == "ok")
    falhas = sum(1 for _, _, s in runs if s == "falha")
    total = len(runs)

    if falhas > 0:
        status = "VERMELHO"
    elif total < ESPERADO_RUNS:
        status = "AMARELO"
    else:
        status = "VERDE"

    hoje = datetime.now().strftime("%Y%m%d")
    relatorio = LOG_DIR / f"saude_{hoje}.md"

    with relatorio.open("w", encoding="utf-8") as fp:
        fp.write(f"# Saude do pipeline Margem Futura\n\n")
        fp.write(f"Gerado em {datetime.now():%Y-%m-%d %H:%M}\n\n")
        fp.write(f"## Status: **{status}**\n\n")
        fp.write(f"- Runs encontrados (ultimos 7 dias): **{total}** / {ESPERADO_RUNS} esperados\n")
        fp.write(f"- Sucessos: **{sucessos}**\n")
        fp.write(f"- Falhas: **{falhas}**\n\n")

        if detalhes_ok:
            fp.write("## Sucessos\n\n")
            fp.write("| Data | Hora | R escrito |\n")
            fp.write("|------|------|-----------|\n")
            for ts, valor in detalhes_ok:
                fp.write(f"| {ts:%Y-%m-%d} | {ts:%H:%M:%S} | {valor} |\n")
            fp.write("\n")

        if detalhes_falha:
            fp.write("## Falhas\n\n")
            fp.write("| Data | Hora | Mensagem |\n")
            fp.write("|------|------|----------|\n")
            for ts, msg in detalhes_falha:
                fp.write(f"| {ts:%Y-%m-%d} | {ts:%H:%M:%S} | `{msg}` |\n")
            fp.write("\n")

        if total == 0:
            fp.write("> **Nenhum run encontrado nos ultimos 7 dias.** Verifique se a tarefa "
                    "`AutomacaoGerencial-MargemFutura` esta habilitada no Task Scheduler.\n")

    print(f"Relatorio: {relatorio}")
    print(f"Status: {status}  ({sucessos} ok / {falhas} falha / {total} total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
