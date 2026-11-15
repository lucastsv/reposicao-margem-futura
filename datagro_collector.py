"""
Coletor DATAGRO Indicador do Boi (publico, sem login).

Fontes (SVG):
  boletim_cinco: https://pec.datagro.com/pec/mapas/boletim_cinco.svg
    Tabela boi gordo R$/@ x estado x 5 ultimos dias uteis + media 5d.
    Estados (ordem do SVG): SP, BA, GO, MG, MS, MT, PA, RO.

  nelore       : https://pec.datagro.com/pec/mapas/nelore.svg
    Tabela reposicao Nelore R$/kg vivo x estado x categoria.
    10 estados (ordem por y): SP, MG, MS, MT, GO, TO, PA, PR, RS, RO (leitura pela ORDEM).
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

# Tabela do nelore.svg (conferida em 15/11/2026 com o SVG desenhado como imagem: o layout e' o
# mesmo desde 29/04/2026). Os numeros sao <text> com transform matrix(...); as LINHAS (estados) e
# as COLUNAS (categorias) sao lidas pela ORDEM das coordenadas, nao por posicao fixa:
#   linhas  y = 247, 279, 311, ..., 535 (passo 32)  -> NELORE_ESTADOS
#   colunas x = 154, 233, 312, ..., 707 (passo 79)  -> NELORE_CATEGORIAS
# Se a Datagro mudar o numero de linhas/colunas, a coleta PARA com erro (nunca le a celula errada).
# Faixas de peso da Datagro (legenda do SVG): desmama 0-180 kg, bezerro 180-240, garrote 240-300,
# boi magro 300-400. Media a vista ponderada de ate 3 dias uteis (por isso oscila em praca com
# poucos negocios, ex.: garrote MS).
NELORE_ESTADOS = ("SP", "MG", "MS", "MT", "GO", "TO", "PA", "PR", "RS", "RO")
NELORE_CATEGORIAS = ("desmama_m", "bezerro_m", "garrote_m", "boi_magro_m",
                     "desmama_f", "bezerra_f", "novilha_f", "vaca_magra_f")
_MESMA_LINHA = 4.0   # textos com y a menos de 4 px sao da mesma linha


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


def _agrupar(valores: list[float], tolerancia: float = _MESMA_LINHA) -> list[float]:
    """Coordenadas distintas (ordenadas), juntando as que diferem menos que a tolerancia."""
    grupos: list[list[float]] = []
    for v in sorted(valores):
        if grupos and v - grupos[-1][-1] < tolerancia:
            grupos[-1].append(v)
        else:
            grupos.append([v])
    return [sum(g) / len(g) for g in grupos]


def ler_tabela_nelore(svg: str) -> dict[str, dict[str, float]]:
    """Tabela inteira {estado: {categoria: R$/kg}}, pela ordem das linhas e colunas do SVG."""
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
        if not re.fullmatch(r"-?\d+,\d+", texto):
            continue
        pontos.append((float(nums[4]), float(nums[5]), _br_to_float(texto)))
    linhas = _agrupar([y for _, y, _ in pontos])
    colunas = _agrupar([x for x, _, _ in pontos], tolerancia=20.0)
    if len(linhas) != len(NELORE_ESTADOS) or len(colunas) != len(NELORE_CATEGORIAS):
        raise RuntimeError(f"nelore.svg mudou de formato: {len(linhas)} linhas x {len(colunas)} colunas "
                           f"(esperado {len(NELORE_ESTADOS)} x {len(NELORE_CATEGORIAS)}); conferir o "
                           "SVG antes de ajustar NELORE_ESTADOS/NELORE_CATEGORIAS")
    tabela: dict[str, dict[str, float]] = {e: {} for e in NELORE_ESTADOS}
    for x, y, v in pontos:
        i = min(range(len(linhas)), key=lambda k: abs(linhas[k] - y))
        j = min(range(len(colunas)), key=lambda k: abs(colunas[k] - x))
        estado, cat = NELORE_ESTADOS[i], NELORE_CATEGORIAS[j]
        if cat in tabela[estado]:
            raise RuntimeError(f"nelore.svg: dois valores em {estado}/{cat}")
        tabela[estado][cat] = v
    faltando = [f"{e}/{c}" for e in NELORE_ESTADOS for c in NELORE_CATEGORIAS if c not in tabela[e]]
    if faltando:
        raise RuntimeError(f"nelore.svg: celulas vazias {faltando[:4]}")
    return tabela


def parse_nelore(svg: str, estado: str = "MS") -> dict[str, float]:
    """Retorna dict {categoria: R$/kg} para o estado pedido."""
    if estado not in NELORE_ESTADOS:
        raise ValueError(f"Estado nao mapeado em nelore.svg: {estado}")
    return dict(ler_tabela_nelore(svg)[estado])


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
