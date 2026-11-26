import struct
import zlib
from pathlib import Path

from bdo_bot.paginas import ler_detalhe
from bdo_bot.texto import candidatas_imagem, html_para_texto, tamanho_imagem

FIX = Path(__file__).parent / "fixtures"


def test_texto_preserva_titulos_listas_e_tabelas():
    html = """
    <div class="tpl_title_bullet"><h2 class="title">Eventos</h2></div>
    <ul><li>Evento 1</li><li>Evento 2</li></ul>
    <table><tr><td>Item<br>Extra</td><td>x1</td></tr></table>
    <button class="btn_tpl_folding js-editorTitleFolder">Ver loot</button>
    <div class="fold_contents"><p>Escondido mas presente</p></div>
    <script>alert(1)</script>
    """
    t = html_para_texto(html)
    assert "## Eventos" in t
    assert "- Evento 1" in t and "- Evento 2" in t
    assert "Item / Extra | x1" in t
    assert "Ver loot" in t and "Escondido mas presente" in t
    assert "alert" not in t


def test_texto_de_patch_real_nao_fica_vazio():
    d = ler_detalhe("sa", (FIX / "sa_detalhe_patch.html").read_text(encoding="utf-8"))
    t = html_para_texto(d.corpo_html)
    assert t.startswith("Olá, Aventureiros!")
    assert "## Eventos" in t
    assert "\n\n\n" not in t
    # comentarios do editor (<!-- Template Start -->) nao podem virar texto
    assert "Template Start" not in t and "SECTION:" not in t


def _png(w, h):
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))


def _jpeg(w, h):
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, h, w, 1) + b"\x01\x11\x00"
    return b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 4) + b"\x00\x00" + sof


def test_tamanho_imagem_png_e_jpeg():
    assert tamanho_imagem(_png(800, 600)) == (800, 600)
    assert tamanho_imagem(_jpeg(1920, 1080)) == (1920, 1080)
    assert tamanho_imagem(b"lixo") is None


HTML_IMGS = """
<p><img src="https://x/banner.jpg"></p>
<p>Local de aparição do chefe:</p><p><img src="https://x/mapa.png" alt="위치"></p>
<table><tr><td><img src="https://x/icone.png"></td><td>Pedra Cron</td></tr></table>
<p><img src="https://x/anim.gif"></p>
<p>Texto qualquer</p><p><img src="//x/foto.jpg"></p>
<p><img src="https://x/mapa.png"></p>
"""

TAMANHOS = {
    "https://x/banner.jpg": (880, 355),
    "https://x/mapa.png": (800, 800),
    "https://x/icone.png": (44, 44),
    "https://x/foto.jpg": (1920, 1080),
}


def test_candidatas_em_patch_so_levam_imagens_com_sinal_de_informacao():
    urls = candidatas_imagem(HTML_IMGS, TAMANHOS.get, evento=False)
    assert urls == ["https://x/mapa.png"]


def test_candidatas_em_evento_levam_toda_imagem_grande_menos_banner():
    urls = candidatas_imagem(HTML_IMGS, TAMANHOS.get, evento=True)
    assert urls == ["https://x/mapa.png", "https://x/foto.jpg"]
