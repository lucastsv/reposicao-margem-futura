"""Pipeline cloud-ready: coleta -> calibra -> renderiza -> Telegram.

ZERO dependencia de Excel. Tudo em Python puro pra rodar em GH Actions
(ou qualquer runner Linux/Windows sem Office).

Diferencas vs atualizar_planilha.py (versao local que escreve no Excel):
- Nao le nem escreve no .xlsm
- Calcula D, E, G, I, L em Python puro (formulas que antes vivendo no Excel)
- Renderiza imagem via matplotlib (render_tabela_matplotlib) em vez de Excel COM
- Q (Oferta 1) sempre None (era input manual no Excel)

Uso direto: python pipeline_cloud.py
"""
from __future__ import annotations

import math
import sys
import time
from datetime import datetime
from pathlib import Path

from cepea_collector import collect as collect_cepea, BezerroSnapshot
from datagro_collector import collect as collect_datagro, DatagroSnapshot
from scot_collector import collect as collect_scot, ScotSnapshot
from calibracao import RowState, calibrate, ANCHOR_ROW, LAST_ROW
from atualizar_planilha import (
    coleta_com_retry, computar_O, calcular_B, linha_por_peso,
    SCOT_LINHAS, DATAGRO_LINHAS,
)
from render_tabela_matplotlib import LinhaTabela, render_tabela
from telegram_notify import send_photo, TelegramNotConfigured

LOG_DIR = Path(__file__).parent / "logs"


def calcular_D(row: int) -> float:
    """D29 = 164.5; cada linha pra cima soma 15kg. Mesma logica de calcular_B."""
    return 164.5 + (LAST_ROW - row) * 15.0


def trunc2(v: float) -> float:
    """Replica TRUNC(v, 2) do Excel — trunca pra 2 casas (NAO arredonda)."""
    return math.floor(v * 100) / 100


def construir_rows(
    snap_cepea: BezerroSnapshot,
    snap_dg: DatagroSnapshot,
    snap_scot: ScotSnapshot,
) -> list[RowState]:
    """Monta lista de RowState com B/H/O preenchidos a partir das coletas.
    H eh definido manualmente (linha 7 = ancora boi gordo MS DATAGRO);
    O eh media das cotacoes Q/R/S/T mapeadas. P fica zero ate calibrate().
    """
    n = LAST_ROW - ANCHOR_ROW + 1
    rows: list[RowState] = []
    for r in range(ANCHOR_ROW, LAST_ROW + 1):
        B = calcular_B(r)
        rows.append(RowState(row=r, B=B, H=0.0, P=0.0, O=0.0))

    # Ancora: H7 = boi gordo MS DATAGRO
    rows[0].H = snap_dg.boi_gordo_ms_arroba

    # Cotacoes por linha (4 colunas: Q manual nao-coletada, R CEPEA, S DATAGRO, T SCOT)
    q = [None] * n  # Oferta 1 manual — nao coletado
    r_ = [None] * n  # CEPEA
    s = [None] * n  # DATAGRO (rkg * B)
    t = [None] * n  # SCOT (R$/cabeca)

    # CEPEA: linha mais proxima de peso_medio_kg recebe media_4d_preco
    idx_cepea = linha_por_peso(snap_cepea.peso_medio_kg, rows)
    r_[idx_cepea] = snap_cepea.media_4d_preco

    # DATAGRO: 4 categorias por peso de referencia, S = rkg * B
    for cat, linha in DATAGRO_LINHAS.items():
        idx = linha - ANCHOR_ROW
        rkg = snap_dg.reposicao_ms[cat]
        s[idx] = rkg * rows[idx].B

    # SCOT: 4 categorias, T = R$/cabeca direto
    scot_map = {
        "desmama":   snap_scot.desmama_cab,
        "bezerro":   snap_scot.bezerro_cab,
        "garrote":   snap_scot.garrote_cab,
        "boi_magro": snap_scot.boi_magro_cab,
    }
    for cat, linha in SCOT_LINHAS.items():
        idx = linha - ANCHOR_ROW
        t[idx] = scot_map[cat]

    # O = AVG(Q, R, S, T) ignorando None/0
    for i in range(n):
        rows[i].O = computar_O(q[i], r_[i], s[i], t[i])

    return rows


def rows_para_linhas_tabela(rows: list[RowState]) -> list[LinhaTabela]:
    """Converte estado calibrado em estrutura pro renderer."""
    linhas: list[LinhaTabela] = []
    for r_state in rows:
        B = r_state.B
        D = calcular_D(r_state.row)
        H = r_state.H
        linhas.append(LinhaTabela(
            peso_low=B,
            peso_high=D,
            arroba_low=B / 30,
            arroba_high=D / 30,
            preco_faixa=H,
            preco_kg=trunc2(H / 30),
            arroba_exemplo=B / 30,
            preco_animal=(B / 30) * H,
            is_ancora=(r_state.row == ANCHOR_ROW),
        ))
    return linhas


def main() -> int:
    LOG_DIR.mkdir(exist_ok=True)
    log_path = LOG_DIR / f"pipeline_cloud_{datetime.now():%Y%m%d_%H%M%S}.log"

    def log(msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    log("Inicio pipeline cloud-ready (sem Excel).")

    # 1) Coletas com retry
    try:
        snap_cepea = coleta_com_retry("CEPEA", collect_cepea, log)
    except Exception as e:
        log(f"ERRO coleta CEPEA: {e}")
        return 2
    log(f"CEPEA OK: peso={snap_cepea.peso_medio_kg:.1f}kg media4d=R${snap_cepea.media_4d_preco:,.2f}")

    try:
        snap_dg = coleta_com_retry("DATAGRO", collect_datagro, log)
    except Exception as e:
        log(f"ERRO coleta DATAGRO: {e}")
        return 5
    log(f"DATAGRO OK: boi gordo MS R$ {snap_dg.boi_gordo_ms_arroba:.2f}/@; "
        f"reposicao MS R$/kg {snap_dg.reposicao_ms}")

    try:
        snap_scot = coleta_com_retry("SCOT", collect_scot, log)
    except Exception as e:
        log(f"ERRO coleta SCOT: {e}")
        return 6
    log(f"SCOT OK: MS R$/cab des={snap_scot.desmama_cab:,.2f} "
        f"bez={snap_scot.bezerro_cab:,.2f} gar={snap_scot.garrote_cab:,.2f} "
        f"mag={snap_scot.boi_magro_cab:,.2f}")

    # 2) Constroi RowState e calibra (tudo Python puro)
    rows = construir_rows(snap_cepea, snap_dg, snap_scot)
    new_rows = calibrate(rows)
    log(f"Calibrado: H7={new_rows[0].H:.2f}, H{LAST_ROW}={new_rows[-1].H:.2f}")
    n_ancoras = sum(1 for r in rows if r.O > 0)
    log(f"  {n_ancoras} ancoras de mercado encontradas")

    # 3) Mapeia pra estrutura do renderer
    linhas_tabela = rows_para_linhas_tabela(new_rows)

    # 4) Renderiza PNG
    img_path = LOG_DIR / f"preview_cloud_{datetime.now():%Y%m%d}.png"
    render_tabela(
        linhas=linhas_tabela,
        output_path=img_path,
        rodape="* Fecha o gado no dia anterior à pesagem.",
    )
    log(f"Imagem gerada: {img_path.name}")

    # 5) Envia Telegram
    try:
        send_photo(img_path,
                   caption=f"Preço Reposição MS — {datetime.now():%d/%m/%Y}")
        log("Notificacao Telegram enviada.")
    except TelegramNotConfigured as e:
        log(f"AVISO: Telegram nao configurado ({e}). Imagem gerada mas nao enviada.")
    except Exception as e:
        log(f"AVISO: Falha ao enviar Telegram: {e}")

    log("Fim.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
