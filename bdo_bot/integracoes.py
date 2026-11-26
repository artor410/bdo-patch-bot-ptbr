"""Acesso real a rede: paginas oficiais, imagens, base de itens do arsha.io, audio e avisos."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import httpx

from .glossario import itens_no_texto

log = logging.getLogger(__name__)

AGENTE = "Mozilla/5.0 (compatible; bdo-patch-bot-ptbr/1.0; +https://github.com/artor410/bdo-patch-bot-ptbr)"
PAUSA = 1.5  # segundos entre pedidos ao mesmo site, para nao pesar


class Web:
    def __init__(self, http: httpx.Client | None = None):
        self.http = http or httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": AGENTE})
        self._ultimo = 0.0

    def _pausa(self):
        falta = PAUSA - (time.monotonic() - self._ultimo)
        if falta > 0:
            time.sleep(falta)
        self._ultimo = time.monotonic()

    def texto(self, url: str) -> str | None:
        self._pausa()
        for tentativa in range(3):
            try:
                r = self.http.get(url)
            except httpx.TransportError as e:
                log.warning("falha de rede em %s: %s", url, e)
                time.sleep(5 * (tentativa + 1))
                continue
            if "shutdown" in str(r.url) or "closetime" in str(r.url):
                log.info("site em manutencao: %s", url)
                return None
            if r.status_code == 200:
                return r.text
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(5 * (tentativa + 1))
                continue
            log.warning("HTTP %s em %s", r.status_code, url)
            return None
        return None

    def bytes(self, url: str, limite: int | None = None) -> bytes | None:
        headers = {"Range": f"bytes=0-{limite - 1}"} if limite else {}
        try:
            r = self.http.get(url, headers=headers)
        except httpx.TransportError:
            return None
        if r.status_code not in (200, 206):
            return None
        dados = r.content
        return dados[:limite] if limite else dados


class ItensArsha:
    """Nomes oficiais de itens por id (arsha.io), baixados no maximo uma vez por semana."""

    URL = "https://api.arsha.io/util/db?lang={lingua}"
    LINGUAS = {"en": "en", "ko": "kr", "pt": "pt"}
    MINIMO = {"en": 5, "ko": 3}

    def __init__(self, pasta: Path, baixar: Callable[[str], str | None], agora: datetime | None):
        self.pasta = Path(pasta)
        self.baixar = baixar
        self.agora = agora
        self._cache: dict[str, dict[int, str]] = {}

    def _base(self, lingua_arsha: str) -> dict[int, str]:
        if lingua_arsha in self._cache:
            return self._cache[lingua_arsha]
        arq = self.pasta / f"{lingua_arsha}.json"
        velho = (not arq.exists()) or (
            self.agora is not None
            and datetime.fromtimestamp(arq.stat().st_mtime, timezone.utc) < self.agora - timedelta(days=7))
        if velho and self.agora is not None:
            dados = self.baixar(self.URL.format(lingua=lingua_arsha))
            if dados and dados.lstrip().startswith("["):
                self.pasta.mkdir(parents=True, exist_ok=True)
                arq.write_text(dados, encoding="utf-8")
        base: dict[int, str] = {}
        if arq.exists():
            try:
                base = {int(i["id"]): i["name"] for i in json.loads(arq.read_text(encoding="utf-8"))}
            except (ValueError, KeyError, TypeError):
                log.warning("base do arsha.io invalida: %s", arq)
        self._cache[lingua_arsha] = base
        return base

    def __call__(self, texto: str, lingua: str) -> list[tuple[str, str]]:
        origem = self._base(self.LINGUAS[lingua])
        pt = self._base("pt")
        if not origem or not pt:
            return []
        return itens_no_texto(texto, origem, pt, minimo=self.MINIMO.get(lingua, 4))


def deve_avisar(estado: dict, mensagem: str, agora: datetime, intervalo: timedelta = timedelta(hours=6)) -> bool:
    """Evita repetir o mesmo erro no #bot-logs a cada 30 minutos."""
    enviados = estado.setdefault("erros_avisados", {})
    chave = mensagem[:160]
    ultimo = enviados.get(chave)
    if ultimo and agora - datetime.fromisoformat(ultimo) < intervalo:
        return False
    enviados[chave] = agora.isoformat()
    for k, v in list(enviados.items()):
        if agora - datetime.fromisoformat(v) > timedelta(days=3):
            del enviados[k]
    return True


# grafia fonetica: em maiusculas (HEX) a voz soletra letra por letra
_FALA = {"PRI": "Pri", "DUO": "Duo", "TRI": "Tri", "TET": "Téti", "PEN": "Pen",
         "HEX": "Réx", "HEP": "Rép", "OCT": "Ócti", "ENE": "Êne", "DEC": "Déca", "DECA": "Déca"}
_ROMANOS = {"I": "PRI", "II": "DUO", "III": "TRI", "IV": "TET", "V": "PEN",
            "VI": "HEX", "VII": "HEP", "VIII": "OCT", "IX": "ENE", "X": "DEC"}
NIVEIS_FALADOS = {**{r: _FALA[n] for r, n in _ROMANOS.items()}, **_FALA}
_NIVEL = re.compile(r"(?<![\w-])(" + "|".join(sorted(NIVEIS_FALADOS, key=len, reverse=True)) + r")(?![\w-])")


def para_fala(texto: str) -> str:
    """Niveis de aprimoramento em romano (V) viram o nome que os jogadores falam (PEN)."""
    return _NIVEL.sub(lambda m: NIVEIS_FALADOS[m.group(1)], texto)


class Audio:
    """Texto -> MP3 com edge-tts; se falhar, WAV com o TTS do Gemini."""

    def __init__(self, voz: str, gemini=None, voz_gemini: str = "Kore"):
        self.voz = voz
        self.gemini = gemini
        self.voz_gemini = voz_gemini

    async def _edge(self, texto: str) -> bytes:
        import edge_tts

        dados = bytearray()
        async for parte in edge_tts.Communicate(texto, self.voz, rate="+8%").stream():
            if parte["type"] == "audio":
                dados += parte["data"]
        return bytes(dados)

    def __call__(self, texto: str) -> tuple[str, bytes]:
        texto = para_fala(texto)
        erro: Exception | None = None
        for tentativa in range(3):
            try:
                dados = asyncio.run(self._edge(texto))
                if len(dados) > 1000:
                    return "resumo.mp3", dados
            except Exception as e:  # noqa: BLE001
                erro = e
                log.warning("edge-tts falhou (tentativa %s): %s", tentativa + 1, e)
            time.sleep(3 * (tentativa + 1))
        if self.gemini is not None:
            return "resumo.wav", self.gemini.fala(texto, self.voz_gemini)
        raise RuntimeError(f"nenhum TTS funcionou: {erro}")
