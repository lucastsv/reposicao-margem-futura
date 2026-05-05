"""
Coletor SCOT Consultoria - Cotacoes de Reposicao (publico, sem login).

Fonte: https://www.scotconsultoria.com.br/cotacoes/reposicao/?ref=smnb

Tabela MACHO NELORE — 4 categorias x 3 colunas (R$/cab, R$/kg, Troca em @) por estado.
Categorias e pesos de referencia (NELORE):
  - Boi Magro : 375 kg / 12,5@
  - Garrote   : 18 M, 300 kg / 10@
  - Bezerro   : 12 M, 240 kg / 8@
  - Desmama   :  8 M, 195 kg / 6,5@

Coleta os 4 R$/cab do estado MS (Mato Grosso do Sul). Atualizacao diaria ~18h00.
"""

from __future__ import annotations
import re
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path

URL = "https://www.scotconsultoria.com.br/cotacoes/reposicao/?ref=smnb"
CACHE = Path(__file__).parent / "cepea_cache" / "scot_reposicao.html"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ScotSnapshot:
    # R$/cabeca, MS, MACHO NELORE, valores extraidos da tabela
    boi_magro_cab: float    # 375 kg
    garrote_cab: float      # 300 kg
    bezerro_cab: float      # 240 kg
    desmama_cab: float      # 195 kg
    data_ref: str           # ex: "28/04/2026"


def _br_to_float(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _baixar(url: str = URL) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
        html = r.read().decode("utf-8", errors="replace")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(html, encoding="utf-8")
    return html


def parse(html: str, estado: str = "MS") -> ScotSnapshot:
    # Remove scripts/styles e tags
    texto = re.sub(r"<script.*?</script>", "", html, flags=re.DOTALL)
    texto = re.sub(r"<style.*?</style>", "", texto, flags=re.DOTALL)
    texto = re.sub(r"<[^>]+>", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    # Localiza bloco MACHO NELORE - DD/MM/YYYY ate proxima secao (MACHO MESTICO ou FEMEA)
    m = re.search(
        r"MACHO NELORE\s*-\s*(\d{2}/\d{2}/\d{4})(.*?)(?=MACHO MESTI|MACHO  MESTI|F[ÊE]MEA|$)",
        texto,
    )
    if not m:
        raise RuntimeError("Bloco 'MACHO NELORE' nao encontrado no HTML do SCOT")
    data_ref = m.group(1)
    bloco = m.group(2)

    # Linha do estado: 'MS' seguido de exatamente 12 numeros R$ (formato BR com virgula)
    pat = rf"\b{re.escape(estado)}\b((?:\s+-?\d+(?:\.\d+)?,\d+){{12}})"
    rm = re.search(pat, bloco)
    if not rm:
        raise RuntimeError(f"Linha do estado '{estado}' nao encontrada em MACHO NELORE")
    nums = re.findall(r"-?\d+(?:\.\d+)?,\d+", rm.group(1))
    if len(nums) != 12:
        raise RuntimeError(f"Esperado 12 valores para {estado}, achei {len(nums)}")

    # Ordem das colunas: Boi Magro [R$/cab, R$/kg, Troca], Garrote [...], Bezerro [...], Desmama [...]
    boi_magro = _br_to_float(nums[0])
    garrote = _br_to_float(nums[3])
    bezerro = _br_to_float(nums[6])
    desmama = _br_to_float(nums[9])

    return ScotSnapshot(
        boi_magro_cab=boi_magro,
        garrote_cab=garrote,
        bezerro_cab=bezerro,
        desmama_cab=desmama,
        data_ref=data_ref,
    )


def collect() -> ScotSnapshot:
    return parse(_baixar(), "MS")


if __name__ == "__main__":
    snap = collect()
    print(f"=== SCOT MACHO NELORE - MS ({snap.data_ref}) ===")
    print(f"Boi Magro (375 kg) : R$/cab {snap.boi_magro_cab:>10,.2f}")
    print(f"Garrote   (300 kg) : R$/cab {snap.garrote_cab:>10,.2f}")
    print(f"Bezerro   (240 kg) : R$/cab {snap.bezerro_cab:>10,.2f}")
    print(f"Desmama   (195 kg) : R$/cab {snap.desmama_cab:>10,.2f}")
