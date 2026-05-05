"""Renderiza a tabela 'Compra de gado no peso' como PNG via matplotlib.

Substitui gerar_imagem.py (que dependia de Excel COM + xlwings).
Recebe dados ja calculados em Python puro -> totalmente cloud-ready.

Convencao visual seguindo o preview Excel atual:
- Header amarelo brilhante
- Subtitulo amarelo claro
- Subheaders cinza claro
- Zebra striping no body
- Coluna "Precos para faixa de peso" com fundo amarelo claro destacado
- Linha-ancora (a do H7 manual) com fundo azul claro
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


# Cores no estilo da planilha
COR_HEADER_BG = "#FFD700"           # amarelo ouro
COR_SUBTITULO_BG = "#FFFFE0"        # amarelo claro
COR_SUBHEADER_BG = "#E8E8E8"        # cinza claro
COR_BODY_ALT_BG = "#FFFFFF"         # branco
COR_BODY_ZEBRA_BG = "#D9D9D9"       # cinza medio (zebra com bom contraste)
COR_ANCORA_BG = "#B8DAFF"           # azul claro (linha ancora)
COR_BORDA = "#666666"
COR_TEXTO = "#000000"


@dataclass
class LinhaTabela:
    """Uma linha da tabela de pesagem."""
    peso_low: float       # ex: 480
    peso_high: float      # ex: 494.5
    arroba_low: float     # ex: 16.00
    arroba_high: float    # ex: 16.48
    preco_faixa: float    # ex: 347.70 (R$ por arroba na faixa)
    preco_kg: float       # ex: 11.59
    arroba_exemplo: float  # ex: 16.00 (arroba do peso_low)
    preco_animal: float   # ex: 5563 (R$ pra um animal naquela arroba)
    is_ancora: bool = False


def _fmt_kg(v: float) -> str:
    return f"{v:g} Kg"


def _fmt_arroba(v: float) -> str:
    return f"{v:.2f} @".replace(".", ",")


def _fmt_brl(v: float, casas: int = 2) -> str:
    """R$ X.XXX,XX (separador br)."""
    s = f"{v:,.{casas}f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_brl_compact(v: float) -> str:
    """R$ X.XXX (sem casas, p/ valor de animal)."""
    s = f"{int(round(v)):,d}"
    return "R$ " + s.replace(",", ".")


def render_tabela(
    linhas: list[LinhaTabela],
    output_path: Path,
    titulo: str = "COMPRA DE GADO NO PESO*",
    subtitulo: str = (
        "Exemplos de pesagem para referência de valores. Pagamento com trinta (30) dias.\n"
        "Distância até 350 Km da fazenda."
    ),
    rodape: str | None = None,
) -> Path:
    """Renderiza a tabela em PNG."""
    n_linhas = len(linhas)
    # Layout: 2 linhas de titulo + 2 linhas de subheader (2-line wrap) + n_linhas
    # Vamos usar matplotlib Table API em manual mode pra ter controle total.

    # Largura ~ proporcional ao preview Excel; altura por linha generosa
    fig_w = 9.5
    row_h_in = 0.42  # polegadas por linha do body
    # altura total: titulo + subtitulo + subheader + body + rodape
    fig_h = 0.55 + 0.55 + 0.65 + n_linhas * row_h_in + (0.30 if rodape else 0.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=130)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Coordenadas de coluna (em fraction): 5 colunas
    # col 1: faixa peso (low|ate|high inline)
    # col 2: faixa arroba
    # col 3: preco faixa (DESTAQUE)
    # col 4: preco kg
    # col 5: exemplo preço por animal (low_arroba @ = R$ valor)
    col_w = [0.245, 0.245, 0.180, 0.150, 0.180]
    col_x = [0.0]
    for w in col_w:
        col_x.append(col_x[-1] + w)

    # Calcula y de cada banda em fracoes da figura.
    # Total de altura "real" em polegadas conhecida; converto pra fracao.
    h_titulo = 0.55 / fig_h
    h_subtitulo = 0.55 / fig_h
    h_subheader = 0.65 / fig_h
    h_rodape = (0.30 / fig_h) if rodape else 0.0
    h_body = (1.0 - h_titulo - h_subtitulo - h_subheader - h_rodape) / max(n_linhas, 1)
    y_top = 1.0

    def draw_cell(x0, x1, y0, y1, color, text, fontweight="normal", fontsize=8,
                  fontcolor=COR_TEXTO, halign="center"):
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0,
                               facecolor=color, edgecolor=COR_BORDA, linewidth=0.5))
        if text is None:
            return
        x_anchor = (x0 + x1) / 2 if halign == "center" else x0 + 0.005
        ax.text(x_anchor, (y0 + y1) / 2, text,
                ha=halign, va="center", fontsize=fontsize,
                fontweight=fontweight, color=fontcolor, family="DejaVu Sans")

    # === Titulo ===
    y1, y0 = y_top, y_top - h_titulo
    draw_cell(0, 1, y0, y1, COR_HEADER_BG, titulo,
              fontweight="bold", fontsize=14)

    # === Subtitulo ===
    y1, y0 = y0, y0 - h_subtitulo
    draw_cell(0, 1, y0, y1, COR_SUBTITULO_BG, None)
    ax.text(0.5, (y0 + y1) / 2, subtitulo, ha="center", va="center",
            fontsize=10, fontweight="bold", family="DejaVu Sans",
            color="#1f1f1f")

    # === Subheaders (2 linhas) ===
    y1_sh, y0_sh = y0, y0 - h_subheader
    headers = [
        "Faixa de peso",
        "Faixa de arroba (50% de\nrendimento de carcaça)",
        "Preços para\nfaixa de peso",
        "Preço por quilo\npara pesar",
        "Exemplo de preço\npara o animal por",
    ]
    for i, hd in enumerate(headers):
        draw_cell(col_x[i], col_x[i + 1], y0_sh, y1_sh,
                  COR_SUBHEADER_BG, hd, fontweight="bold", fontsize=10)

    # === Body com zebra ===
    y_cur = y0_sh
    for idx, ln in enumerate(linhas):
        y1, y0 = y_cur, y_cur - h_body
        # Zebra: linhas alternadas pra leitura
        zebra = (idx % 2 == 1)
        row_color = COR_BODY_ZEBRA_BG if zebra else COR_BODY_ALT_BG
        # Coluna 3 (preco): segue zebra normal; SO ancora ganha azul
        if ln.is_ancora:
            preco_col_color = COR_ANCORA_BG
            preco_text_color = "#0033CC"
        else:
            preco_col_color = row_color
            preco_text_color = COR_TEXTO

        # Col 1: faixa peso
        peso_txt = f"{_fmt_kg(ln.peso_low)}  até  {_fmt_kg(ln.peso_high)}"
        draw_cell(col_x[0], col_x[1], y0, y1, row_color, peso_txt, fontsize=10)
        # Col 2: faixa arroba
        arroba_txt = f"{_fmt_arroba(ln.arroba_low)}  até  {_fmt_arroba(ln.arroba_high)}"
        draw_cell(col_x[1], col_x[2], y0, y1, row_color, arroba_txt, fontsize=10)
        # Col 3: preco faixa (sempre destacada; azul SO se ancora)
        draw_cell(col_x[2], col_x[3], y0, y1, preco_col_color,
                  _fmt_brl(ln.preco_faixa, 2),
                  fontweight="bold", fontsize=11.5,
                  fontcolor=preco_text_color)
        # Col 4: preco kg
        draw_cell(col_x[3], col_x[4], y0, y1, row_color,
                  _fmt_brl(ln.preco_kg, 2), fontsize=10.5)
        # Col 5: exemplo preço pro animal
        ex_txt = f"{_fmt_arroba(ln.arroba_exemplo)}  =  {_fmt_brl_compact(ln.preco_animal)}"
        draw_cell(col_x[4], col_x[5], y0, y1, row_color, ex_txt, fontsize=10)

        y_cur = y0

    # === Rodape (opcional) ===
    if rodape:
        y1, y0 = y_cur, y_cur - h_rodape
        draw_cell(0, 1, y0, y1, COR_BODY_ALT_BG, rodape,
                  fontsize=8, fontcolor="#444444")

    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    fig.savefig(output_path, dpi=140, bbox_inches="tight",
                pad_inches=0.05, facecolor="white")
    plt.close(fig)
    return output_path


# ===========================================
# Demo: gera tabela com dados do preview atual
# ===========================================
def _dados_demo() -> list[LinhaTabela]:
    """Reproduz exatamente os dados do preview_20260504.png."""
    dados = [
        # peso_low, peso_high, arroba_low, arroba_high, preco_faixa, preco_kg, arroba_exemplo, preco_animal, is_ancora
        (480, 494.5, 16.00, 16.48, 347.70, 11.59, 16.00, 5563, True),
        (465, 479.5, 15.50, 15.98, 358.65, 11.95, 15.50, 5565, False),
        (450, 464.5, 15.00, 15.48, 369.95, 12.33, 15.00, 5549, False),
        (435, 449.5, 14.50, 14.98, 381.61, 12.72, 14.50, 5533, False),
        (420, 434.5, 14.00, 14.48, 393.63, 13.12, 14.00, 5511, False),
        (405, 419.5, 13.50, 13.98, 406.03, 13.53, 13.50, 5481, False),
        (390, 404.5, 13.00, 13.48, 418.82, 13.96, 13.00, 5445, False),
        (375, 389.5, 12.50, 12.98, 432.01, 14.40, 12.50, 5400, False),
        (360, 374.5, 12.00, 12.48, 438.85, 14.62, 12.00, 5266, False),
        (345, 359.5, 11.50, 11.98, 445.79, 14.85, 11.50, 5127, False),
        (330, 344.5, 11.00, 11.48, 452.84, 15.09, 11.00, 4981, False),
        (315, 329.5, 10.50, 10.98, 460.00, 15.33, 10.50, 4830, False),
        (300, 314.5, 10.00, 10.48, 467.28, 15.57, 10.00, 4673, False),
        (285, 299.5, 9.50, 9.98, 477.68, 15.92, 9.50, 4538, False),
        (270, 284.5, 9.00, 9.48, 488.31, 16.27, 9.00, 4395, False),
        (255, 269.5, 8.50, 8.98, 499.18, 16.63, 8.50, 4243, False),
        (240, 254.5, 8.00, 8.48, 510.29, 17.00, 8.00, 4082, False),
        (225, 239.5, 7.50, 7.98, 518.12, 17.27, 7.50, 3886, False),
        (210, 224.5, 7.00, 7.48, 526.07, 17.53, 7.00, 3682, False),
        (195, 209.5, 6.50, 6.98, 534.14, 17.80, 6.50, 3472, False),
        (180, 194.5, 6.00, 6.48, 542.33, 18.07, 6.00, 3254, False),
        (165, 179.5, 5.50, 5.98, 550.65, 18.35, 5.50, 3029, False),
        (150, 164.5, 5.00, 5.48, 559.10, 18.63, 5.00, 2795, False),
    ]
    return [LinhaTabela(*row) for row in dados]


if __name__ == "__main__":
    out = Path(__file__).parent / "logs" / "preview_matplotlib.png"
    out.parent.mkdir(exist_ok=True)
    render_tabela(
        linhas=_dados_demo(),
        output_path=out,
        rodape="* Fecha o gado no dia anterior à pesagem.",
    )
    print(f"PNG gerado: {out}")
