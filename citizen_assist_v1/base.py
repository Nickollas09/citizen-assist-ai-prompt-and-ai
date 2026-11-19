"""Carrega as fichas de referência (.md) e as transforma em estruturas consultáveis.

Cada ficha vira um objeto `Ficha` com seus campos (Custo, Prazo, Documentos...) na ordem
original. Nada é reescrito: o assistente só devolve trechos literais das fichas.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .texto import normalizar

PASTA_PADRAO = Path(__file__).resolve().parent.parent / "base_conhecimento"

_RE_TITULO = re.compile(r"^#\s*(FC-\d+)\s*[—–-]\s*(.+?)\s*$")
_RE_CAMPO = re.compile(r"^\*\*(.+?):\*\*\s*(.*)$")
_RE_VERSAO = re.compile(r"vers[aã]o(?: das fichas)?:?\s*(?:de\s*)?(\d{2}/\d{2}/\d{4})", re.I)


@dataclass
class Campo:
    rotulo: str          # como aparece na ficha, ex.: "Documentos necessários para a segunda via"
    chave: str           # normalizado, ex.: "documentos necessarios para a segunda via"
    texto: str           # conteúdo literal (pode ter várias linhas/listas)


@dataclass
class Ficha:
    codigo: str
    titulo: str
    arquivo: str
    versao: str
    campos: list[Campo] = field(default_factory=list)
    palavras_chave: list[str] = field(default_factory=list)
    texto_integral: str = ""

    def campos_por_prefixo(self, prefixos) -> list[Campo]:
        achados = []
        for c in self.campos:
            if c.chave in ("palavras-chave", "fonte"):
                continue
            if any(c.chave.startswith(p) for p in prefixos) and c not in achados:
                achados.append(c)
        return achados

    def campo(self, prefixo: str) -> Campo | None:
        r = self.campos_por_prefixo([prefixo])
        return r[0] if r else None

    @property
    def fonte(self) -> str:
        return f"{self.codigo} — {self.titulo} (versão de {self.versao})"


def _parse_ficha(caminho: Path) -> Ficha | None:
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    codigo = titulo = None
    campos: list[Campo] = []
    atual: Campo | None = None
    for linha in linhas:
        m = _RE_TITULO.match(linha)
        if m and codigo is None:
            codigo, titulo = m.group(1), m.group(2)
            continue
        m = _RE_CAMPO.match(linha.strip())
        if m:
            rotulo = m.group(1).strip()
            atual = Campo(rotulo, normalizar(rotulo), m.group(2).strip())
            campos.append(atual)
            continue
        if atual is not None and linha.strip():
            atual.texto = (atual.texto + "\n" + linha.rstrip()).strip()
    if not codigo:
        return None
    texto = caminho.read_text(encoding="utf-8")
    mv = _RE_VERSAO.search(texto)
    pc = next((c for c in campos if c.chave == "palavras-chave"), None)
    palavras = [normalizar(p) for p in pc.texto.split(",")] if pc else []
    return Ficha(codigo, titulo, caminho.name, mv.group(1) if mv else "?", campos, palavras, texto)


class BaseConhecimento:
    def __init__(self, pasta: Path | str = PASTA_PADRAO):
        self.pasta = Path(pasta)
        self.fichas: dict[str, Ficha] = {}
        for arq in sorted(self.pasta.glob("FC-*.md")):
            f = _parse_ficha(arq)
            if f:
                self.fichas[f.codigo] = f
        if not self.fichas:
            raise FileNotFoundError(f"Nenhuma ficha FC-*.md encontrada em {self.pasta}")
        leia = self.pasta / "00_LEIA-ME.md"
        mv = _RE_VERSAO.search(leia.read_text(encoding="utf-8")) if leia.exists() else None
        self.versao = mv.group(1) if mv else next(iter(self.fichas.values())).versao

    def __getitem__(self, codigo: str) -> Ficha:
        return self.fichas[codigo]

    def __iter__(self):
        return iter(self.fichas.values())

    def corpus_numerico(self) -> str:
        """Todo o texto das fichas, usado para checar se números citados existem na fonte."""
        return "\n".join(f.texto_integral for f in self)
