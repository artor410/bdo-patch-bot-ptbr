"""Leitura das paginas oficiais (listagens e detalhes).

Dois "layouts" existem:
- "sa":  sites regionais (sa./kr./naeu.playblackdesert.com) -> ?groupContentNo=N
- "pa":  blackdesert.pearlabyss.com (SEA/Asia e Global Lab)  -> ?_boardNo=N
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class ItemLista:
    post_id: str
    titulo: str
    url: str
    imagem: str = ""


@dataclass(frozen=True)
class Detalhe:
    titulo: str
    publicado: datetime | None
    corpo_html: str


def _limpa(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def _imagem_cheia(src: str) -> str:
    return re.sub(r"\.\d+x\d+(\.\w+)$", r"\1", src or "")


def ler_lista(layout: str, html: str) -> list[ItemLista]:
    sopa = BeautifulSoup(html, "html.parser")
    itens: list[ItemLista] = []
    vistos: set[str] = set()
    if layout == "sa":
        # ignora o carrossel "Novidades" do topo (div.news_item)
        links = [a for a in sopa.select('a[name="btnDetail"]') if not a.find_parent(class_="news_item")]
        padrao = r"groupContentNo=(\d+)"
    else:
        links = sopa.select("li.board_item a.board_item_inner")
        padrao = r"_boardNo=(\d+)"
    for a in links:
        m = re.search(padrao, a.get("href", ""))
        if not m or m.group(1) in vistos:
            continue
        titulo_el = a.select_one(".title em") or a.select_one(".title .line_clamp") or a.select_one(".title")
        img = a.find("img")
        vistos.add(m.group(1))
        itens.append(
            ItemLista(
                post_id=m.group(1),
                titulo=_limpa(titulo_el.get_text(" ") if titulo_el else ""),
                url=a["href"],
                imagem=_imagem_cheia(img.get("src", "")) if img else "",
            )
        )
    return itens


_MESES_EN = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def _data_pa(texto: str) -> datetime | None:
    # "Nov 20, 2026, 12:00 (UTC+3)"
    m = re.search(r"(\w{3})\w* (\d{1,2}), (\d{4}), (\d{1,2}):(\d{2}) \(UTC([+-]\d+)\)", texto)
    if not m or m.group(1) not in _MESES_EN:
        return None
    mes, dia, ano, h, mi, off = m.groups()
    local = datetime(int(ano), _MESES_EN[mes], int(dia), int(h), int(mi),
                     tzinfo=timezone(timedelta(hours=int(off))))
    return local.astimezone(timezone.utc)


def ler_detalhe(layout: str, html: str) -> Detalhe:
    sopa = BeautifulSoup(html, "html.parser")
    corpo = sopa.select_one("div.contents_area.editor_area")
    corpo_html = corpo.decode_contents() if corpo else ""
    if layout == "sa":
        titulo = sopa.select_one(".title_area strong.title")
        data = sopa.select_one("span.date.js-localTimezoneTooltip")
        publicado = None
        if data and data.get("data-fixedtooltip", "").isdigit():
            publicado = datetime.fromtimestamp(int(data["data-fixedtooltip"]) / 1000, tz=timezone.utc)
    else:
        titulo = sopa.select_one("h3.detail_top_title")
        data = sopa.select_one(".detail_top_info span.info_item.date")
        publicado = _data_pa(data.get_text()) if data else None
    return Detalhe(
        titulo=_limpa(titulo.get_text(" ") if titulo else ""),
        publicado=publicado,
        corpo_html=corpo_html,
    )
