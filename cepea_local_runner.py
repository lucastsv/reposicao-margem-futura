"""Runner local CEPEA: coleta -> snapshot JSON -> commit+push se mudou.

Roda no PC (Task Scheduler 11h diario + WakeToRun + catchup) porque CEPEA
bloqueia IPs de datacenter (GH Actions/Azure dao 403). Cloud le o snapshot
versionado deste arquivo.

Uso direto: python cepea_local_runner.py

Convencoes:
- Idempotente: nao commita se snapshot nao mudou
- Falha rapida em erro de coleta (Task Scheduler retry no proximo trigger)
- Loga em logs/cepea_runner_YYYYMMDD.log
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cepea_collector import collect as collect_cepea
from cepea_snapshot import save as save_snapshot, SNAPSHOT_PATH

PROJECT_ROOT = Path(__file__).parent
LOG_DIR = PROJECT_ROOT / "logs"


def _git(*args, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, encoding="utf-8", check=check,
    )


def _snapshot_payload(path: Path) -> dict | None:
    """Le JSON do snapshot atual; retorna None se nao existe ou invalido."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _payloads_diferem(novo: dict, antigo: dict | None) -> bool:
    """Compara campos de dados (ignora 'coletado_em' que muda toda execucao)."""
    if antigo is None:
        return True
    keys = ("media_4d_preco", "peso_medio_kg",
            "data_ultimo_preco", "data_ultimo_peso", "ultimos_4_precos")
    return any(novo.get(k) != antigo.get(k) for k in keys)


def main() -> int:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"cepea_runner_{datetime.now():%Y%m%d}.log"

    def log(msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    log("Inicio CEPEA local runner.")

    try:
        snap = collect_cepea()
    except Exception as e:
        log(f"ERRO coleta CEPEA: {e}")
        return 1
    log(f"CEPEA OK: peso={snap.peso_medio_kg:.1f}kg "
        f"({snap.data_ultimo_peso}), media4d=R${snap.media_4d_preco:,.2f} "
        f"({snap.data_ultimo_preco})")

    antigo = _snapshot_payload(SNAPSHOT_PATH)
    save_snapshot(snap)
    log(f"Snapshot escrito em {SNAPSHOT_PATH.relative_to(PROJECT_ROOT)}")

    novo = _snapshot_payload(SNAPSHOT_PATH)
    if not _payloads_diferem(novo, antigo):
        log("Sem mudancas vs ultimo snapshot — nada a commitar.")
        return 0

    # Commit + push
    try:
        _git("add", str(SNAPSHOT_PATH.relative_to(PROJECT_ROOT)))
        msg = (f"data: cepea snapshot {snap.data_ultimo_preco} "
               f"(coletado {datetime.now():%Y-%m-%d %H:%M})")
        _git("commit", "-m", msg)
        log(f"Commit: {msg}")
        _git("push", "origin", "HEAD")
        log("Push OK -> origin/main")
    except subprocess.CalledProcessError as e:
        log(f"ERRO git: {e.stderr.strip() if e.stderr else e}")
        return 2

    log("Fim.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
