"""Fontes monitoradas, como classificar cada post e quando checar cada fonte."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Tipo(str, Enum):
    GLOBAL_LAB = "global_lab"      # servidor de testes, coreano -> #bdo-patch
    PREVIEW_SEA = "preview_sea"    # patch SEA (ingles), preview do SA -> #bdo-patch
    PATCH_SA = "patch_sa"          # "Notas da Atualizacao" -> #bdo-patch (compara com o preview)
    HOTFIX_SA = "hotfix_sa"        # "Detalhes da atualizacao" -> #bdo-patch, curto, sem audio
    EVENTO_SA = "evento_sa"        # -> #eventos
    LOJA_SA = "loja_sa"            # -> #loja-de-perolas, sem audio


@dataclass(frozen=True)
class Fonte:
    nome: str
    layout: str  # "sa" ou "pa" (ver paginas.py)
    url_lista: str
    # janelas de checagem a cada 30 min, em UTC: (dia_da_semana 0=seg, hora_inicio, hora_fim_exclusiva)
    janelas: tuple[tuple[int, int, int], ...]


SEG, TER, QUA, QUI, SEX, SAB, DOM = range(7)

# Janelas tiradas de ~30 posts de cada fonte (nov/2026). Fora delas, checagem de hora em hora.
FONTES: dict[str, Fonte] = {
    f.nome: f
    for f in [
        Fonte("globallab", "pa", "https://blackdesert.pearlabyss.com/GlobalLab/en-US/News/Notice?_categoryNo=2",
              # sexta 09:00 UTC; em semana de feriado coreano adianta para quinta
              ((SEX, 8, 11), (QUI, 8, 11), (QUI, 23, 24), (SEX, 0, 1))),
        Fonte("sea", "pa", "https://blackdesert.pearlabyss.com/Asia/en-US/News/Notice?_categoryNo=2",
              # quinta 02:00 UTC (quarta 23h em Brasilia); em semana de feriado, quarta
              ((QUI, 1, 4), (QUA, 1, 4))),
        Fonte("sa_atualizacao", "sa", "https://www.sa.playblackdesert.com/pt-BR/News/Notice?boardType=2",
              # quinta 06:00 UTC, mas o site fica em manutencao ate ~08-10 UTC; hotfix qui/sex 08-12 UTC
              ((QUI, 5, 12), (SEX, 8, 12), (QUA, 16, 23))),
        Fonte("sa_eventos", "sa", "https://www.sa.playblackdesert.com/pt-BR/News/Notice?boardType=3&progressType=1",
              ((QUI, 5, 12), (QUA, 16, 23))),
        Fonte("sa_loja", "sa", "https://www.sa.playblackdesert.com/pt-BR/News/Notice?boardType=5",
              ((QUI, 5, 12),)),
    ]
}

# Usado so para aprender termos (nunca e postado).
URL_LISTA_KR = "https://www.kr.playblackdesert.com/ko-KR/News/Notice?boardType=2"

# Paginas oficiais de classes, para o glossario (nomes pareados pelo classType).
URL_CLASSES = {
    "ko": "https://www.kr.playblackdesert.com/ko-KR/GameInfo/Class",
    "en": "https://www.naeu.playblackdesert.com/en-US/GameInfo/Class",
    "pt": "https://www.sa.playblackdesert.com/pt-BR/GameInfo/Class",
}


def e_patch_kr(titulo: str) -> bool:
    """Post coreano de atualizacao (Global Lab ou KR ao vivo), sem os de modulo de seguranca."""
    return "업데이트" in titulo and "보안" not in titulo


def classificar(fonte: str, titulo: str) -> Tipo | None:
    t = titulo.strip()
    baixo = t.lower()
    if fonte == "globallab":
        return Tipo.GLOBAL_LAB if e_patch_kr(t) else None
    if fonte == "sea":
        if "[hotfix]" in baixo or "update details" not in baixo:
            return None
        return Tipo.PREVIEW_SEA
    if fonte == "sa_atualizacao":
        if t.startswith("[") and not t.lower().startswith("[atualiza"):
            return None  # [Black Desert+], [Módulo de segurança], ...
        if re.search(r"notas da atualiza", baixo):
            return Tipo.PATCH_SA
        if re.search(r"detalhes da atualiza", baixo):
            return Tipo.HOTFIX_SA
        return None
    if fonte == "sa_eventos":
        return Tipo.EVENTO_SA
    if fonte == "sa_loja":
        return Tipo.LOJA_SA
    return None


def fontes_para_checar(agora_utc: datetime, meia_hora: bool) -> list[str]:
    """Na checagem de hora cheia olha tudo; na de meia hora, so as fontes dentro da janela."""
    if not meia_hora:
        return list(FONTES)
    dia, hora = agora_utc.weekday(), agora_utc.hour
    return [
        nome for nome, f in FONTES.items()
        if any(d == dia and inicio <= hora < fim for d, inicio, fim in f.janelas)
    ]
