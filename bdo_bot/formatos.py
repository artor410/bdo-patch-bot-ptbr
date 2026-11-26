"""Monta os embeds do Discord a partir das respostas da IA."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

BRASILIA = timezone(timedelta(hours=-3))
LIMITE_DESCRICAO = 4000

COR = {
    "global_lab": 0x9B59B6,
    "preview_sea": 0xF1C40F,
    "patch_sa": 0x2ECC71,
    "hotfix_sa": 0x95A5A6,
    "evento_sa": 0x3498DB,
    "loja_sa": 0xE91E63,
    "lembrete": 0xE67E22,
}

AVISO_IA = "Resumo feito por IA a partir do post oficial; na dúvida, confira o link."


def fim_do_evento(texto: str) -> datetime | None:
    try:
        local = datetime.strptime((texto or "").strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        return None
    return local.replace(tzinfo=BRASILIA).astimezone(timezone.utc)


def _ts(fim: datetime, estilo: str) -> str:
    return f"<t:{int(fim.timestamp())}:{estilo}>"


def _bullets(itens: list[str]) -> str:
    return "\n".join(f"• {i.strip()}" for i in itens if i and i.strip())


def _quebrar(texto: str) -> list[str]:
    """Quebra em pedacos de ate LIMITE_DESCRICAO caracteres, preferindo quebras de linha."""
    pedacos: list[str] = []
    while len(texto) > LIMITE_DESCRICAO:
        corte = texto.rfind("\n", 0, LIMITE_DESCRICAO)
        if corte < LIMITE_DESCRICAO // 2:
            corte = LIMITE_DESCRICAO
        pedacos.append(texto[:corte].rstrip())
        texto = texto[corte:].lstrip("\n")
    if texto.strip():
        pedacos.append(texto)
    return pedacos


def _montar(titulo: str, url: str, corpo: str, cor: int, imagem: str = "", rodape: str = "") -> list[dict]:
    embeds = []
    for i, pedaco in enumerate(_quebrar(corpo) or [""]):
        e: dict = {"description": pedaco, "color": cor}
        if i == 0:
            e["title"] = titulo[:256]
            if url:
                e["url"] = url
            if imagem:
                e["image"] = {"url": imagem}
        embeds.append(e)
    embeds[-1]["footer"] = {"text": (rodape + " • " if rodape else "") + AVISO_IA}
    return embeds


def embeds_patch(r: dict, cabecalho: str, url: str, imagem: str, rodape: str, cor: int) -> list[dict]:
    partes = []
    if r.get("destaques"):
        partes.append("**Destaques**\n" + _bullets(r["destaques"]))
    for s in r.get("secoes", []):
        if s.get("itens"):
            partes.append(f"**{s.get('nome', '').strip()}**\n" + _bullets(s["itens"]))
    partes.append(f"[Ler o post completo]({url})")
    titulo = f"{cabecalho}: {r.get('titulo_curto', '').strip()}" if r.get("titulo_curto") else cabecalho
    return _montar(titulo, url, "\n\n".join(partes), cor, imagem, rodape)


def embeds_evento(r: dict, url: str, imagem: str, fim: datetime | None) -> list[dict]:
    partes = [r.get("resumo", "").strip()]
    if fim:
        partes.append(f"⏰ **Termina:** {_ts(fim, 'F')} ({_ts(fim, 'R')})")
    elif r.get("periodo"):
        partes.append(f"⏰ **Período:** {r['periodo']}")
    if r.get("como_participar"):
        partes.append("**Como participar**\n" + _bullets(r["como_participar"]))
    if r.get("recompensas"):
        partes.append("**Recompensas**\n" + _bullets(r["recompensas"]))
    if fim and r.get("periodo"):
        partes.append(f"_Período: {r['periodo']}_")
    partes.append(f"[Ver o evento no site]({url})")
    titulo = "🎉 " + (r.get("titulo") or "Novo evento").strip()
    return _montar(titulo, url, "\n\n".join(p for p in partes if p), COR["evento_sa"], imagem, "Eventos SA")


def embeds_loja(r: dict, url: str, imagem: str) -> list[dict]:
    partes = [_bullets(r.get("novidades", []))]
    if r.get("periodo"):
        partes.append(f"⏰ **Período:** {r['periodo']}")
    partes.append(f"[Ver na página oficial]({url})")
    return _montar("💎 " + (r.get("titulo") or "Loja de Pérolas").strip(), url, "\n\n".join(partes),
                   COR["loja_sa"], imagem, "Loja de Pérolas SA")


def embeds_hotfix(r: dict, titulo: str, url: str) -> list[dict]:
    corpo = _bullets(r.get("itens", [])) + f"\n\n[Ler o post completo]({url})"
    return _montar(f"🔧 {titulo}", url, corpo, COR["hotfix_sa"], rodape="Atualização SA")


def embeds_comparacao(r: dict, titulo: str, url: str, url_preview: str) -> list[dict]:
    if r.get("conteudo_igual"):
        corpo = (f"O update do SA saiu e é **igual ao preview do SEA** já anunciado aqui.\n\n"
                 f"[Post oficial SA]({url}) · [Preview SEA]({url_preview})")
        return _montar(f"✅ {titulo}", url, corpo, COR["patch_sa"], rodape="Atualização SA")
    corpo = ("O update do SA saiu. Ele segue o preview do SEA, **com estas diferenças**:\n\n"
             + _bullets(r.get("diferencas", [])) + f"\n\n[Post oficial SA]({url}) · [Preview SEA]({url_preview})")
    return _montar(f"🟢 {titulo}", url, corpo, COR["patch_sa"], rodape="Atualização SA")


def lembrete(titulo: str, url: str, fim: datetime) -> dict:
    return {
        "title": f"⏳ Acaba em breve: {titulo}"[:256],
        "url": url,
        "description": f"Termina {_ts(fim, 'R')} ({_ts(fim, 'F')}). Corre se ainda não completou!",
        "color": COR["lembrete"],
    }
