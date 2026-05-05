"""Utilidades compartilhadas entre o pipeline local (atualizar_planilha)
e o pipeline cloud (pipeline_cloud).

NAO importa nada de Excel/openpyxl/xlwings — fica neutro pro cloud.
"""
from __future__ import annotations

import socket
import time
from urllib.error import URLError

from calibracao import RowState, ANCHOR_ROW, LAST_ROW

# Retry de rede: cobre falhas transitorias (DNS subindo, blip, etc).
# 3 tentativas no total, backoff 30s/60s entre elas.
RETRY_BACKOFFS_SEC = (30, 60)
RETRY_EXCEPTIONS = (URLError, TimeoutError, ConnectionError, socket.gaierror)

# Mapeamento de categorias -> linha Excel (DATAGRO e SCOT compartilham).
SCOT_LINHAS = {
    "desmama":   26,   # 195 kg (B exato)
    "bezerro":   23,   # 240 kg (B exato)
    "garrote":   19,   # 300 kg (B exato)
    "boi_magro": 14,   # 375 kg (B exato)
}
DATAGRO_LINHAS = SCOT_LINHAS


def coleta_com_retry(nome, fn, log, _sleep=time.sleep):
    """Roda fn() com retry em erros de rede. Re-lanca a ultima exception se esgotar."""
    for i, backoff in enumerate((0,) + RETRY_BACKOFFS_SEC):
        if backoff:
            log(f"{nome}: aguardando {backoff}s antes de retentar (tentativa {i+1}/3)")
            _sleep(backoff)
        try:
            return fn()
        except RETRY_EXCEPTIONS as e:
            if i == len(RETRY_BACKOFFS_SEC):
                raise
            log(f"{nome}: falha de rede ({e}); vai retentar")


def computar_O(q, r, s, t) -> float:
    """Replica IFERROR(AVERAGE(Q:T), 0) — ignora celulas vazias/None."""
    vals = [v for v in (q, r, s, t) if v is not None and v > 0]
    return sum(vals) / len(vals) if vals else 0.0


def calcular_B(row: int) -> float:
    """B eh deterministico: B29=150, cada linha pra cima soma 15kg."""
    return 150.0 + (LAST_ROW - row) * 15.0


def linha_por_peso(peso_kg: float, rows: list[RowState]) -> int:
    """Retorna o index (0-based) da row cuja B esta mais proxima de peso_kg."""
    return min(range(len(rows)), key=lambda i: abs(rows[i].B - peso_kg))
