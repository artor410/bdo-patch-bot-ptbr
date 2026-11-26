"""Glossario KR / EN / PT-BR usado nas traducoes.

- data/glossario.json: termos aprovados (classes, skills, chefes, sistemas, siglas...)
- nomes de itens: base do arsha.io (ko/en/pt por id), baixada no maximo 1x por semana
- termos novos sugeridos pela IA viram um pull request que o dono aprova
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Termo:
    ko: str = ""
    en: str = ""
    pt: str = ""
    tipo: str = ""
    nota: str = ""
    evidencia: str = field(default="", compare=False)

    def chave(self) -> str:
        """Identidade do termo: o original (coreano ou ingles), normalizado."""
        return _norm(self.ko or self.en)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@dataclass
class Glossario:
    termos: list[Termo]

    @classmethod
    def carregar(cls, caminho: Path) -> "Glossario":
        if not caminho.exists():
            return cls([])
        return cls.de_json(caminho.read_text(encoding="utf-8"))

    @classmethod
    def de_json(cls, texto: str) -> "Glossario":
        dados = json.loads(texto)
        campos = Termo.__dataclass_fields__
        return cls([Termo(**{k: v for k, v in t.items() if k in campos}) for t in dados.get("termos", [])])

    def para_json(self) -> str:
        termos = [{k: v for k, v in asdict(t).items() if v} for t in self.termos]
        return json.dumps({"termos": termos}, ensure_ascii=False, indent=2) + "\n"

    def relevantes(self, texto: str) -> list[Termo]:
        baixo = texto.lower()
        return [
            t for t in self.termos
            if (t.ko and t.ko in texto) or (t.en and _contem_palavra(baixo, t.en.lower())) or (t.pt and t.pt.lower() in baixo)
        ]

    def _chaves(self) -> set[str]:
        chaves = set()
        for t in self.termos:
            if t.ko:
                chaves.add("ko:" + _norm(t.ko))
            if t.en:
                chaves.add("en:" + _norm(t.en))
        return chaves

    def novos(self, propostos: list[dict]) -> list[Termo]:
        conhecidas = self._chaves()
        saida: list[Termo] = []
        for p in propostos:
            t = Termo(ko=(p.get("ko") or "").strip(), en=(p.get("en") or "").strip(), pt=(p.get("pt") or "").strip(),
                      tipo=(p.get("tipo") or "").strip(), evidencia=(p.get("evidencia") or "").strip())
            if not t.pt or not (t.ko or t.en):
                continue
            chaves = ({"ko:" + _norm(t.ko)} if t.ko else set()) | ({"en:" + _norm(t.en)} if t.en else set())
            if chaves & conhecidas:
                continue
            conhecidas |= chaves
            saida.append(t)
        return saida


def _contem_palavra(texto: str, termo: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(termo) + r"(?![a-z0-9])", texto) is not None


def itens_no_texto(texto: str, origem: dict[int, str], pt: dict[int, str], minimo: int = 4,
                   limite: int = 300) -> list[tuple[str, str]]:
    """Nomes de itens (na lingua do texto) que aparecem no texto, com o nome oficial em PT-BR.

    Prefere nomes mais longos ("Advice of Valks (+60)" antes de "Valks").
    """
    baixo = texto.lower()
    achados: list[tuple[str, str]] = []
    vistos: set[str] = set()
    for item_id, nome in sorted(origem.items(), key=lambda kv: -len(kv[1] or "")):
        if not nome or len(nome) < minimo or item_id not in pt or not pt[item_id]:
            continue
        chave = nome.lower()
        if chave in vistos or chave not in baixo:
            continue
        if nome.isascii() and not _contem_palavra(baixo, chave):
            continue
        vistos.add(chave)
        achados.append((nome, pt[item_id]))
        if len(achados) >= limite:
            break
    return achados


def _links(t: Termo) -> str:
    busca = t.en or t.ko
    codex = f"https://www.google.com/search?q=site%3Abdocodex.com+%22{quote_plus(busca)}%22"
    lytics = f"https://www.google.com/search?q=site%3Abdolytics.com+%22{quote_plus(busca)}%22"
    return f"[Codex]({codex}) · [BDOlytics]({lytics})"


def corpo_do_pr(novos: list[Termo]) -> str:
    linhas = [
        "Termos novos que o bot encontrou comparando patches de regiões diferentes.",
        "",
        "Confira cada linha (os links buscam o termo no Codex/BDOlytics). Para corrigir, edite",
        "`data/glossario.json` neste PR antes do merge. Para recusar tudo, feche o PR.",
        "",
        "| Coreano | Inglês | **PT-BR** | Tipo | De onde veio | Conferir |",
        "|---|---|---|---|---|---|",
    ]
    for t in novos:
        linhas.append(f"| {t.ko or '—'} | {t.en or '—'} | **{t.pt}** | {t.tipo or '—'} | {t.evidencia or '—'} | {_links(t)} |")
    return "\n".join(linhas) + "\n"
