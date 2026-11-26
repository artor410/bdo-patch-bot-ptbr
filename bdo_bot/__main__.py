"""Linha de comando do bot.

    python -m bdo_bot rodar [--meia-hora]     checagem normal (GitHub Actions a cada 30 min)
    python -m bdo_bot testar-fonte FONTE      reposta o post mais recente da FONTE no #bot-logs
    python -m bdo_bot testar-vozes            manda um audio de cada voz no #bot-logs
    python -m bdo_bot glossario-inicial N     compara os ultimos N patches SA/SEA/KR e abre um PR de termos
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

from . import prompts
from .bot import Bot, agora_utc
from .discord import Discord
from .fontes import FONTES, URL_LISTA_KR, fontes_para_checar
from .formatos import COR
from .github_pr import abrir_pr_glossario
from .glossario import Glossario, Termo
from .ia import MODELOS_PADRAO, Gemini
from .integracoes import Audio, ItensArsha, Web, deve_avisar
from .paginas import ler_detalhe, ler_lista
from .texto import html_para_texto

RAIZ = Path(__file__).resolve().parent.parent
ARQ_ESTADO = RAIZ / "data" / "estado.json"
ARQ_GLOSSARIO = RAIZ / "data" / "glossario.json"
CACHE = RAIZ / ".cache" / "arsha"

VOZES = {"Francisca (feminina)": "pt-BR-FranciscaNeural", "Antonio (masculina)": "pt-BR-AntonioNeural"}

log = logging.getLogger("bdo_bot")


def _webhooks(env: str) -> list[str]:
    return [u.strip() for u in os.environ.get(env, "").splitlines() if u.strip()]


def _discord(tudo_nos_logs: bool = False) -> Discord:
    canais = {
        "patch": _webhooks("DISCORD_WEBHOOK_PATCH"),
        "eventos": _webhooks("DISCORD_WEBHOOK_EVENTOS"),
        "loja": _webhooks("DISCORD_WEBHOOK_LOJA"),
        "logs": _webhooks("DISCORD_WEBHOOK_LOGS"),
    }
    if tudo_nos_logs:
        canais = {c: canais["logs"] for c in canais}
    return Discord(canais, token_bot=os.environ.get("DISCORD_BOT_TOKEN", ""))


def _gemini() -> Gemini:
    chave = os.environ.get("GEMINI_API_KEY", "")
    if not chave:
        sys.exit("GEMINI_API_KEY não configurada (rode scripts/configurar-segredos.ps1).")
    modelos = [m.strip() for m in os.environ.get("GEMINI_MODELOS", "").split(",") if m.strip()]
    return Gemini(chave, modelos or MODELOS_PADRAO)


def _estado() -> dict:
    return json.loads(ARQ_ESTADO.read_text(encoding="utf-8")) if ARQ_ESTADO.exists() else {}


def _salvar_estado(estado: dict) -> None:
    ARQ_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ARQ_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _montar_bot(estado: dict, discord: Discord) -> Bot:
    web = Web()
    gemini = _gemini()
    agora = agora_utc()
    voz = os.environ.get("TTS_VOZ") or VOZES["Francisca (feminina)"]
    return Bot(baixar=web.texto, baixar_bytes=web.bytes, ia=gemini, audio=Audio(voz, gemini), discord=discord,
               glossario=Glossario.carregar(ARQ_GLOSSARIO), itens=ItensArsha(CACHE, web.texto, agora),
               estado=estado, agora=agora)


def _avisar(discord: Discord, estado: dict, bot: Bot) -> None:
    for erro in bot.erros:
        log.error(erro)
        if deve_avisar(estado, erro, bot.agora):
            discord.enviar("logs", [{"title": "⚠️ Problema no bot", "description": erro[:3900], "color": 0xE74C3C}])


def _pr_termos(discord: Discord, termos: list[Termo], agora) -> None:
    if not termos:
        return
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
    if not (repo and token):
        log.info("termos novos (sem GitHub para abrir PR): %s", termos)
        return
    url = abrir_pr_glossario(termos, repo, token, agora.strftime("%Y-%m-%d-%H%M"))
    if url:
        discord.enviar("logs", [{"title": f"📚 {len(termos)} termo(s) novo(s) para aprovar", "url": url,
                                 "description": f"Revise e aprove (Merge) aqui: {url}", "color": COR["lembrete"]}])


def rodar(meia_hora: bool) -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        log.warning("GEMINI_API_KEY ainda não configurada; nada a fazer até as chaves serem coladas.")
        return
    estado = _estado()
    discord = _discord()
    bot = _montar_bot(estado, discord)
    fontes = fontes_para_checar(bot.agora, meia_hora)
    log.info("checando: %s", fontes or "(nenhuma fonte nesta meia hora; só lembretes)")
    bot.rodar(fontes)
    try:
        _pr_termos(discord, bot.termos_novos, bot.agora)
    except Exception as e:  # noqa: BLE001
        bot.erros.append(f"não consegui abrir o PR do glossário: {e}")
    _avisar(discord, estado, bot)
    _salvar_estado(estado)


def testar_fonte(fonte: str) -> None:
    """Processa de novo o post mais recente da fonte, mandando tudo para o #bot-logs. Nao mexe no estado."""
    discord = _discord(tudo_nos_logs=True)
    web = Web()
    itens = ler_lista(FONTES[fonte].layout, web.texto(FONTES[fonte].url_lista) or "")
    if not itens:
        sys.exit(f"não achei posts em {fonte} (site em manutenção?)")
    estado = {"vistos": {fonte: [i.post_id for i in itens[1:]]}, "previews": []}
    bot = _montar_bot(estado, discord)
    bot.rodar([fonte])
    _avisar(discord, {}, bot)
    if bot.termos_novos:
        log.info("termos que seriam sugeridos: %s", bot.termos_novos)


def testar_vozes() -> None:
    discord = _discord()
    gemini = _gemini()
    texto = ("Olá, aventureiros! Este é um teste de voz do bot de patches do Black Desert. "
             "O update desta semana traz a expansão de dificuldade do Abismo dos Imortais, "
             "melhorias para a Caçadora e um evento novo que termina na quarta-feira.")
    for nome, voz in VOZES.items():
        arquivo, dados = Audio(voz, gemini)(texto)
        discord.enviar("logs", [{"title": f"🔊 Teste de voz: {nome}",
                                 "description": f"Para usar esta voz, crie a variável `TTS_VOZ` = `{voz}`.",
                                 "color": COR["lembrete"]}], anexo=(arquivo, dados))


def glossario_inicial(semanas: int) -> None:
    """Compara os ultimos patches SA x SEA x KR e abre um PR com os termos encontrados."""
    web = Web()
    gemini = _gemini()
    discord = _discord()
    glossario = Glossario.carregar(ARQ_GLOSSARIO)
    sa = [i for i in ler_lista("sa", web.texto(FONTES["sa_atualizacao"].url_lista) or "")
          if "notas da atualiza" in i.titulo.lower()][:semanas]
    sea = [i for i in ler_lista("pa", web.texto(FONTES["sea"].url_lista) or "")
           if "update details" in i.titulo.lower() and "[hotfix]" not in i.titulo.lower()]
    kr = [i for i in ler_lista("sa", web.texto(URL_LISTA_KR) or "") if "업데이트" in i.titulo]

    def detalhe(layout, item):
        d = ler_detalhe(layout, web.texto(item.url) or "")
        return d, html_para_texto(d.corpo_html)

    sea_det = [detalhe("pa", i) for i in sea[: semanas + 2]]
    kr_det = [detalhe("sa", i) for i in kr[: semanas + 4]]
    todos: list[dict] = []
    for item in sa:
        d_sa, t_sa = detalhe("sa", item)
        if not d_sa.publicado:
            continue

        def perto(lista, dias):
            return next((t for d, t in lista if d.publicado and timedelta(0) <= d_sa.publicado - d.publicado
                         <= timedelta(days=dias)), "")

        t_sea, t_kr = perto(sea_det, 2), perto(kr_det, 4)
        if not t_sea:
            log.warning("sem SEA para %s", item.titulo)
            continue
        log.info("comparando %s", item.titulo)
        r = gemini.json(prompts.aprender_termos(t_sa, t_sea, t_kr, glossario.relevantes(t_sa)), prompts.SCHEMA_TERMOS)
        for t in r.get("termos", []):
            t["evidencia"] = f"{item.titulo}: {t.get('evidencia', '')}"[:160]
        todos += r.get("termos", [])
    novos = glossario.novos(todos)
    log.info("%d termos novos", len(novos))
    _pr_termos(discord, novos, agora_utc())


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="bdo_bot")
    sub = p.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("rodar")
    r.add_argument("--meia-hora", action="store_true")
    t = sub.add_parser("testar-fonte")
    t.add_argument("fonte", choices=list(FONTES))
    sub.add_parser("testar-vozes")
    g = sub.add_parser("glossario-inicial")
    g.add_argument("semanas", type=int, nargs="?", default=4)
    a = p.parse_args(argv)
    if a.comando == "rodar":
        rodar(a.meia_hora)
    elif a.comando == "testar-fonte":
        testar_fonte(a.fonte)
    elif a.comando == "testar-vozes":
        testar_vozes()
    else:
        glossario_inicial(a.semanas)


if __name__ == "__main__":
    main()
