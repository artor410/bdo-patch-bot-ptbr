"""Fluxo completo com paginas, IA, audio e Discord falsos."""

from datetime import datetime, timedelta, timezone

from bdo_bot.bot import Bot
from bdo_bot.fontes import FONTES
from bdo_bot.glossario import Glossario, Termo

AGORA = datetime(2026, 11, 26, 9, 0, tzinfo=timezone.utc)


def lista_sa(*posts):
    lis = "".join(
        f'<li><a href="https://sa/Detail?groupContentNo={i}&countryType=pt-BR" name="btnDetail">'
        f'<img src="https://img/{i}.400x225.jpg"><strong class="title"><span class="line_clamp">{t}</span></strong></a></li>'
        for i, t in posts)
    return f'<ul class="thumb_nail_list">{lis}</ul>'


def lista_pa(*posts):
    lis = "".join(
        f'<li class="board_item"><a class="board_item_inner" href="https://pa/Detail?_boardNo={i}">'
        f'<p class="title">{t}</p></a></li>' for i, t in posts)
    return f"<ul>{lis}</ul>"


def detalhe_sa(titulo, corpo, quando):
    ms = int(quando.timestamp() * 1000)
    return (f'<div class="title_area"><span class="date js-localTimezoneTooltip" data-fixedtooltip="{ms}">x</span>'
            f'<strong class="title">{titulo}</strong></div><div class="contents_area editor_area">{corpo}</div>')


def detalhe_pa(titulo, corpo, quando):
    q = quando.astimezone(timezone(timedelta(hours=8)))
    data = q.strftime("%b %d, %Y, %H:%M") + " (UTC+8)"
    return (f'<h3 class="detail_top_title">{titulo}</h3><div class="detail_top_info"><span class="info_item date">'
            f'{data}</span></div><div class="contents_area editor_area">{corpo}</div>')


class Web:
    def __init__(self, paginas):
        self.paginas = dict(paginas)
        self.pedidos = []

    def __call__(self, url):
        self.pedidos.append(url)
        return self.paginas.get(url, "")


class IA:
    def __init__(self, compara_igual=True):
        self.chamadas = []
        self.compara_igual = compara_igual

    def json(self, prompt, schema, imagens=None, temperatura=0.3):
        props = schema["properties"]
        self.chamadas.append((prompt, list(props), imagens or []))
        if "conteudo_igual" in props:
            return {"conteudo_igual": self.compara_igual,
                    "diferencas": [] if self.compara_igual else ["Só no SA: evento X"],
                    "roteiro_audio": "" if self.compara_igual else "No SA tem o evento X."}
        if "termos" in props:
            return {"termos": [{"ko": "", "en": "Pit of the Undying", "pt": "Abismo dos Imortais",
                                "tipo": "local", "evidencia": "Abismo dos Imortais"}]}
        if "fim_brasilia" in props:
            return {"titulo": "Salve o Banquete", "resumo": "r", "como_participar": ["a"], "recompensas": ["b"],
                    "periodo": "p", "fim_brasilia": "2026-11-27T05:00", "roteiro_audio": "fala do evento"}
        if "novidades" in props:
            return {"titulo": "Trajes", "novidades": ["Traje A"], "periodo": ""}
        if "itens" in props and "destaques" not in props:
            return {"itens": ["corrigido X"]}
        return {"titulo_curto": "Abismo", "destaques": ["d"], "secoes": [], "roteiro_audio": "fala do patch"}


class Audio:
    def __init__(self):
        self.textos = []

    def __call__(self, texto):
        self.textos.append(texto)
        return ("resumo.mp3", b"mp3")


class Discord:
    def __init__(self):
        self.envios = []

    def enviar(self, canal, embeds, anexo=None, texto=""):
        self.envios.append((canal, embeds, anexo))
        return 1


def montar(paginas, estado=None, ia=None, imagens=None):
    web = Web(paginas)
    bot = Bot(baixar=web, baixar_bytes=lambda url, limite=None: (imagens or {}).get(url), ia=ia or IA(),
              audio=Audio(), discord=Discord(), glossario=Glossario([Termo(en="Ranger", pt="Caçadora")]),
              itens=lambda texto, lingua: [], estado=estado if estado is not None else {}, agora=AGORA)
    return bot, web


def test_primeira_execucao_marca_tudo_como_visto_sem_postar_patches():
    url = FONTES["sa_atualizacao"].url_lista
    bot, _ = montar({url: lista_sa(("10", "Notas da Atualização – 19 de novembro"))})
    bot.rodar(["sa_atualizacao"])
    assert bot.discord.envios == []
    assert bot.estado["vistos"]["sa_atualizacao"] == ["10"]


def test_primeira_execucao_anuncia_eventos_ativos():
    url = FONTES["sa_eventos"].url_lista
    bot, _ = montar({
        url: lista_sa(("50", "Salve o Banquete")),
        "https://sa/Detail?groupContentNo=50&countryType=pt-BR": detalhe_sa("Salve o Banquete", "<p>Mate o chefe</p>", AGORA),
    })
    bot.rodar(["sa_eventos"])
    canal, embeds, anexo = bot.discord.envios[0]
    assert canal == "eventos" and anexo == ("resumo.mp3", b"mp3")
    assert "50" in bot.estado["eventos"]


def test_preview_sea_e_depois_patch_sa_igual():
    sea_url = FONTES["sea"].url_lista
    sa_url = FONTES["sa_atualizacao"].url_lista
    estado = {"vistos": {"sea": ["1"], "sa_atualizacao": ["10"]}}
    paginas = {
        sea_url: lista_pa(("2", "November 26, 2026 (Thu) Update Details"), ("1", "old")),
        "https://pa/Detail?_boardNo=2": detalhe_pa("November 26, 2026 (Thu) Update Details",
                                                   "<p>Ranger buff</p>", AGORA - timedelta(hours=7)),
        sa_url: lista_sa(("11", "Notas da Atualização – 26 de novembro"), ("10", "x")),
        "https://sa/Detail?groupContentNo=11&countryType=pt-BR": detalhe_sa(
            "Notas da Atualização – 26 de novembro", "<p>Buff da Caçadora no Abismo dos Imortais</p>", AGORA - timedelta(hours=3)),
    }
    ia = IA(compara_igual=True)
    bot, _ = montar(paginas, estado, ia)
    bot.rodar(["sea"])
    canal, embeds, anexo = bot.discord.envios[0]
    assert canal == "patch" and embeds[0]["title"].startswith("👀 Preview")
    assert anexo is not None
    # glossario relevante vai no prompt
    assert "Ranger -> Caçadora" in ia.chamadas[0][0]

    bot.rodar(["sa_atualizacao"])
    canal, embeds, anexo = bot.discord.envios[1]
    assert "igual ao preview" in embeds[0]["description"]
    assert anexo is None  # igual ao preview: sem audio
    assert [t.pt for t in bot.termos_novos] == ["Abismo dos Imortais"]


def test_patch_sa_com_diferenca_lista_diferencas_e_gera_audio():
    sa_url = FONTES["sa_atualizacao"].url_lista
    estado = {"vistos": {"sa_atualizacao": []},
              "previews": [{"id": "2", "url": "https://pa/Detail?_boardNo=2", "publicado": (AGORA - timedelta(hours=7)).isoformat()}]}
    paginas = {
        sa_url: lista_sa(("11", "Notas da Atualização – 26 de novembro")),
        "https://pa/Detail?_boardNo=2": detalhe_pa("Update", "<p>en</p>", AGORA - timedelta(hours=7)),
        "https://sa/Detail?groupContentNo=11&countryType=pt-BR": detalhe_sa("Notas da Atualização", "<p>pt</p>", AGORA),
    }
    bot, _ = montar(paginas, estado, IA(compara_igual=False))
    bot.rodar(["sa_atualizacao"])
    canal, embeds, anexo = bot.discord.envios[0]
    assert "Só no SA: evento X" in embeds[0]["description"]
    assert anexo is not None


def test_patch_sa_sem_preview_vira_resumo_completo():
    sa_url = FONTES["sa_atualizacao"].url_lista
    paginas = {
        sa_url: lista_sa(("11", "Notas da Atualização – 26 de novembro")),
        "https://sa/Detail?groupContentNo=11&countryType=pt-BR": detalhe_sa("Notas da Atualização", "<p>pt</p>", AGORA),
    }
    bot, _ = montar(paginas, {"vistos": {"sa_atualizacao": []}})
    bot.rodar(["sa_atualizacao"])
    canal, embeds, anexo = bot.discord.envios[0]
    assert embeds[0]["title"].startswith("🟢 Update SA")
    assert anexo is not None


def test_hotfix_e_loja_sem_audio():
    sa_url, loja_url = FONTES["sa_atualizacao"].url_lista, FONTES["sa_loja"].url_lista
    paginas = {
        sa_url: lista_sa(("12", "Detalhes da atualização – 27 de Novembro")),
        "https://sa/Detail?groupContentNo=12&countryType=pt-BR": detalhe_sa("Detalhes da atualização", "<p>fix</p>", AGORA),
        loja_url: lista_sa(("70", "Novos Itens da Loja de Pérolas – 26/11")),
        "https://sa/Detail?groupContentNo=70&countryType=pt-BR": detalhe_sa("Loja", "<p>traje</p>", AGORA),
    }
    bot, _ = montar(paginas, {"vistos": {"sa_atualizacao": [], "sa_loja": []}})
    bot.rodar(["sa_atualizacao", "sa_loja"])
    canais = [(c, a) for c, _, a in bot.discord.envios]
    assert ("patch", None) in canais and ("loja", None) in canais
    assert bot.audio.textos == []


def test_lembrete_de_evento_que_acaba_em_menos_de_24h_sai_uma_vez():
    fim = (AGORA + timedelta(hours=20)).isoformat()
    passado = (AGORA - timedelta(hours=1)).isoformat()
    estado = {"eventos": {"50": {"titulo": "Banquete", "url": "u", "fim": fim, "lembrado": False},
                          "51": {"titulo": "Velho", "url": "u", "fim": passado, "lembrado": False}}}
    bot, _ = montar({}, estado)
    bot.lembretes()
    bot.lembretes()
    assert len(bot.discord.envios) == 1
    assert "Banquete" in bot.discord.envios[0][1][0]["title"]
    assert "51" not in bot.estado["eventos"]


def test_evento_manda_imagens_grandes_para_a_ia():
    import struct, zlib
    ihdr = struct.pack(">IIBBBBB", 800, 800, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + ihdr + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    url = FONTES["sa_eventos"].url_lista
    corpo = '<p><img src="https://i/banner.jpg"></p><p>Local:</p><p><img src="https://i/mapa.png"></p>'
    ia = IA()
    bot, _ = montar({
        url: lista_sa(("50", "Evento")),
        "https://sa/Detail?groupContentNo=50&countryType=pt-BR": detalhe_sa("Evento", corpo, AGORA),
    }, {"vistos": {"sa_eventos": []}}, ia, imagens={"https://i/mapa.png": png})
    bot.rodar(["sa_eventos"])
    assert ia.chamadas[0][2] == [(png, "image/png")]


def test_site_em_manutencao_nao_marca_nada_e_nao_quebra():
    bot, _ = montar({}, {"vistos": {"sa_atualizacao": ["10"]}})
    bot.rodar(["sa_atualizacao"])
    assert bot.estado["vistos"]["sa_atualizacao"] == ["10"]
    assert bot.discord.envios == []


def test_falha_em_um_post_nao_marca_como_visto_e_vai_para_erros():
    class IAQuebrada(IA):
        def json(self, *a, **k):
            raise RuntimeError("cota")

    sa_url = FONTES["sa_atualizacao"].url_lista
    paginas = {
        sa_url: lista_sa(("12", "Detalhes da atualização – 27 de Novembro")),
        "https://sa/Detail?groupContentNo=12&countryType=pt-BR": detalhe_sa("Detalhes da atualização", "<p>fix</p>", AGORA),
    }
    bot, _ = montar(paginas, {"vistos": {"sa_atualizacao": []}}, IAQuebrada())
    bot.rodar(["sa_atualizacao"])
    assert "12" not in bot.estado["vistos"]["sa_atualizacao"]
    assert bot.erros and "cota" in bot.erros[0]
