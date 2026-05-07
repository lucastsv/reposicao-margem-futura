"""
Gera PNG do range B4:L30 da aba 'Preco Reposicao' com fidelidade visual ao Excel.

Estrategia: abre o .xlsm via COM (Excel headless), forca recalculacao das formulas,
seleciona o range, usa CopyPicture pra colocar bitmap no clipboard, e Pillow salva PNG.

Pre-req: Excel instalado, .xlsm fechado (sem lock).
"""

from __future__ import annotations
import time
from pathlib import Path

import win32com.client as win32
from PIL import ImageGrab

XL_SCREEN = 1
XL_BITMAP = 2
RANGE_TABELA = "B4:L30"


def gerar(xlsm_path: Path, sheet: str, output_path: Path, range_addr: str = RANGE_TABELA) -> None:
    """
    CopyPicture exige Excel visivel pra renderizar o bitmap. Tornamos visivel
    minimizado, capturamos, e fechamos. Janela aparece brevemente.
    """
    excel = win32.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = True
    excel.WindowState = -4140  # xlMinimized
    excel.DisplayAlerts = False
    try:
        wb = excel.Workbooks.Open(str(xlsm_path))
        try:
            excel.CalculateFull()
            ws = wb.Sheets(sheet)
            ws.Activate()
            rng = ws.Range(range_addr)
            rng.Select()
            # Tenta algumas vezes — clipboard as vezes demora
            img = None
            for _ in range(5):
                rng.CopyPicture(Appearance=XL_SCREEN, Format=XL_BITMAP)
                time.sleep(0.5)
                img = ImageGrab.grabclipboard()
                if img is not None:
                    break
            if img is None:
                raise RuntimeError("Clipboard vazio apos varias tentativas de CopyPicture")
            img.save(str(output_path), "PNG")
        finally:
            wb.Close(SaveChanges=False)
    finally:
        excel.Quit()


if __name__ == "__main__":
    XLSM = Path(__file__).parent / "planilha" / "Três Marias - Cálculo de Margem Futura.xlsm"
    out = Path(__file__).parent / "logs" / "preview.png"
    out.parent.mkdir(exist_ok=True)
    gerar(XLSM, "Preço Reposição", out)
    print(f"PNG gerado: {out}")
