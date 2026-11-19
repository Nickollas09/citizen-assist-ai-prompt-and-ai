"""Verificador de fundamentação: confere se um texto gerado por LLM só usa fatos das fichas.

Regras (algoritmo, sem IA):
  * todo valor em R$ precisa existir nas fichas citadas na resposta-base;
  * todo prazo "N dias/horas/anos" precisa existir nas fichas citadas;
  * só pode citar fichas que existem e que estavam na resposta-base;
  * precisa citar pelo menos uma ficha.
"""
from __future__ import annotations

import re

from .base import BaseConhecimento
from .texto import normalizar

_RE_VALOR = re.compile(r"R\$\s?\d{1,3}(?:\.\d{3})*(?:,\d{2})?")
_RE_PRAZO = re.compile(r"\b(\d{1,3})\s+(dias?|anos?|horas?|meses)\b", re.I)
_RE_FICHA = re.compile(r"FC-\d{2}")


def verificar(texto: str, base: BaseConhecimento, fontes_permitidas: list[str]) -> list[str]:
    fontes = [f for f in fontes_permitidas if f in base.fichas] or list(base.fichas)
    corpus = "\n".join(base[f].texto_integral for f in fontes)
    corpus_sem_espaco = corpus.replace(" ", "")
    corpus_norm = normalizar(corpus)
    problemas = []
    for v in _RE_VALOR.findall(texto):
        if v.replace(" ", "") not in corpus_sem_espaco:
            problemas.append(f"valor fora das fichas: {v}")
    for n, unidade in _RE_PRAZO.findall(texto):
        if not re.search(rf"\b{n}\s+{normalizar(unidade)[:3]}", corpus_norm):
            problemas.append(f"prazo fora das fichas: {n} {unidade}")
    citadas = set(_RE_FICHA.findall(texto))
    for f in citadas - set(fontes):
        problemas.append(f"ficha não usada na base citada: {f}")
    if not citadas:
        problemas.append("sem citação de ficha")
    return problemas
