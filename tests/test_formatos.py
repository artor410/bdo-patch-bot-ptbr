from datetime import datetime, timezone

from bdo_bot.formatos import embeds_evento, embeds_patch, fim_do_evento, lembrete


def test_fim_do_evento_converte_brasilia_para_utc():
    assert fim_do_evento("2026-12-02T23:59") == datetime(2026, 12, 3, 2, 59, tzinfo=timezone.utc)
    assert fim_do_evento("") is None
    assert fim_do_evento("dia 2") is None


def test_embeds_patch_quebra_texto_grande_e_mantem_link_no_primeiro():
    r = {"titulo_curto": "Abismo", "destaques": ["a" * 150] * 8,
         "secoes": [{"nome": f"S{i}", "itens": ["b" * 150] * 6} for i in range(6)], "roteiro_audio": "x"}
    es = embeds_patch(r, cabecalho="👀 Preview SA (via SEA)", url="https://x", imagem="https://img",
                      rodape="Fonte: SEA", cor=1)
    assert es[0]["url"] == "https://x" and es[0]["title"].startswith("👀 Preview SA (via SEA)")
    assert es[0]["image"]["url"] == "https://img"
    assert all(len(e["description"]) <= 4096 for e in es)
    assert len(es) > 1
    assert "footer" in es[-1]


def test_embed_evento_usa_timestamp_relativo_do_discord():
    r = {"titulo": "Salve o Banquete", "resumo": "Caçe chefes.", "como_participar": ["Mate Targargo"],
         "recompensas": ["Pedra Cron x10"], "periodo": "19/11 até 02/12", "fim_brasilia": "2026-12-02T23:59",
         "roteiro_audio": ""}
    fim = fim_do_evento(r["fim_brasilia"])
    e = embeds_evento(r, url="https://ev", imagem="", fim=fim)[0]
    ts = int(fim.timestamp())
    assert f"<t:{ts}:R>" in e["description"] and f"<t:{ts}:F>" in e["description"]
    assert "Mate Targargo" in e["description"]


def test_lembrete_e_curto_e_tem_contagem():
    fim = datetime(2026, 12, 3, 2, 59, tzinfo=timezone.utc)
    e = lembrete("Salve o Banquete", "https://ev", fim)
    assert "Salve o Banquete" in e["title"]
    assert f"<t:{int(fim.timestamp())}:R>" in e["description"]
