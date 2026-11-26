import base64
import json

import httpx
import pytest

from bdo_bot.discord import Discord, dividir_embeds
from bdo_bot.ia import Gemini, IAIndisponivel


def resposta_gemini(obj):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps(obj)}]}}]}


def test_gemini_envia_texto_imagens_e_schema_e_devolve_json():
    pedidos = []

    def tratar(req: httpx.Request):
        pedidos.append(req)
        return httpx.Response(200, json=resposta_gemini({"ok": True}))

    ia = Gemini("CHAVE", modelos=["m1"], http=httpx.Client(transport=httpx.MockTransport(tratar)))
    out = ia.json("oi", {"type": "OBJECT"}, imagens=[(b"\x89PNG", "image/png")])
    assert out == {"ok": True}
    corpo = json.loads(pedidos[0].content)
    assert "models/m1:generateContent" in str(pedidos[0].url)
    assert pedidos[0].headers["x-goog-api-key"] == "CHAVE"
    assert "CHAVE" not in str(pedidos[0].url)
    partes = corpo["contents"][0]["parts"]
    assert partes[0]["text"] == "oi"
    assert partes[1]["inline_data"]["data"] == base64.b64encode(b"\x89PNG").decode()
    assert corpo["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_cai_para_proximo_modelo_quando_estoura_cota():
    chamados = []

    def tratar(req):
        chamados.append(req.url.path)
        if "m1" in req.url.path:
            return httpx.Response(429, json={"error": {"message": "quota"}})
        return httpx.Response(200, json=resposta_gemini({"modelo": 2}))

    ia = Gemini("K", modelos=["m1", "m2"], http=httpx.Client(transport=httpx.MockTransport(tratar)), espera=0)
    assert ia.json("x", {}) == {"modelo": 2}
    assert any("m1" in c for c in chamados) and any("m2" in c for c in chamados)


def test_gemini_sem_modelo_disponivel_levanta_erro():
    ia = Gemini("K", modelos=["m1"], espera=0,
                http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    with pytest.raises(IAIndisponivel):
        ia.json("x", {})


def test_dividir_embeds_respeita_limites_do_discord():
    embeds = [{"title": "t", "description": "x" * 4000} for _ in range(5)]
    grupos = dividir_embeds(embeds)
    for g in grupos:
        assert len(g) <= 10
        assert sum(len(e.get("title", "")) + len(e.get("description", "")) for e in g) <= 6000
    assert sum(len(g) for g in grupos) == 5


def test_discord_posta_em_todos_os_webhooks_do_canal_com_anexo_so_na_primeira_mensagem():
    pedidos = []

    def tratar(req):
        pedidos.append(req)
        return httpx.Response(200, json={"id": str(len(pedidos)), "channel_id": "c"})

    d = Discord({"patch": ["https://discord.com/api/webhooks/1/a", "https://discord.com/api/webhooks/2/b"]},
                http=httpx.Client(transport=httpx.MockTransport(tratar)))
    embeds = [{"title": "t", "description": "x" * 4000} for _ in range(2)]
    d.enviar("patch", embeds, anexo=("resumo.mp3", b"ID3audio"))
    assert len(pedidos) == 4  # 2 mensagens x 2 webhooks
    assert all("wait=true" in str(p.url) for p in pedidos)
    com_anexo = [p for p in pedidos if b"resumo.mp3" in p.content]
    assert len(com_anexo) == 2


def test_discord_sem_webhook_configurado_nao_quebra():
    d = Discord({"patch": []}, http=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    d.enviar("patch", [{"title": "t"}])
