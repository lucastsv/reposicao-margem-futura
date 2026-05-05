Attribute VB_Name = "Calibracao"
Sub RecalibrarAgios()
    On Error GoTo Erro
    RunPython "import excel_runner; excel_runner.recalibrar()"
    Exit Sub
Erro:
    MsgBox "Erro ao recalibrar: " & Err.Description, vbCritical, "Recalibrar Agios"
End Sub
