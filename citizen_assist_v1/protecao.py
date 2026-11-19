"""Camada de proteção (guardrails): dados pessoais, tentativas de manipulação e pedidos
que o assistente não pode atender (consultar cadastro, agendar, emitir documento).

Roda ANTES de qualquer busca ou modelo de linguagem.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .texto import contem_algum, normalizar

# --- Dados pessoais (LGPD) ---------------------------------------------------------------
PADROES_DADOS = {
    "CPF": re.compile(r"\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-.\s]?\d{2}\b"),
    "e-mail": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"),
    "telefone": re.compile(r"(?:\(?\b\d{2}\)?[\s-]?)?\b9?\d{4}[\s-]\d{4}\b"),
    "CEP": re.compile(r"\b\d{5}-\d{3}\b"),
    "número de documento": re.compile(r"\b\d{7,}\b|\b\d{1,2}\.\d{3}\.\d{3}-?[\dxX]\b"),
    "endereço": re.compile(r"\b(?:rua|r\.|avenida|av\.|travessa|alameda|estrada|rodovia|pra[cç]a)\s+[A-Za-zÀ-ú .]{2,40},?\s*(?:n[ºo°.]?\s*)?\d{1,5}\b", re.I),
    "senha": re.compile(r"\bsenha\b[^.?!\n]{0,25}?(?:\s(?:e|é|eh)\s|:)\s*\S{3,}", re.I),
    "cartão": re.compile(r"\b(?:\d{4}[\s-]?){3}\d{4}\b"),
}


def detectar_dados_pessoais(texto: str) -> list[str]:
    achados = []
    for nome, padrao in PADROES_DADOS.items():
        if padrao.search(texto):
            achados.append(nome)
    # um CPF também casa com "número de documento"; não repetir
    if "CPF" in achados and "número de documento" in achados:
        achados.remove("número de documento")
    if "cartão" in achados and "número de documento" in achados:
        achados.remove("número de documento")
    return achados


def mascarar(texto: str) -> str:
    """Substitui dados pessoais por marcadores. Roda antes de qualquer outro processamento:
    o restante do agente (inclusive o LLM) só recebe o texto mascarado."""
    for nome, padrao in PADROES_DADOS.items():
        texto = padrao.sub(f"[{nome.upper()} OMITIDO]", texto)
    return texto


# --- Manipulação / injeção de instruções -----------------------------------------------------
_INJECAO = [
    r"\b(ignore|ignora|esqueca|esquece|desconsidere|desconsidera|desobedeca)\b.{0,40}\b(instruc|regra|orienta|anterior|fichas|prompt|sistema)",
    r"\bvoce (agora )?(e|sera) (um|uma|o|a)\b",
    r"\b(finja|fingir|faz de conta|simule|roleplay)\b",
    r"\bmodo (desenvolvedor|dev|deus|admin|livre|irrestrito)\b",
    r"\b(jailbreak|dan mode|prompt do sistema|system prompt|suas instrucoes)\b",
    r"\b(invente|inventa|chute|chuta)\b",
    r"\bresponda (sem|fora d)[ae]s? (fichas|regras)\b",
    r"\bdiga que\b.{0,60}\b(gratuit|gratis|nao precisa|e de graca|custa)",
]

# --- Pedidos de ação que o assistente não executa --------------------------------------------
_ACAO = [
    "agende para mim", "agenda para mim", "pode agendar", "marque para mim", "marca pra mim",
    "faz o agendamento", "faca o agendamento", "consulte meu", "consulta meu", "consultar meu",
    "verifique meu", "verifica meu", "verificar meu", "meu cpf esta regular", "situacao do meu",
    "status do meu", "meu protocolo", "andamento do meu pedido", "emita", "emitir para mim",
    "gere a guia", "gera a guia", "gerar a guia para mim", "cancele meu", "cancelar meu agendamento",
    "acessar minha conta", "minha conta no portal", "esta regular", "ta regular", "esta ativo",
    "esta cancelado", "ja esta pronto", "ja esta pronta", "ficou pronto", "ficou pronta", "foi aprovado",
]

_SAUDACOES = ["oi", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "hello", "opa", "tudo bem"]
_AGRADECIMENTOS = ["obrigado", "obrigada", "valeu", "agradeco", "brigado", "muito obrigado"]


@dataclass
class Avaliacao:
    dados_pessoais: list[str] = field(default_factory=list)
    injecao: bool = False
    pedido_acao: bool = False
    saudacao: bool = False
    agradecimento: bool = False


def avaliar(texto: str) -> Avaliacao:
    norm = normalizar(texto)
    a = Avaliacao()
    a.dados_pessoais = detectar_dados_pessoais(texto)
    a.injecao = any(re.search(p, norm) for p in _INJECAO)
    a.pedido_acao = contem_algum(norm, _ACAO)
    palavras = norm.replace(",", " ").replace("!", " ").split()
    curto = len(palavras) <= 4
    a.saudacao = curto and contem_algum(norm, _SAUDACOES)
    a.agradecimento = curto and contem_algum(norm, _AGRADECIMENTOS)
    return a


# --- Validação de entrada ---------------------------------------------------------------------
def validar_entrada(texto: str | None, max_caracteres: int) -> str | None:
    """Devolve o motivo da recusa ('vazia', 'longa', 'sem_sentido') ou None se a entrada é válida."""
    t = (texto or "").strip()
    if not t:
        return "vazia"
    if len(t) > max_caracteres:
        return "longa"
    if not re.search(r"[A-Za-zÀ-ú]{2,}", t):
        return "sem_sentido"
    return None
