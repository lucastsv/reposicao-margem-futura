"""
Script de setup (rodar UMA vez) para:
1. Converter o .xlsx em .xlsm (macro-enabled)
2. Adicionar aba 'xlwings.conf' apontando para o venv do projeto
3. Injetar a macro VBA 'RecalibrarAgios' (requer Trust Center liberado — ver erro)
4. Adicionar o botao 'Recalibrar Agios' na aba Preco Reposicao

Pre-requisitos:
- Excel fechado
- xlwings addin instalado (`./venv/Scripts/xlwings.exe addin install`)
"""

import os
import sys
import win32com.client as win32

PROJECT = r"C:\PYTHON\projeto_automacao_gerencial"
XLSX = os.path.join(PROJECT, "planilha", "Três Marias - Cálculo de Margem Futura.xlsx")
XLSM = os.path.join(PROJECT, "planilha", "Três Marias - Cálculo de Margem Futura.xlsm")
SHEET = "Preço Reposição"
VENV_PY = os.path.join(PROJECT, "venv", "Scripts", "python.exe")

VBA_CODE = '''Sub RecalibrarAgios()
    On Error GoTo Erro
    RunPython "import excel_runner; excel_runner.recalibrar()"
    Exit Sub
Erro:
    MsgBox "Erro ao recalibrar: " & Err.Description, vbCritical, "Recalibrar Agios"
End Sub
'''

XL_OPENXML_MACRO = 52      # xlOpenXMLWorkbookMacroEnabled
XL_SHEET_HIDDEN = 0        # xlSheetHidden
VBEXT_CT_STD_MODULE = 1    # standard module


def ensure_xlwings_conf(wb):
    try:
        cf = wb.Sheets("xlwings.conf")
        cf.Cells.Clear()
    except Exception:
        cf = wb.Sheets.Add()
        cf.Name = "xlwings.conf"
    cf.Range("A1").Value = "INTERPRETER_WIN"
    cf.Range("B1").Value = VENV_PY
    cf.Range("A2").Value = "PYTHONPATH"
    cf.Range("B2").Value = PROJECT
    cf.Visible = XL_SHEET_HIDDEN


XLWINGS_BAS = os.path.join(PROJECT, "venv", "Lib", "site-packages", "xlwings", "xlwings.bas")


def import_xlwings_bas(wb):
    """Importa o modulo standalone xlwings.bas, que define RunPython.
    Substitui qualquer modulo 'xlwings' pre-existente para garantir versao atual."""
    vbproj = wb.VBProject
    for comp in list(vbproj.VBComponents):
        if comp.Name == "xlwings":
            vbproj.VBComponents.Remove(comp)
            break
    vbproj.VBComponents.Import(XLWINGS_BAS)


def inject_vba(wb):
    vbproj = wb.VBProject  # raises if Trust setting is off
    import_xlwings_bas(wb)
    existing = None
    for comp in vbproj.VBComponents:
        if comp.Name == "Calibracao":
            existing = comp
            break
    if existing is None:
        existing = vbproj.VBComponents.Add(VBEXT_CT_STD_MODULE)
        existing.Name = "Calibracao"
    cm = existing.CodeModule
    if cm.CountOfLines > 0:
        cm.DeleteLines(1, cm.CountOfLines)
    cm.AddFromString(VBA_CODE)


def add_button(wb, with_macro=True):
    ws = wb.Sheets(SHEET)
    for shp in list(ws.Shapes):
        try:
            if shp.Name.startswith("Btn_Recalibrar"):
                shp.Delete()
        except Exception:
            pass
    anchor = ws.Range("Q3")
    # 1 cm = 72/2.54 ≈ 28.35 pontos. Botao 1cm acima do topo de Q3.
    btn = ws.Buttons().Add(anchor.Left, anchor.Top - 28.35, 150, 28)
    btn.Caption = "Recalibrar Agios"
    btn.Name = "Btn_Recalibrar"
    if with_macro:
        btn.OnAction = "RecalibrarAgios"


def main():
    if os.path.exists(XLSM):
        print(f"Atualizando .xlsm existente: {XLSM}")
        input_path = XLSM
    elif os.path.exists(XLSX):
        input_path = XLSX
    else:
        print(f"ERRO: nao encontrei nem {XLSX} nem {XLSM}")
        sys.exit(1)

    excel = win32.gencache.EnsureDispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False

    try:
        wb = excel.Workbooks.Open(input_path)

        if input_path.lower().endswith(".xlsx"):
            wb.SaveAs(XLSM, FileFormat=XL_OPENXML_MACRO)
            wb = excel.Workbooks(os.path.basename(XLSM))

        ensure_xlwings_conf(wb)

        vba_ok = False
        try:
            inject_vba(wb)
            vba_ok = True
            print("VBA injetada com sucesso.")
        except Exception as e:
            print(f"AVISO: nao foi possivel injetar VBA: {e}")
            print()
            print("PASSO MANUAL:")
            print("  Excel -> Arquivo -> Opcoes -> Central de Confiabilidade ->")
            print("  Configuracoes da Central de Confiabilidade -> Configuracoes de Macro ->")
            print("  Marcar 'Confiar acesso ao modelo de objeto do projeto VBA'")
            print("  Depois rode novamente este script.")
            print()
            print("ALTERNATIVA (sem mexer no Trust Center): abra o arquivo, Alt+F11, Inserir > Modulo,")
            print("cole o codigo VBA do arquivo VBA_macro.bas e atribua a macro ao botao.")

        add_button(wb, with_macro=vba_ok)

        wb.Save()
        wb.Close()
        print()
        print(f"OK: {XLSM}")
        if vba_ok:
            print("Botao pronto. Abra o arquivo, clique em 'Recalibrar Agios'.")
    finally:
        excel.Quit()


if __name__ == "__main__":
    main()
