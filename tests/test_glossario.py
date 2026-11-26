from bdo_bot.glossario import Glossario, Termo, corpo_do_pr, itens_no_texto


def gl():
    return Glossario([
        Termo(ko="레인저", en="Ranger", pt="Caçadora", tipo="classe"),
        Termo(ko="크론석", en="Cron Stone", pt="Pedra Cron", tipo="item"),
    ])


def test_relevantes_casa_por_coreano_ou_ingles():
    g = gl()
    assert [t.pt for t in g.relevantes("레인저 스킬 변경")] == ["Caçadora"]
    assert [t.pt for t in g.relevantes("ranger and cron stone changes")] == ["Caçadora", "Pedra Cron"]
    assert g.relevantes("nada aqui") == []


def test_novos_ignora_termos_ja_conhecidos_e_vazios():
    g = gl()
    propostos = [
        {"ko": "레인저", "en": "Ranger", "pt": "Caçadora", "tipo": "classe", "evidencia": "x"},
        {"ko": "", "en": "cron stone", "pt": "Pedra Cron", "tipo": "item", "evidencia": "x"},
        {"ko": "불멸의 나락", "en": "Pit of the Undying", "pt": "Abismo dos Imortais", "tipo": "local", "evidencia": "SA 26/11"},
        {"ko": "", "en": "Foo", "pt": "", "tipo": "item", "evidencia": ""},
        {"ko": "불멸의 나락", "en": "Pit of the Undying", "pt": "Abismo dos Imortais", "tipo": "local", "evidencia": "dup"},
    ]
    novos = g.novos(propostos)
    assert [t.pt for t in novos] == ["Abismo dos Imortais"]


def test_json_ida_e_volta():
    g = gl()
    assert Glossario.de_json(g.para_json()).termos == g.termos


def test_corpo_do_pr_tem_tabela_e_links_de_conferencia():
    corpo = corpo_do_pr([Termo(ko="불멸의 나락", en="Pit of the Undying", pt="Abismo dos Imortais",
                               tipo="local", evidencia="SA 26/11")])
    assert "| 불멸의 나락 | Pit of the Undying | **Abismo dos Imortais** |" in corpo
    assert "bdocodex.com" in corpo and "bdolytics.com" in corpo


def test_itens_no_texto_usa_nomes_oficiais_por_id():
    origem = {1: "Cron Stone", 2: "Beer", 3: "Advice of Valks (+60)"}
    pt = {1: "Pedra Cron", 2: "Cerveja", 3: "Conselho de Valks (+60)"}
    achados = itens_no_texto("Get Advice of Valks (+60) and a Cron Stone", origem, pt, minimo=4)
    assert ("Advice of Valks (+60)", "Conselho de Valks (+60)") in achados
    assert ("Cron Stone", "Pedra Cron") in achados
    assert all(o != "Beer" for o, _ in achados)
