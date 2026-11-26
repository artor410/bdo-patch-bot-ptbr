"""Envio por webhook do Discord.

Cada canal pode ter varios webhooks (um por linha no segredo), por exemplo o canal do
servidor do bot e o canal do servidor da guild. Se DISCORD_BOT_TOKEN existir, as mensagens
em canais de anuncio tambem sao "publicadas" para quem segue o canal.
"""

from __future__ import annotations

import json
import logging
import time

import httpx

log = logging.getLogger(__name__)

NOME = "BDO Patch PT-BR"
LIMITE_TOTAL = 6000
LIMITE_EMBEDS = 10


def _tamanho(e: dict) -> int:
    n = len(e.get("title", "")) + len(e.get("description", ""))
    n += len((e.get("footer") or {}).get("text", "")) + len((e.get("author") or {}).get("name", ""))
    for f in e.get("fields", []):
        n += len(f.get("name", "")) + len(f.get("value", ""))
    return n


def dividir_embeds(embeds: list[dict]) -> list[list[dict]]:
    grupos: list[list[dict]] = []
    atual: list[dict] = []
    total = 0
    for e in embeds:
        n = _tamanho(e)
        if atual and (total + n > LIMITE_TOTAL or len(atual) >= LIMITE_EMBEDS):
            grupos.append(atual)
            atual, total = [], 0
        atual.append(e)
        total += n
    if atual:
        grupos.append(atual)
    return grupos


class ErroEnvio(RuntimeError):
    """Nenhum webhook do canal aceitou a mensagem."""


class Discord:
    def __init__(self, webhooks: dict[str, list[str]], http: httpx.Client | None = None,
                 token_bot: str = "", avatar: str = "", pausa: float = 3.0):
        self.pausa = pausa
        self.webhooks = webhooks
        self.http = http or httpx.Client(timeout=60)
        self.token_bot = token_bot
        self.avatar = avatar
        self.avisos: list[str] = []  # problemas nao fatais, para o #bot-logs

    def _post(self, url: str, payload: dict, anexo: tuple[str, bytes] | None) -> dict | None:
        for tentativa in range(4):
            try:
                if anexo:
                    r = self.http.post(url, params={"wait": "true"},
                                       data={"payload_json": json.dumps(payload)},
                                       files={"files[0]": (anexo[0], anexo[1])})
                else:
                    r = self.http.post(url, params={"wait": "true"}, json=payload)
            except httpx.TransportError as e:
                log.warning("falha de rede no Discord: %s", e)
                time.sleep(self.pausa)
                continue
            if r.status_code == 429 and tentativa < 3:
                espera = float((r.json() if r.content else {}).get("retry_after", 2))
                time.sleep(min(espera, 30))
                continue
            if r.status_code >= 400:
                log.error("Discord recusou (%s): %s", r.status_code, r.text[:300])
                return None
            return r.json() if r.content else {}
        return None

    def _publicar(self, msg: dict) -> None:
        if not self.token_bot or not msg or "channel_id" not in msg:
            return
        try:
            r = self.http.post(
                f"https://discord.com/api/v10/channels/{msg['channel_id']}/messages/{msg['id']}/crosspost",
                headers={"Authorization": f"Bot {self.token_bot}"})
        except httpx.TransportError as e:
            self.avisos.append(f"não consegui publicar a mensagem para quem segue o canal: {e}")
            return
        if r.status_code > 400:  # 400 so significa "este canal nao e de anuncio"
            self.avisos.append(f"não consegui publicar a mensagem para quem segue o canal "
                               f"(HTTP {r.status_code}; o bot tem permissão no canal?)")

    def enviar(self, canal: str, embeds: list[dict], anexo: tuple[str, bytes] | None = None,
               texto: str = "") -> int:
        """Envia para todos os webhooks do canal. Devolve quantos webhooks aceitaram.

        Se nenhum aceitar, levanta ErroEnvio (o post sera tentado de novo na proxima execucao).
        Se ao menos um aceitar, nao levanta: reenviar duplicaria o post nos servidores que ja receberam.
        """
        urls = [u for u in self.webhooks.get(canal, []) if u]
        if not urls:
            log.warning("Canal %s sem webhook configurado; nada enviado.", canal)
            return 0
        aceitas = 0
        grupos = dividir_embeds(embeds) or [[]]
        for url in urls:
            ok = False
            for i, grupo in enumerate(grupos):
                payload = {"username": NOME, "embeds": grupo, "allowed_mentions": {"parse": []}}
                if self.avatar:
                    payload["avatar_url"] = self.avatar
                if i == 0 and texto:
                    payload["content"] = texto[:2000]
                msg = self._post(url, payload, anexo if i == 0 else None)
                if msg is not None:
                    ok = True
                    self._publicar(msg)
            aceitas += ok
        if aceitas == 0:
            raise ErroEnvio(f"o Discord recusou o envio para o canal {canal}")
        if aceitas < len(urls):
            self.avisos.append(f"{len(urls) - aceitas} de {len(urls)} webhooks do canal {canal} falharam")
        return aceitas
