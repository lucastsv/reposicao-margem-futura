"""
Coletor DATAGRO Indicador do Boi (publico, sem login).

Fontes (SVG):
  boletim_cinco: https://pec.datagro.com/pec/mapas/boletim_cinco.svg
    Tabela boi gordo R$/@ x estado x 5 ultimos dias uteis + media 5d.
    Estados (ordem do SVG): SP, BA, GO, MG, MS, MT, PA, RO.

  nelore       : https://pec.datagro.com/pec/mapas/nelore.svg
    Tabela reposicao Nelore R$/kg vivo x estado x categoria.
    10 estados (ordem por y): SP, MG, MS, MT, GO, TO, PA, PR, RS, RO.
    8 categorias (ordem por x): Desmama M, Bezerro M, Garrote M, Boi Magro M,
                                Desmama F, Bezerra F, Novilha F, Vaca Magra F.

Funcao publica: collect() retorna DatagroSnapshot com:
  - boi_gordo_ms_arroba (R$/@): valor mais recente do MS no boletim_cinco
  - reposicao_ms (dict R$/kg vivo): {desmama, bezerro, garrote, boi_magro} (categorias macho do MS)
  - data_ref (str): data do boletim
"""

from __future__ import annotations
import re
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path

URL_BOLETIM_CINCO = "https://pec.datagro.com/pec/mapas/boletim_cinco.svg"
URL_NELORE = "https://pec.datagro.com/pec/mapas/nelore.svg"

CACHE_DIR = Path(__file__).parent / "cepea_cache"  # mesmo cache pra debug

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REFERER = "https://www.indicadordoboi.com.br/"

# Mapeamento por coordenada y -> estado em nelore.svg (descoberto em 2026-04-29)
NELORE_Y_TO_STATE = {
    240: "SP", 270: "MG", 300: "MS", 330: "MT", 360: "GO",
    420: "TO", 450: "PA", 480: "PR", 510: "RS", 540: "RO",
}
# Mapeamento por coordenada x -> categoria em nelore.svg
NELORE_X_TO_CATEGORY = {
    154: "desmama_m", 233: "bezerro_m", 312: "garrote_m", 391: "boi_magro_m",
    470: "desmama_f", 549: "bezerra_f", 628: "novilha_f", 707: "vaca_magra_f",
}


@dataclass
class DatagroSnapshot:
    boi_gordo_ms_arroba: float            # R$/@
    reposicao_ms: dict[str, float]        # {categoria: R$/kg vivo}
    data_ref: str                         # ex: "28/Abr"


def _baixar(url: str, destino: Path) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Referer": REFERER})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        data = r.read()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(data)
    return data.decode("utf-8", errors="replace")


def _br_to_float(s: str) -> float:
    """Converte '348,72' -> 348.72."""
    return float(s.strip().replace(".", "").replace(",", "."))


def parse_boletim_cinco(svg: str) -> tuple[float, str]:
    """Retorna (boi_gordo_MS_R$/@_ultimo_dia, data_ultimo_dia)."""
    textos = [m.group(1).strip() for m in re.finditer(r"<text[^>]*>([^<]+)</text>", svg)]
    textos = [t for t in textos if t]

    datas = textos[:5]
    resto = textos[5:]

    try:
        idx = resto.index("MS")
    except ValueError as e:
        raise RuntimeError("Estado 'MS' nao encontrado no boletim_cinco") from e

    valores = resto[idx + 1: idx + 7]
    if len(valores) < 5:
        raise RuntimeError(f"Esperado >=5 valores apos MS, achei {len(valores)}")

    ms_ultimo = _br_to_float(valores[4])  # 5o valor = dia mais recente
    data_ultimo = datas[4] if len(datas) >= 5 else "?"
    return ms_ultimo, data_ultimo


def parse_nelore(svg: str, estado: str = "MS") -> dict[str, float]:
    """Retorna dict {categoria: R$/kg} para o estado pedido."""
    pontos: list[tuple[float, float, float]] = []
    for m in re.finditer(r'<text\s+([^>]*?)>([^<]+)</text>', svg):
        attrs = m.group(1)
        texto = m.group(2).strip()
        tm = re.search(r"matrix\(([^)]+)\)", attrs)
        if not tm:
            continue
        nums = re.findall(r"-?\d+(?:\.\d+)?", tm.group(1))
        if len(nums) < 6:
            continue
        x, y = float(nums[4]), float(nums[5])
        if not re.fullmatch(r"-?\d+,\d+", texto):
            continue
        pontos.append((x, y, _br_to_float(texto)))

    state_to_y = {v: k for k, v in NELORE_Y_TO_STATE.items()}
    if estado not in state_to_y:
        raise ValueError(f"Estado nao mapeado em nelore.svg: {estado}")
    y_alvo = state_to_y[estado]

    out: dict[str, float] = {}
    for x_alvo, cat in NELORE_X_TO_CATEGORY.items():
        candidatos = [v for x, y, v in pontos
                      if abs(y - y_alvo) <= 15 and abs(x - x_alvo) <= 15]
        if not candidatos:
            raise RuntimeError(f"Sem valor em nelore.svg para {estado}/{cat} "
                               f"(y~{y_alvo}, x~{x_alvo})")
        out[cat] = candidatos[0]
    return out


def collect() -> DatagroSnapshot:
    CACHE_DIR.mkdir(exist_ok=True)
    svg_boletim = _baixar(URL_BOLETIM_CINCO, CACHE_DIR / "datagro_boletim_cinco.svg")
    svg_nelore = _baixar(URL_NELORE, CACHE_DIR / "datagro_nelore.svg")

    boi_ms_arroba, data_ref = parse_boletim_cinco(svg_boletim)
    nelore_ms = parse_nelore(svg_nelore, "MS")

    # Filtra so as 4 categorias macho que interessam pro pipeline
    reposicao = {k[:-2]: v for k, v in nelore_ms.items() if k.endswith("_m")}

    return DatagroSnapshot(
        boi_gordo_ms_arroba=boi_ms_arroba,
        reposicao_ms=reposicao,
        data_ref=data_ref,
    )


if __name__ == "__main__":
    snap = collect()
    print("=== DATAGRO Indicador do Boi - MS ===")
    print(f"Data ref     : {snap.data_ref}")
    print(f"Boi gordo MS : R$ {snap.boi_gordo_ms_arroba:.2f}/@")
    print(f"Reposicao MS (R$/kg vivo):")
    for cat in ("desmama", "bezerro", "garrote", "boi_magro"):
        print(f"  {cat:>10}: {snap.reposicao_ms[cat]:>6.2f}")
