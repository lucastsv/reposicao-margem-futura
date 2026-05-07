"""
Calibracao de agios da aba "Preco Reposicao" de Tres Marias - Calculo de Margem Futura.

Algoritmo: interpolacao geometrica entre ancoras.
- Ancora: linha com cotacao de mercado (O > 0). Linha 7 (boi gordo) eh sempre a ancora
  inicial — H7 vem manualmente do indicador DATAGRO MS.
- Para cada par de ancoras consecutivas (i, j), aplica-se um agio CONSTANTE P_seg em
  todas as linhas entre i+1 e j, escolhido para fechar exatamente em j:
        P_seg = (H_alvo_j / H_i)^(1/n) - 1     onde n = j - i
        H_alvo_j = O[j] * 30 / B[j]            (E = B/30, 50% rendimento de carcaca)
- H[n] = H[n-1] * (1 + P[n])
- L[n] = (B[n] / 30) * H[n]

Filtro de monotonicidade (ancoras rebeldes):
- Uma ancora candidata so eh aceita se H_alvo > H_alvo da ultima ancora aceita.
- Caso contrario eh descartada (geraria agio negativo, violando a convencao
  de "animal mais leve sempre vale mais por @"). A linha fica visivel na coluna
  da fonte mas L diverge de O, sinalizando desacordo de mercado.

Cauda fixa (apos ultima ancora aceita):
- Linhas sem fonte de mercado recebem TAIL_AGIO (1%) por faixa em vez de extender
  o agio do ultimo segmento — evita que segmentos esticados projetem precos
  artificialmente altos/baixos nas faixas mais leves.

A coluna P eh a unica gravada de volta. H, L, O sao recalculados pelas formulas
do Excel a partir de P e das cotacoes (Q, R, S, T).
"""

from dataclasses import dataclass

ANCHOR_ROW = 7   # boi gordo 16@ — H eh definido manualmente (DATAGRO MS)
LAST_ROW = 29    # categoria mais leve (5@)
RENDIMENTO_CARCACA = 0.50  # 1@ = 15kg carcaca = 30kg vivo
TAIL_AGIO = 0.01  # 1% por faixa apos a ultima ancora aceita


@dataclass
class RowState:
    row: int
    B: float       # peso vivo (kg)
    H: float       # preco por arroba (R$/@)
    P: float       # agio (decimal, ex 0.02 = 2%)
    O: float       # media das cotacoes (R$/animal); 0 se sem cotacao


def calibrate(rows: list[RowState]) -> tuple[list[RowState], list[int]]:
    """
    Recebe lista de RowState ordenada da ancora inicial ate a ultima linha.
    Retorna (rows calibradas, lista de row numbers de ancoras rebeldes descartadas).
    rows[0] eh sempre tratada como ancora inicial (H preservado da entrada).
    """
    if not rows:
        return rows, []
    out = [RowState(row=r.row, B=r.B, H=r.H, P=r.P, O=r.O) for r in rows]

    # Ancoras: indice 0 sempre + linhas com O>0 que respeitem monotonicidade.
    anchors = [0]
    last_H_alvo = out[0].H  # H da ancora inicial (vem do DATAGRO boi gordo)
    rebeldes: list[int] = []

    for i in range(1, len(rows)):
        if rows[i].O > 0:
            H_alvo_i = rows[i].O * 30 / rows[i].B
            if H_alvo_i > last_H_alvo:
                anchors.append(i)
                last_H_alvo = H_alvo_i
            else:
                rebeldes.append(rows[i].row)

    # Interpola entre ancoras consecutivas
    for k in range(len(anchors) - 1):
        i, j = anchors[k], anchors[k + 1]
        n = j - i
        H_alvo = rows[j].O * 30 / rows[j].B
        P_seg = (H_alvo / out[i].H) ** (1 / n) - 1
        for idx in range(i + 1, j + 1):
            out[idx].P = P_seg
            out[idx].H = out[idx - 1].H * (1 + P_seg)

    # Cauda: linhas apos a ultima ancora aceita — agio fixo TAIL_AGIO (1%)
    last_anchor = anchors[-1]
    for idx in range(last_anchor + 1, len(out)):
        out[idx].P = TAIL_AGIO
        out[idx].H = out[idx - 1].H * (1 + TAIL_AGIO)

    return out, rebeldes


def L(state: RowState) -> float:
    """Preco total do animal: L = (B/30) * H."""
    return (state.B / 30) * state.H


def deviation_pct(state: RowState) -> float | None:
    """Desvio relativo de L vs O em pontos percentuais. None se sem cotacao."""
    if state.O <= 0:
        return None
    return (L(state) - state.O) / state.O
