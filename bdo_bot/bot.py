"""Fluxo principal: olha as fontes, decide o que e novo e posta no Discord."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from . import prompts
from .fontes import FONTES, URL_LISTA_KR, Tipo, classificar
from .formatos import (BRASILIA, COR, embeds_comparacao, embeds_evento, embeds_hotfix, embeds_loja,
                       embeds_patch, fim_do_evento, lembrete)
from .glossario import Glossario, Termo
from .paginas import Detalhe, ItemLista, ler_detalhe, ler_lista
from .texto import candidatas_imagem, html_para_texto, tamanho_imagem

log = logging.getLogger(__name__)

MAX_POR_FONTE = 5          # posts novos processados por fonte em cada execucao
MAX_TENTATIVAS = 4         # depois disso o post e marcado como visto e o erro vai para #bot-logs
GUARDAR_VISTOS = 300
JANELA_PREVIEW = timedelta(days=4)

CANAL = {
    Tipo.GLOBAL_LAB: "patch", Tipo.PREVIEW_SEA: "patch", Tipo.PATCH_SA: "patch", Tipo.HOTFIX_SA: "patch",
    Tipo.EVENTO_SA: "eventos", Tipo.LOJA_SA: "loja",
}


def _mime(dados: bytes) -> str:
    if dados[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if dados[:4] == b"RIFF":
        return "image/webp"
    return "image/jpeg"


class Bot:
    def __init__(self, *, baixar: Callable[[str], str | None], baixar_bytes: Callable[..., bytes | None], ia,
                 audio: Callable[[str], tuple[str, bytes]], discord, glossario: Glossario,
                 itens: Callable[[str, str], list[tuple[str, str]]], estado: dict, agora: datetime):
        self.baixar = baixar
        self.baixar_bytes = baixar_bytes
        self.ia = ia
        self.audio = audio
        self.discord = discord
        self.glossario = glossario
        self.itens = itens
        self.estado = estado
        self.agora = agora
        self.erros: list[str] = []
        self.termos_novos: list[Termo] = []
        for chave, padrao in (("vistos", {}), ("eventos", {}), ("previews", []), ("tentativas", {}),
                              ("termos_propostos", [])):
            self.estado.setdefault(chave, padrao)

    # ------------------------------------------------------------------ geral

    def rodar(self, fontes: list[str]) -> None:
        for nome in fontes:
            try:
                self._fonte(nome)
            except Exception as e:  # noqa: BLE001 - uma fonte quebrada nao derruba as outras
                log.exception("fonte %s falhou", nome)
                self.erros.append(f"{nome}: {type(e).__name__}: {e}")
        self.lembretes()

    def _fonte(self, nome: str) -> None:
        fonte = FONTES[nome]
        html = self.baixar(fonte.url_lista)
        itens = ler_lista(fonte.layout, html) if html else []
        if not itens:
            log.info("%s: listagem vazia ou site em manutencao", nome)
            return
        vistos: list[str] = self.estado["vistos"].get(nome)
        if vistos is None:
            # primeira execucao: nao anuncia o passado, exceto eventos ainda ativos
            self.estado["vistos"][nome] = [] if nome == "sa_eventos" else [i.post_id for i in itens]
            if nome != "sa_eventos":
                return
            vistos = self.estado["vistos"][nome]
        novos = [i for i in itens if i.post_id not in vistos][:MAX_POR_FONTE]
        for item in reversed(novos):  # do mais antigo para o mais novo
            tipo = classificar(nome, item.titulo)
            chave = f"{nome}:{item.post_id}"
            if tipo is not None:
                try:
                    self._processar(nome, tipo, item)
                except Exception as e:  # noqa: BLE001
                    log.exception("falha em %s", chave)
                    n = self.estado["tentativas"].get(chave, 0) + 1
                    self.estado["tentativas"][chave] = n
                    desistiu = n >= MAX_TENTATIVAS
                    self.erros.append(f"{item.titulo} ({item.url}) tentativa {n}"
                                      f"{' - desisti deste post' if desistiu else ''}: {type(e).__name__}: {e}")
                    if not desistiu:
                        continue
            self.estado["tentativas"].pop(chave, None)
            vistos.append(item.post_id)
        del vistos[:-GUARDAR_VISTOS]

    def _detalhe(self, layout: str, url: str) -> tuple[Detalhe, str]:
        html = self.baixar(url)
        if not html:
            raise RuntimeError(f"nao consegui abrir {url}")
        det = ler_detalhe(layout, html)
        texto = html_para_texto(det.corpo_html)
        if not texto:
            raise RuntimeError(f"post sem texto: {url}")
        return det, texto

    def _imagens(self, corpo_html: str, evento: bool) -> list[tuple[bytes, str]]:
        cabecas: dict[str, tuple[int, int] | None] = {}

        def tamanho(url: str):
            if url not in cabecas:
                dados = self.baixar_bytes(url, 65536)
                cabecas[url] = tamanho_imagem(dados) if dados else None
            return cabecas[url]

        saida = []
        for url in candidatas_imagem(corpo_html, tamanho, evento=evento):
            dados = self.baixar_bytes(url, None)
            if dados:
                saida.append((dados, _mime(dados)))
        return saida

    def _falar(self, roteiro: str) -> tuple[str, bytes] | None:
        if not (roteiro or "").strip():
            return None
        try:
            return self.audio(roteiro)
        except Exception as e:  # noqa: BLE001 - sem audio o post sai mesmo assim
            log.exception("audio falhou")
            self.erros.append(f"áudio falhou (post enviado sem áudio): {e}")
            return None

    @staticmethod
    def _data(det: Detalhe) -> str:
        return det.publicado.astimezone(BRASILIA).strftime("%d/%m") if det.publicado else ""

    # ------------------------------------------------------------------ tipos

    def _processar(self, nome: str, tipo: Tipo, item: ItemLista) -> None:
        layout = FONTES[nome].layout
        det, texto = self._detalhe(layout, item.url)
        termos = self.glossario.relevantes(texto)
        if tipo in (Tipo.GLOBAL_LAB, Tipo.PREVIEW_SEA):
            self._patch_estrangeiro(tipo, item, det, texto, termos)
        elif tipo == Tipo.PATCH_SA:
            self._patch_sa(item, det, texto, termos)
        elif tipo == Tipo.HOTFIX_SA:
            r = self.ia.json(prompts.hotfix(texto, termos), prompts.SCHEMA_HOTFIX)
            self.discord.enviar("patch", embeds_hotfix(r, det.titulo or item.titulo, item.url))
        elif tipo == Tipo.EVENTO_SA:
            self._evento(item, det, texto, termos)
        elif tipo == Tipo.LOJA_SA:
            r = self.ia.json(prompts.loja(texto, termos), prompts.SCHEMA_LOJA)
            self.discord.enviar("loja", embeds_loja(r, item.url, item.imagem))

    def _patch_estrangeiro(self, tipo: Tipo, item: ItemLista, det: Detalhe, texto: str, termos: list[Termo]):
        if tipo == Tipo.GLOBAL_LAB:
            lingua, idioma = "ko", "coreano (às vezes com partes em inglês)"
            contexto = "Global Lab, o servidor de testes; o conteúdo pode mudar antes de chegar ao SA"
            cabecalho = f"🧪 Global Lab (teste) {self._data(det)}"
            rodape = "Global Lab: servidor de testes, o conteúdo pode mudar antes de chegar ao SA"
        else:
            lingua, idioma = "en", "inglês"
            contexto = "servidor SEA; o SA costuma receber o mesmo patch algumas horas depois"
            cabecalho = f"👀 Preview do update SA {self._data(det)}"
            rodape = "Preview via SEA: o SA costuma receber o mesmo patch ~4h depois"
        imagens = self._imagens(det.corpo_html, evento=False)
        r = self.ia.json(prompts.patch(texto, idioma, contexto, termos, self.itens(texto, lingua)),
                         prompts.SCHEMA_PATCH, imagens)
        embeds = embeds_patch(r, cabecalho, item.url, item.imagem, rodape, COR[tipo.value])
        self.discord.enviar("patch", embeds, self._falar(r.get("roteiro_audio", "")))
        if tipo == Tipo.PREVIEW_SEA:
            publicado = det.publicado or self.agora
            self.estado["previews"].append({"id": item.post_id, "url": item.url, "publicado": publicado.isoformat()})
            del self.estado["previews"][:-10]

    def _preview_da_semana(self, quando: datetime) -> dict | None:
        for p in reversed(self.estado["previews"]):
            publicado = datetime.fromisoformat(p["publicado"])
            if not p.get("usado") and timedelta(0) <= quando - publicado <= JANELA_PREVIEW:
                return p
        return None

    def _patch_sa(self, item: ItemLista, det: Detalhe, texto: str, termos: list[Termo]) -> None:
        titulo = f"Update SA {self._data(det)}".strip()
        preview = self._preview_da_semana(det.publicado or self.agora)
        if preview is None:
            imagens = self._imagens(det.corpo_html, evento=False)
            r = self.ia.json(prompts.patch(texto, "português (texto oficial do SA)", "servidor SA", termos, []),
                             prompts.SCHEMA_PATCH, imagens)
            embeds = embeds_patch(r, f"🟢 {titulo}", item.url, item.imagem, "Atualização SA", COR["patch_sa"])
            self.discord.enviar("patch", embeds, self._falar(r.get("roteiro_audio", "")))
            return
        _, texto_sea = self._detalhe("pa", preview["url"])
        termos_sea = list({t: None for t in termos + self.glossario.relevantes(texto_sea)})
        r = self.ia.json(prompts.comparar(texto, texto_sea, termos_sea), prompts.SCHEMA_COMPARA)
        anexo = None if r.get("conteudo_igual") else self._falar(r.get("roteiro_audio", ""))
        self.discord.enviar("patch", embeds_comparacao(r, titulo, item.url, preview["url"]), anexo)
        preview["usado"] = True
        self._aprender(texto, texto_sea, det.publicado or self.agora)

    def _texto_kr(self, quando: datetime) -> str:
        """Patch coreano da mesma semana: o maior post de "업데이트" publicado ate 4 dias antes."""
        candidatos = [i for i in ler_lista("sa", self.baixar(URL_LISTA_KR) or "")
                      if "업데이트" in i.titulo and "보안" not in i.titulo][:6]
        melhor = ""
        for item in candidatos:
            det, texto = self._detalhe("sa", item.url)
            if not det.publicado or quando - det.publicado > JANELA_PREVIEW:
                break  # listagem vem do mais novo para o mais velho
            if det.publicado <= quando and len(texto) > len(melhor):
                melhor = texto
        return melhor

    def _aprender(self, texto_sa: str, texto_sea: str, quando: datetime) -> None:
        try:
            try:
                texto_kr = self._texto_kr(quando)
            except Exception:  # noqa: BLE001 - coreano e opcional
                texto_kr = ""
            conhecidos = self.glossario.relevantes(texto_sa)
            r = self.ia.json(prompts.aprender_termos(texto_sa, texto_sea, texto_kr, conhecidos), prompts.SCHEMA_TERMOS)
            ja = set(self.estado["termos_propostos"])
            for t in self.glossario.novos(r.get("termos", [])):
                chave = (t.ko or t.en).lower()
                if chave not in ja:
                    ja.add(chave)
                    self.termos_novos.append(t)
            self.estado["termos_propostos"] = sorted(ja)[-2000:]
        except Exception as e:  # noqa: BLE001 - aprender termos nunca impede o post
            log.exception("aprendizado de termos falhou")
            self.erros.append(f"aprendizado de termos falhou: {e}")

    def _evento(self, item: ItemLista, det: Detalhe, texto: str, termos: list[Termo]) -> None:
        imagens = self._imagens(det.corpo_html, evento=True)
        r = self.ia.json(prompts.evento(texto, termos, bool(imagens)), prompts.SCHEMA_EVENTO, imagens)
        fim = fim_do_evento(r.get("fim_brasilia", ""))
        if fim and not (self.agora - timedelta(days=1) < fim < self.agora + timedelta(days=200)):
            fim = None  # data improvavel: melhor nao mostrar contagem errada
        self.discord.enviar("eventos", embeds_evento(r, item.url, item.imagem, fim),
                            self._falar(r.get("roteiro_audio", "")))
        if fim:
            self.estado["eventos"][item.post_id] = {
                "titulo": r.get("titulo") or item.titulo, "url": item.url, "fim": fim.isoformat(),
                "lembrado": fim - self.agora <= timedelta(hours=24),
            }

    def lembretes(self) -> None:
        for post_id, ev in list(self.estado["eventos"].items()):
            fim = datetime.fromisoformat(ev["fim"])
            if fim <= self.agora:
                del self.estado["eventos"][post_id]
            elif not ev.get("lembrado") and fim - self.agora <= timedelta(hours=24):
                self.discord.enviar("eventos", [lembrete(ev["titulo"], ev["url"], fim)])
                ev["lembrado"] = True


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)
