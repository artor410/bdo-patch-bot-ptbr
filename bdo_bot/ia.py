"""Cliente minimo da API do Gemini (plano gratuito), com troca automatica de modelo."""

from __future__ import annotations

import base64
import json
import logging
import time

import httpx

log = logging.getLogger(__name__)

API = "https://generativelanguage.googleapis.com/v1beta/models"

# Do melhor para o mais "barato" em cota. Trocavel pela variavel GEMINI_MODELOS (separados por virgula).
MODELOS_PADRAO = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
MODELOS_TTS_PADRAO = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]


class IAIndisponivel(RuntimeError):
    pass


class Gemini:
    def __init__(self, chave: str, modelos: list[str] | None = None, http: httpx.Client | None = None,
                 espera: float = 20.0):
        self.chave = chave
        self.modelos = modelos or MODELOS_PADRAO
        self.http = http or httpx.Client(timeout=300)
        self.espera = espera

    def _post(self, modelo: str, corpo: dict) -> dict:
        r = self.http.post(f"{API}/{modelo}:generateContent", json=corpo,
                           headers={"x-goog-api-key": self.chave})
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(f"{modelo}: HTTP {r.status_code} {r.text[:300]}", request=r.request, response=r)
        return r.json()

    def _tentar(self, modelos: list[str], corpo: dict) -> dict:
        erros = []
        for modelo in modelos:
            for tentativa in range(2):
                try:
                    return self._post(modelo, corpo)
                except (httpx.HTTPStatusError, httpx.TransportError) as e:
                    status = getattr(getattr(e, "response", None), "status_code", 0)
                    erros.append(str(e)[:200])
                    log.warning("Gemini %s falhou (%s)", modelo, str(e)[:200])
                    if status in (400, 401, 403, 404):
                        break  # pedido ou modelo invalido: tenta o proximo modelo
                    if tentativa == 0 and self.espera:
                        time.sleep(self.espera)
        raise IAIndisponivel("; ".join(erros) or "nenhum modelo configurado")

    def json(self, prompt: str, schema: dict, imagens: list[tuple[bytes, str]] | None = None,
             temperatura: float = 0.3) -> dict:
        partes: list[dict] = [{"text": prompt}]
        for dados, mime in imagens or []:
            partes.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(dados).decode()}})
        corpo = {
            "contents": [{"role": "user", "parts": partes}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": schema,
                "temperature": temperatura,
            },
        }
        resposta = self._tentar(self.modelos, corpo)
        try:
            texto = "".join(p.get("text", "") for p in resposta["candidates"][0]["content"]["parts"])
            return json.loads(texto)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise IAIndisponivel(f"resposta inesperada do Gemini: {str(resposta)[:300]}") from e

    def fala(self, texto: str, voz: str, modelos: list[str] | None = None) -> bytes:
        """Texto -> audio PCM 16 bits 24 kHz mono (Gemini TTS). Devolve o WAV pronto."""
        corpo = {
            "contents": [{"parts": [{"text": texto}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voz}}},
            },
        }
        resposta = self._tentar(modelos or MODELOS_TTS_PADRAO, corpo)
        try:
            dados = resposta["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
        except (KeyError, IndexError) as e:
            raise IAIndisponivel("Gemini TTS nao devolveu audio") from e
        return pcm_para_wav(base64.b64decode(dados))


def pcm_para_wav(pcm: bytes, taxa: int = 24000) -> bytes:
    import struct

    cabecalho = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack(
        "<IHHIIHH", 16, 1, 1, taxa, taxa * 2, 2, 16) + b"data" + struct.pack("<I", len(pcm))
    return cabecalho + pcm
