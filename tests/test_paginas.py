from datetime import datetime, timezone
from pathlib import Path

from bdo_bot.paginas import ler_detalhe, ler_lista

FIX = Path(__file__).parent / "fixtures"


def html(nome):
    return (FIX / nome).read_text(encoding="utf-8")


def test_lista_sa_traz_id_titulo_e_link():
    itens = ler_lista("sa", html("sa_lista.html"))
    assert itens[0].post_id == "8910"
    assert itens[0].titulo == "Detalhes da atualização – 20 de Novembro de 2026"
    assert itens[0].url.endswith("groupContentNo=8910&countryType=pt-BR")
    ids = [i.post_id for i in itens]
    assert "8885" in ids
    assert len(ids) == len(set(ids))


def test_lista_sa_eventos_usa_titulo_dentro_de_em():
    itens = ler_lista("sa", html("sa_lista_eventos.html"))
    titulos = [i.titulo for i in itens]
    assert "Passe Especial da Solare" in titulos
    assert all(t and "\n" not in t for t in titulos)


def test_lista_sa_traz_thumbnail_em_tamanho_cheio():
    itens = ler_lista("sa", html("sa_lista.html"))
    assert itens[0].imagem.startswith("https://static.pearlcdn.com/")
    assert ".400x225" not in itens[0].imagem


def test_lista_pearlabyss_sea_e_globallab():
    sea = ler_lista("pa", html("sea_lista.html"))
    assert any(i.titulo == "November 5, 2026 (Thu) Update Details" and i.post_id == "20010" for i in sea)
    gl = ler_lista("pa", html("gl_lista.html"))
    assert gl[0].post_id.isdigit()
    assert any("업데이트" in i.titulo for i in gl)


def test_detalhe_sa_usa_epoch_exato():
    d = ler_detalhe("sa", html("sa_detalhe_patch.html"))
    assert d.titulo.startswith("Notas da Atualização")
    assert d.publicado == datetime(2026, 11, 19, 6, 0, tzinfo=timezone.utc)
    assert "contents_area" not in d.corpo_html and len(d.corpo_html) > 1000


def test_detalhe_pearlabyss_converte_fuso():
    d = ler_detalhe("pa", html("sea_detalhe.html"))
    assert d.titulo == "November 26, 2026 (Thu) Update Details"
    assert d.publicado == datetime(2026, 11, 26, 2, 0, tzinfo=timezone.utc)
    g = ler_detalhe("pa", html("gl_detalhe.html"))
    assert g.publicado == datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
    assert "검은" in g.corpo_html
