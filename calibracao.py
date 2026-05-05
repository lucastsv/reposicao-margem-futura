"""
Calibracao de agios da aba "Preco Reposicao" de Tres Marias - Calculo de Margem Futura.

Algoritmo: interpolacao geometrica entre ancoras.
- Ancora: linha com cotacao de mercado (O > 0). Linha 7 (boi gordo) eh sempre a ancora
  inicial — H7 vem manualmente do indicador DATAGRO MS.
- Para cada par de ancoras consecutivas (i, j), aplica-se um agio CONSTANTE P_seg em
  todas as linhas entre i+1 e j, escolhido para fechar exatamente em j:
        P_seg = (H_alvo_j / H_i)^(1/n) - 1     onde n = j - i
        H_alvo_j = O[j] * 30 / B[j]            (E = B/30, 50% rendimento de carcaca)
- Apos a ultima ancora, extende-se com o P do ultimo segmento (continuacao da tendencia).
- H[n] = H[n-1] * (1 + P[n])
- L[n] = (B[n] / 30) * H[n]

A coluna P eh a unica gravada de volta. H, L, O sao recalculados pelas formulas
do Excel a partir de P e das cotacoes (Q, R, S, T).
"""

from dataclasses import dataclass

ANCHOR_ROW = 7   # boi gordo 16@ — H eh definido manualmente (DATAGRO MS)
LAST_ROW = 29    # categoria mais leve (5@)
RENDIMENTO_CARCACA = 0.50  # 1@ = 15kg carcaca = 30kg vivo


@dataclass
class RowState:
    row: int
    B: float       # peso vivo (kg)
    H: float       # preco por arroba (R$/@)
    P: float       # agio (decimal, ex 0.02 = 2%)
    O: float       # media das cotacoes (R$/animal); 0 se sem cotacao


def calibrate(rows: list[RowState]) -> list[RowState]:
    """
    Recebe lista de RowState ordenada da ancora inicial ate a ultima linha.
    Retorna nova lista com P e H recalculados via interpolacao geometrica.
    rows[0] eh sempre tratada como ancora inicial (H preservado da entrada).
    """
    if not rows:
        return rows
    out = [RowState(row=r.row, B=r.B, H=r.H, P=r.P, O=r.O) for r in rows]

    # Ancoras: indice 0 (sempre, H dado) + linhas com cotacao
    anchors = [0] + [i for i in range(1, len(rows)) if rows[i].O > 0]

    last_seg_P = 0.0  # fallback se nao houver segundo ancora

    # Interpola entre ancoras consecutivas
    for k in range(len(anchors) - 1):
        i, j = anchors[k], anchors[k + 1]
        n = j - i
        H_alvo = rows[j].O * 30 / rows[j].B
        P_seg = (H_alvo / out[i].H) ** (1 / n) - 1
        for idx in range(i + 1, j + 1):
            out[idx].P = P_seg
            out[idx].H = out[idx - 1].H * (1 + P_seg)
        last_seg_P = P_seg

    # Cauda: linhas apos a ultima ancora — extende com o P do ultimo segmento
    last_anchor = anchors[-1]
    for idx in range(last_anchor + 1, len(out)):
        out[idx].P = last_seg_P
        out[idx].H = out[idx - 1].H * (1 + last_seg_P)

    return out


def L(state: RowState) -> float:
    """Preco total do animal: L = (B/30) * H."""
    return (state.B / 30) * state.H


def deviation_pct(state: RowState) -> float | None:
    """Desvio relativo de L vs O em pontos percentuais. None se sem cotacao."""
    if state.O <= 0:
        return None
    return (L(state) - state.O) / state.O
