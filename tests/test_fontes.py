from datetime import datetime, timezone

import pytest

from bdo_bot.fontes import FONTES, Tipo, classificar, fontes_para_checar


@pytest.mark.parametrize(
    "fonte,titulo,esperado",
    [
        ("sa_atualizacao", "Notas da Atualização – 19 de novembro de 2026 (qui.)", Tipo.PATCH_SA),
        ("sa_atualizacao", "Detalhes da atualização – 20 de Novembro de 2026", Tipo.HOTFIX_SA),
        ("sa_atualizacao", "[Black Desert+] Novidades no app", None),
        ("sa_atualizacao", "[Módulo de segurança] Atualização", None),
        ("sa_eventos", "Passe Especial da Solare", Tipo.EVENTO_SA),
        ("sa_loja", "Novos Itens da Loja de Pérolas – 19/11 (qui.)", Tipo.LOJA_SA),
        ("sa_loja", "Novo Traje: Algo Bonito", Tipo.LOJA_SA),
        ("sea", "November 26, 2026 (Thu) Update Details", Tipo.PREVIEW_SEA),
        ("sea", "[Hotfix] November 6, 2026 (Fri) Update Details", None),
        ("sea", "Pearl Shop Update", None),
        ("globallab", "11월 20일(금) 업데이트 안내", Tipo.GLOBAL_LAB),
        ("globallab", "보안 모듈 업데이트 안내", None),
    ],
)
def test_classificar(fonte, titulo, esperado):
    assert classificar(fonte, titulo) == esperado


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def test_checagem_de_hora_cheia_olha_todas_as_fontes():
    assert set(fontes_para_checar(utc(2026, 11, 24, 15, 0), meia_hora=False)) == set(FONTES)


def test_checagem_de_meia_hora_so_olha_fontes_na_janela():
    # quinta 06:30 UTC: janela do SA (pos-manutencao)
    q = fontes_para_checar(utc(2026, 11, 26, 6, 30), meia_hora=True)
    assert "sa_atualizacao" in q and "sa_eventos" in q and "sa_loja" in q
    assert "globallab" not in q
    # quinta 02:30 UTC: janela do SEA
    assert fontes_para_checar(utc(2026, 11, 26, 2, 30), meia_hora=True) == ["sea"]
    # sexta 09:30 UTC: janela do Global Lab
    assert "globallab" in fontes_para_checar(utc(2026, 11, 27, 9, 30), meia_hora=True)
    # terca 15:30 UTC: nenhuma janela
    assert fontes_para_checar(utc(2026, 11, 24, 15, 30), meia_hora=True) == []
