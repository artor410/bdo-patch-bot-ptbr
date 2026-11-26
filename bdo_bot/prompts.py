"""Prompts e formatos de resposta (JSON) pedidos ao Gemini."""

from __future__ import annotations

from .glossario import Termo

LIMITE_TEXTO = 120_000  # caracteres por texto enviado

REGRAS = """Você escreve para jogadores brasileiros de Black Desert Online (servidor SA).
Regras:
- Português do Brasil, frases curtas, fácil de ler em poucos segundos.
- Use SEMPRE os nomes oficiais em PT-BR do glossário abaixo para classes, itens, skills, chefes,
  regiões e sistemas. Nunca traduza literalmente um termo que está no glossário
  (ex.: "Ranger" / "레인저" é "Caçadora", não "guarda florestal").
- Se um nome próprio não está no glossário e você não tem certeza do nome oficial no SA,
  traduza e mantenha o original entre parênteses: "Abismo dos Imortais (Pit of the Undying)".
- Siglas e gírias da comunidade (AP, DP, PEN, TET, PvP, LoML...) ficam como estão.
- Não invente nada. Números, datas, horários e quantidades exatamente como no original.
- Ignore saudações, assinaturas e avisos genéricos.
"""

_ROTEIRO = ("roteiro_audio: texto para ser LIDO EM VOZ ALTA por um narrador. Sem emojis, sem markdown, "
            "sem links, sem listas com símbolos; escreva números por extenso quando ajudar a leitura. "
            "Tom de amigo contando a novidade.")


def _glossario(termos: list[Termo], itens: list[tuple[str, str]]) -> str:
    linhas = ["GLOSSÁRIO OFICIAL (original -> nome oficial no SA):"]
    for t in termos:
        origem = " / ".join(x for x in (t.ko, t.en) if x)
        nota = f"  ({t.nota})" if t.nota else ""
        linhas.append(f"- {origem} -> {t.pt}{nota}")
    if itens:
        linhas.append("ITENS CITADOS (nome original -> nome oficial do item no SA):")
        linhas += [f"- {o} -> {p}" for o, p in itens]
    if len(linhas) == 1:
        linhas.append("(vazio)")
    return "\n".join(linhas)


def _corta(texto: str) -> str:
    return texto if len(texto) <= LIMITE_TEXTO else texto[:LIMITE_TEXTO] + "\n[...texto cortado...]"


_STR = {"type": "STRING"}
_LISTA = {"type": "ARRAY", "items": _STR}

SCHEMA_PATCH = {
    "type": "OBJECT",
    "properties": {
        "titulo_curto": _STR,
        "destaques": _LISTA,
        "secoes": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {"nome": _STR, "itens": _LISTA},
                                              "required": ["nome", "itens"]}},
        "roteiro_audio": _STR,
    },
    "required": ["titulo_curto", "destaques", "secoes", "roteiro_audio"],
}


def patch(texto: str, idioma: str, contexto: str, termos: list[Termo], itens: list[tuple[str, str]]) -> str:
    return f"""{REGRAS}
{_glossario(termos, itens)}

TAREFA: o texto abaixo são as notas de atualização ({contexto}), escritas em {idioma}.
Traduza e RESUMA para português, para leitura rápida no Discord.
- titulo_curto: até 80 caracteres, o tema principal do patch.
- destaques: de 3 a 8 tópicos com o que mais importa para o jogador (até 160 caracteres cada).
- secoes: resumo por área (ex.: Eventos, Classes, Conteúdo, Itens, Sistema, Correções), só as áreas
  que existem no texto, no máximo 6 itens curtos por seção. Mudanças de classe: diga a classe e o que
  mudou em poucas palavras (ex.: "Caçadora: dano de Disparo Forte +8% no PvE").
- {_ROTEIRO} Entre 150 e 280 palavras, cobrindo os destaques.

TEXTO ORIGINAL:
{_corta(texto)}
"""


SCHEMA_EVENTO = {
    "type": "OBJECT",
    "properties": {
        "titulo": _STR,
        "resumo": _STR,
        "como_participar": _LISTA,
        "recompensas": _LISTA,
        "periodo": _STR,
        "fim_brasilia": _STR,
        "roteiro_audio": _STR,
    },
    "required": ["titulo", "resumo", "como_participar", "recompensas", "periodo", "fim_brasilia", "roteiro_audio"],
}


def evento(texto: str, termos: list[Termo], tem_imagens: bool) -> str:
    extra = ("\nAs imagens anexadas fazem parte do post (mapas, locais, passos). Use a informação delas "
             "que não estiver no texto, como o local de um NPC ou chefe.") if tem_imagens else ""
    return f"""{REGRAS}
{_glossario(termos, [])}

TAREFA: o texto abaixo é um evento do site oficial do SA (já em português). Resuma para o Discord.{extra}
- titulo: nome do evento.
- resumo: 1 ou 2 frases sobre o que é o evento.
- como_participar: passos curtos do que fazer para completar o evento.
- recompensas: as principais recompensas (com quantidades).
- periodo: o período por extenso como no post (ex.: "19/11 após a manutenção até 02/12 às 23:59").
- fim_brasilia: data e hora em que o evento TERMINA, no horário de Brasília, no formato AAAA-MM-DDTHH:MM.
  Se o post diz "antes da manutenção" de uma quinta, use 03:00 dessa quinta. Se não tem hora, use 23:59.
  Se há vários prazos, use o fim da participação no evento (não o prazo de resgate).
  Se o evento é permanente ou não tem fim, devolva "".
- {_ROTEIRO} Entre 60 e 140 palavras: o que é, o que fazer, o que ganha e até quando.

TEXTO DO EVENTO:
{_corta(texto)}
"""


SCHEMA_LOJA = {
    "type": "OBJECT",
    "properties": {"titulo": _STR, "novidades": _LISTA, "periodo": _STR},
    "required": ["titulo", "novidades", "periodo"],
}


def loja(texto: str, termos: list[Termo]) -> str:
    return f"""{REGRAS}
{_glossario(termos, [])}

TAREFA: post da Loja de Pérolas do SA. Liste só o que é NOVO (trajes, pacotes, promoções) para o Discord.
- titulo: até 80 caracteres.
- novidades: até 10 tópicos curtos com nome do item/pacote, preço em pérolas se houver e limite de compra.
- periodo: período de venda como no post, ou "" se não houver.

TEXTO:
{_corta(texto)}
"""


SCHEMA_HOTFIX = {"type": "OBJECT", "properties": {"itens": _LISTA}, "required": ["itens"]}


def hotfix(texto: str, termos: list[Termo]) -> str:
    return f"""{REGRAS}
{_glossario(termos, [])}

TAREFA: correções rápidas (hotfix) do SA. Liste em até 8 tópicos bem curtos o que mudou.

TEXTO:
{_corta(texto)}
"""


SCHEMA_COMPARA = {
    "type": "OBJECT",
    "properties": {"conteudo_igual": {"type": "BOOLEAN"}, "diferencas": _LISTA, "roteiro_audio": _STR},
    "required": ["conteudo_igual", "diferencas", "roteiro_audio"],
}


def comparar(texto_sa: str, texto_sea: str, termos: list[Termo]) -> str:
    return f"""{REGRAS}
{_glossario(termos, [])}

TAREFA: compare o CONTEÚDO do patch do SA (português) com o patch do SEA (inglês) da mesma semana.
O SEA já foi anunciado como preview. Quero saber se o SA trouxe algo diferente.
- Ignore diferenças de tradução, redação, ordem, formatação, imagens e tamanho do download.
- Ignore a nota do GM "HYPERBOOST" que o SA repete toda semana.
- É diferença real: item, evento, loja, correção ou mudança de classe que existe em um e não no outro;
  números, datas ou recompensas diferentes.
- conteudo_igual: true se não há diferença real.
- diferencas: tópicos curtos, começando com "Só no SA:" ou "Não veio para o SA:" ou "Diferente no SA:".
- {_ROTEIRO} Só se houver diferenças: até 120 palavras explicando o que muda em relação ao preview.
  Se conteudo_igual for true, devolva "".

PATCH SA:
{_corta(texto_sa)}

PATCH SEA:
{_corta(texto_sea)}
"""


SCHEMA_TERMOS = {
    "type": "OBJECT",
    "properties": {
        "termos": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
            "ko": _STR, "en": _STR, "pt": _STR, "tipo": _STR, "evidencia": _STR},
            "required": ["ko", "en", "pt", "tipo", "evidencia"]}},
    },
    "required": ["termos"],
}


def aprender_termos(texto_sa: str, texto_sea: str, texto_kr: str, conhecidos: list[Termo]) -> str:
    ja = "\n".join(f"- {t.en or t.ko}" for t in conhecidos) or "(nenhum)"
    kr = f"\nPATCH COREANO (mesmo conteúdo, pode estar algumas semanas à frente):\n{_corta(texto_kr)}\n" if texto_kr else ""
    return f"""Você está montando um glossário oficial de Black Desert Online: coreano / inglês / português (SA).
Abaixo estão as notas do MESMO patch em regiões diferentes. Alinhe os nomes próprios do jogo:
classes, skills, itens, chefes, monstros, NPCs, regiões, sistemas, modos de jogo e siglas.
Regras:
- Só inclua um termo se o nome em português aparece LITERALMENTE no patch SA e o inglês no patch SEA.
- ko: o nome em coreano se aparecer no patch coreano; senão "".
- Não inclua palavras comuns ("dano", "evento"), números, datas nem frases.
- Não inclua termos já conhecidos (lista abaixo).
- tipo: classe, skill, item, chefe, monstro, npc, local, sistema, sigla ou outro.
- evidencia: trecho curto (até 80 caracteres) do patch SA onde o termo aparece.
- No máximo 40 termos, os mais importantes primeiro.

JÁ CONHECIDOS:
{ja}

PATCH SA (português):
{_corta(texto_sa)}

PATCH SEA (inglês):
{_corta(texto_sea)}
{kr}"""
