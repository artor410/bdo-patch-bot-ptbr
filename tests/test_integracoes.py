import base64
import json

import httpx

from bdo_bot.github_pr import abrir_pr_glossario
from bdo_bot.glossario import Glossario, Termo
from bdo_bot.integracoes import ItensArsha, deve_avisar


def test_pr_do_glossario_cria_branch_arquivo_e_pr_a_partir_do_main_atual():
    atual = Glossario([Termo(en="Ranger", pt="Caçadora")]).para_json()
    pedidos = []

    def tratar(req: httpx.Request):
        pedidos.append((req.method, req.url.path, json.loads(req.content) if req.content else None))
        p = req.url.path
        if p.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "abc"}})
        if p.endswith("/git/refs"):
            return httpx.Response(201, json={})
        if p.endswith("/contents/data/glossario.json") and req.method == "GET":
            return httpx.Response(200, json={"sha": "f1", "content": base64.b64encode(atual.encode()).decode()})
        if p.endswith("/contents/data/glossario.json") and req.method == "PUT":
            return httpx.Response(200, json={})
        if p.endswith("/pulls"):
            return httpx.Response(201, json={"html_url": "https://github.com/o/r/pull/1"})
        return httpx.Response(404)

    url = abrir_pr_glossario([Termo(en="Pit of the Undying", pt="Abismo dos Imortais", evidencia="x")],
                             repo="o/r", token="T", sufixo="2026-11-26",
                             http=httpx.Client(transport=httpx.MockTransport(tratar)))
    assert url == "https://github.com/o/r/pull/1"
    put = next(c for m, pth, c in pedidos if m == "PUT")
    novo = Glossario.de_json(base64.b64decode(put["content"]).decode())
    assert [t.pt for t in novo.termos] == ["Caçadora", "Abismo dos Imortais"]
    assert put["branch"] == "glossario-2026-11-26" and put["sha"] == "f1"
    pr = next(c for m, pth, c in pedidos if pth.endswith("/pulls"))
    assert pr["base"] == "main" and "Abismo dos Imortais" in pr["body"]


def test_itens_arsha_cruza_por_id_e_respeita_tamanho_minimo(tmp_path):
    for lingua, nomes in {"en": {1: "Cron Stone", 2: "Beer"}, "kr": {1: "크론석", 2: "맥주"},
                          "pt": {1: "Pedra Cron", 2: "Cerveja"}}.items():
        (tmp_path / f"{lingua}.json").write_text(
            json.dumps([{"id": i, "name": n, "grade": 0} for i, n in nomes.items()]), encoding="utf-8")
    itens = ItensArsha(tmp_path, baixar=lambda url: None, agora=None)
    assert itens("buy a Cron Stone", "en") == [("Cron Stone", "Pedra Cron")]
    assert itens("크론석 획득", "ko") == [("크론석", "Pedra Cron")]
    assert itens("맥주", "ko") == []  # nome curto demais: muito falso positivo


def test_itens_arsha_sem_base_devolve_vazio(tmp_path):
    itens = ItensArsha(tmp_path, baixar=lambda url: None, agora=None)
    assert itens("Cron Stone", "en") == []


def test_aviso_de_erro_repetido_so_sai_de_novo_depois_de_6h():
    from datetime import datetime, timedelta, timezone
    agora = datetime(2026, 11, 26, 12, tzinfo=timezone.utc)
    estado = {}
    assert deve_avisar(estado, "sea: timeout", agora)
    assert not deve_avisar(estado, "sea: timeout", agora + timedelta(hours=1))
    assert deve_avisar(estado, "sea: timeout", agora + timedelta(hours=7))
    assert deve_avisar(estado, "outro erro", agora + timedelta(hours=1))
