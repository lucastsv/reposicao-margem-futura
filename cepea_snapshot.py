"""Serializa/carrega BezerroSnapshot via JSON em disco.

Usado pelo pipeline cloud (que NAO consegue acessar CEPEA por bloqueio de IP
de datacenter) — le do JSON commitado pelo runner local.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from cepea_collector import BezerroSnapshot

PROJECT_ROOT = Path(__file__).parent
SNAPSHOT_PATH = PROJECT_ROOT / "data" / "cepea_snapshot.json"


def save(snap: BezerroSnapshot, *, path: Path = SNAPSHOT_PATH,
         coletado_em: datetime | None = None) -> None:
    """Serializa BezerroSnapshot pra JSON. Datas viram strings ISO."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "media_4d_preco": snap.media_4d_preco,
        "peso_medio_kg": snap.peso_medio_kg,
        "data_ultimo_preco": snap.data_ultimo_preco.isoformat(),
        "data_ultimo_peso": snap.data_ultimo_peso.isoformat(),
        "ultimos_4_precos": [[d.isoformat(), v] for d, v in snap.ultimos_4_precos],
        "coletado_em": (coletado_em or datetime.now()).isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load(path: Path = SNAPSHOT_PATH) -> tuple[BezerroSnapshot, datetime]:
    """Carrega BezerroSnapshot + timestamp da coleta. Levanta FileNotFoundError se ausente."""
    if not path.exists():
        raise FileNotFoundError(f"Snapshot CEPEA nao encontrado em {path}. "
                                "Rode cepea_local_runner.py localmente primeiro.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    snap = BezerroSnapshot(
        media_4d_preco=float(payload["media_4d_preco"]),
        peso_medio_kg=float(payload["peso_medio_kg"]),
        data_ultimo_preco=date.fromisoformat(payload["data_ultimo_preco"]),
        data_ultimo_peso=date.fromisoformat(payload["data_ultimo_peso"]),
        ultimos_4_precos=[(date.fromisoformat(d), float(v))
                          for d, v in payload["ultimos_4_precos"]],
    )
    coletado_em = datetime.fromisoformat(payload["coletado_em"])
    return snap, coletado_em
