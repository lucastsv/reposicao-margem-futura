"""
Ponte entre Excel (botao via xlwings) e a logica de calibracao em Python.

A macro VBA "RecalibrarAgios" chama excel_runner.recalibrar(). Esta funcao
le H/B/P/O do workbook ativo, roda calibrate(), e escreve as novas P de volta.
H, L e O sao recalculados pelas formulas do Excel automaticamente.
"""

import xlwings as xw

from calibracao import RowState, calibrate, ANCHOR_ROW, LAST_ROW

SHEET = "Preço Reposição"


def recalibrar():
    wb = xw.Book.caller()
    sht = wb.sheets[SHEET]

    rows: list[RowState] = []
    for r in range(ANCHOR_ROW, LAST_ROW + 1):
        rows.append(RowState(
            row=r,
            B=float(sht.range(f"B{r}").value or 0),
            H=float(sht.range(f"H{r}").value or 0),
            P=float(sht.range(f"P{r}").value or 0),
            O=float(sht.range(f"O{r}").value or 0),
        ))

    new, rebeldes = calibrate(rows)

    # Escreve apenas P (col 16) das linhas pos-ancora. Linha 7 (P7) eh seed manual.
    for s in new[1:]:
        sht.range(f"P{s.row}").value = s.P

    if rebeldes:
        # Sinaliza no Excel: status no canto superior da aba (cell A1 ou similar fica
        # ocupado; usa Q1 que esta no header da tabela direita).
        # Mantem visivel sem popup pra nao bloquear.
        print(f"AVISO: ancoras rebeldes descartadas: linhas {rebeldes}")
