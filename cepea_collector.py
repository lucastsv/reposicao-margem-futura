"""
Coletor do indicador CEPEA Bezerro MS.

Endpoints (retornam .xls OLE2 com serie historica):
  preco: https://cepea.org.br/br/indicador/series/bezerro.aspx?id=8
  peso : https://cepea.org.br/br/indicador/series/bezerro.aspx?id=174

Funcao publica: collect() retorna BezerroSnapshot com:
  - media_4d_preco (R$/cabeca): media dos ultimos 4 dias publicados
  - peso_medio_kg: peso medio mais recente (kg vivo)
  - data_ultimo_preco / data_ultimo_peso (datas dos valores mais recentes)

XLS sao cacheados em ./cepea_cache/ pra debug.
"""

from __future__ import annotations
import ssl
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import xlrd

URL_PRECO = "https://cepea.org.br/br/indicador/series/bezerro.aspx?id=8"
URL_PESO = "https://cepea.org.br/br/indicador/series/bezerro.aspx?id=174"

CACHE_DIR = Path(__file__).parent / "cepea_cache"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class BezerroSnapshot:
    media_4d_preco: float        # R$/cabeca
    peso_medio_kg: float         # kg vivo
    data_ultimo_preco: date
    data_ultimo_peso: date
    ultimos_4_precos: list[tuple[date, float]]   # mais antigo -> mais recente


def _baixar_xls(url: str, destino: Path) -> None:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
        data = r.read()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(data)


def _parse_xls_serie(path: Path, n_cols_valor: int = 1) -> list[tuple[date, list[float]]]:
    """
    Retorna lista [(data, [valor1, valor2, ...])] em ordem cronologica crescente.
    n_cols_valor=1 para peso (1 col), 2 para preco (BRL + USD).
    """
    wb = xlrd.open_workbook(str(path), ignore_workbook_corruption=True)
    ws = wb.sheet_by_index(0)
    out = []
    for i in range(ws.nrows):
        row = ws.row_values(i)
        if not row or not row[0]:
            continue
        try:
            dt = datetime.strptime(str(row[0]).strip(), "%d/%m/%Y").date()
            valores = [float(row[1 + k]) for k in range(n_cols_valor)]
        except (ValueError, TypeError, IndexError):
            continue
        out.append((dt, valores))
    out.sort(key=lambda x: x[0])
    return out


def collect() -> BezerroSnapshot:
    CACHE_DIR.mkdir(exist_ok=True)
    xls_preco = CACHE_DIR / "bezerro_preco.xls"
    xls_peso = CACHE_DIR / "bezerro_peso.xls"

    _baixar_xls(URL_PRECO, xls_preco)
    _baixar_xls(URL_PESO, xls_peso)

    serie_preco = _parse_xls_serie(xls_preco, n_cols_valor=2)  # BRL, USD
    serie_peso = _parse_xls_serie(xls_peso, n_cols_valor=1)

    if len(serie_preco) < 4:
        raise RuntimeError(f"Serie de preco com menos de 4 pontos ({len(serie_preco)})")
    if not serie_peso:
        raise RuntimeError("Serie de peso vazia")

    ultimos_4 = serie_preco[-4:]
    ultimos_4_brl = [(d, vals[0]) for d, vals in ultimos_4]
    media = sum(v for _, v in ultimos_4_brl) / 4

    data_ultimo_preco, _ = serie_preco[-1]
    data_ultimo_peso, peso_vals = serie_peso[-1]
    peso_medio = peso_vals[0]

    return BezerroSnapshot(
        media_4d_preco=media,
        peso_medio_kg=peso_medio,
        data_ultimo_preco=data_ultimo_preco,
        data_ultimo_peso=data_ultimo_peso,
        ultimos_4_precos=ultimos_4_brl,
    )


if __name__ == "__main__":
    snap = collect()
    print("=== CEPEA Bezerro MS ===")
    print(f"Peso medio   : {snap.peso_medio_kg:.1f} kg ({snap.data_ultimo_peso})")
    print(f"Ultimos 4 dias de preco (R$/cab):")
    for d, v in snap.ultimos_4_precos:
        print(f"  {d}  {v:>10,.2f}")
    print(f"Media 4 dias : R$ {snap.media_4d_preco:,.2f}")
    print(f"Data ult preco: {snap.data_ultimo_preco}")
