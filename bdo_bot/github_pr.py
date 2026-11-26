"""Abre um pull request com termos novos para o dono aprovar (API REST do GitHub)."""

from __future__ import annotations

import base64

import httpx

from .glossario import Glossario, Termo, corpo_do_pr

ARQUIVO = "data/glossario.json"


def abrir_pr_glossario(novos: list[Termo], repo: str, token: str, sufixo: str,
                       http: httpx.Client | None = None) -> str:
    http = http or httpx.Client(timeout=60)
    api = f"https://api.github.com/repos/{repo}"
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    def ok(r: httpx.Response) -> httpx.Response:
        if r.status_code >= 400:
            raise RuntimeError(f"GitHub {r.request.method} {r.request.url.path}: {r.status_code} {r.text[:300]}")
        return r

    arquivo = ok(http.get(f"{api}/contents/{ARQUIVO}", headers=h, params={"ref": "main"})).json()
    atual = Glossario.de_json(base64.b64decode(arquivo["content"]).decode("utf-8"))
    novos = atual.novos([t.__dict__ for t in novos])  # alguem pode ter aprovado termos nesse meio tempo
    if not novos:
        return ""
    atual.termos.extend(novos)

    sha_main = ok(http.get(f"{api}/git/ref/heads/main", headers=h)).json()["object"]["sha"]
    branch = f"glossario-{sufixo}"
    ok(http.post(f"{api}/git/refs", headers=h, json={"ref": f"refs/heads/{branch}", "sha": sha_main}))
    ok(http.put(f"{api}/contents/{ARQUIVO}", headers=h, json={
        "message": f"glossário: {len(novos)} termo(s) novo(s) para revisar",
        "content": base64.b64encode(atual.para_json().encode("utf-8")).decode(),
        "sha": arquivo["sha"],
        "branch": branch,
    }))
    pr = ok(http.post(f"{api}/pulls", headers=h, json={
        "title": f"Glossário: {len(novos)} termo(s) novo(s) para revisar",
        "head": branch,
        "base": "main",
        "body": corpo_do_pr(novos),
    })).json()
    return pr["html_url"]
