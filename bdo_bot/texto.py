"""Converte o corpo HTML dos posts em texto para a IA e escolhe imagens para ela ler."""

from __future__ import annotations

import re
import struct
from typing import Callable

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

_BLOCOS = {"p", "div", "section", "article", "tr", "br", "h1", "h2", "h3", "h4", "h5", "li", "ul", "ol", "table", "button"}


def html_para_texto(html: str) -> str:
    sopa = BeautifulSoup(html or "", "html.parser")
    for lixo in sopa(["script", "style", "noscript"]):
        lixo.decompose()
    partes: list[str] = []

    def visita(no):
        if isinstance(no, Comment):
            return
        if isinstance(no, NavigableString):
            partes.append(str(no))
            return
        if not isinstance(no, Tag):
            return
        nome = no.name
        if nome == "br":
            partes.append("\n")
            return
        if nome in ("h1", "h2", "h3", "h4", "h5"):
            nivel = {"h1": "#", "h2": "##", "h3": "###"}.get(nome, "####")
            partes.append(f"\n\n{nivel} {no.get_text(' ', strip=True)}\n")
            return
        if nome == "button":
            partes.append(f"\n### {no.get_text(' ', strip=True)}\n")
            return
        if nome == "li":
            partes.append("\n- " + re.sub(r"\s+", " ", no.get_text(" ", strip=True)))
            return
        if nome == "table":
            for tr in no.find_all("tr"):
                celulas = []
                for td in tr.find_all(["td", "th"]):
                    for br in td.find_all("br"):
                        br.replace_with(" / ")
                    celulas.append(re.sub(r"\s+", " ", td.get_text(" ", strip=True)).strip(" /"))
                if any(celulas):
                    partes.append("\n" + " | ".join(celulas))
            partes.append("\n")
            return
        if nome in _BLOCOS:
            partes.append("\n")
        for filho in no.children:
            visita(filho)
        if nome in _BLOCOS:
            partes.append("\n")

    for filho in sopa.children:
        visita(filho)
    texto = "".join(partes).replace("\xa0", " ")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r" *\n *", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def tamanho_imagem(dados: bytes) -> tuple[int, int] | None:
    """Le largura x altura do inicio de um PNG, JPEG, GIF ou WEBP."""
    if dados[:8] == b"\x89PNG\r\n\x1a\n" and len(dados) >= 24:
        return struct.unpack(">II", dados[16:24])
    if dados[:6] in (b"GIF87a", b"GIF89a") and len(dados) >= 10:
        return struct.unpack("<HH", dados[6:10])
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP" and len(dados) >= 30:
        if dados[12:16] == b"VP8X":
            w = int.from_bytes(dados[24:27], "little") + 1
            h = int.from_bytes(dados[27:30], "little") + 1
            return w, h
        return None
    if dados[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(dados):
            if dados[i] != 0xFF:
                i += 1
                continue
            marcador = dados[i + 1]
            if marcador in (0xD8, 0x01) or 0xD0 <= marcador <= 0xD7:
                i += 2
                continue
            tam = struct.unpack(">H", dados[i + 2:i + 4])[0]
            if marcador in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", dados[i + 5:i + 9])
                return w, h
            i += 2 + tam
    return None


_SINAIS = re.compile(
    r"local|aparição|aparicao|posição|posicao|mapa|location|spawn|overview|map\b|위치|전경|지도|seguintes|following",
    re.IGNORECASE,
)
_IGNORAR_URL = re.compile(r"/bdo/brand/|GLOBAL-LAB/.*1f0f1a50c83", re.IGNORECASE)

MAX_IMAGENS_PATCH = 3
MAX_IMAGENS_EVENTO = 6
LARGURA_MINIMA = 500


def _url(src: str) -> str:
    return "https:" + src if src.startswith("//") else src


def _texto_anterior(img: Tag) -> str:
    bloco = img.find_parent(["p", "div"]) or img
    anterior = bloco.find_previous(string=lambda s: s and s.strip())
    return (anterior or "").strip()


def candidatas_imagem(html: str, tamanho: Callable[[str], tuple[int, int] | None], evento: bool) -> list[str]:
    """Escolhe as imagens que podem ter informacao que falta no texto.

    Eventos: toda imagem grande (menos o banner do topo, GIFs e icones).
    Patches: so imagens grandes com sinal de mapa/local no alt ou no texto anterior.
    """
    sopa = BeautifulSoup(html or "", "html.parser")
    escolhidas: list[str] = []
    for indice, img in enumerate(sopa.find_all("img")):
        url = _url(img.get("src", ""))
        if not url or indice == 0 or url in escolhidas:
            continue
        if url.lower().split("?")[0].endswith(".gif") or _IGNORAR_URL.search(url):
            continue
        if img.find_parent("td"):
            continue
        dim = tamanho(url)
        if not dim or dim[0] < LARGURA_MINIMA:
            continue
        if not evento:
            anterior = _texto_anterior(img)
            sinal = _SINAIS.search(img.get("alt", "")) or _SINAIS.search(anterior) or anterior.endswith(":")
            if not sinal:
                continue
        escolhidas.append(url)
        if len(escolhidas) >= (MAX_IMAGENS_EVENTO if evento else MAX_IMAGENS_PATCH):
            break
    return escolhidas
