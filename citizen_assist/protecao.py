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
    "nome": re.compile(r"\b(?:meu nome (?:e|é|eh)|me chamo|eu sou o|eu sou a)\s+[A-ZÀ-Ú][a-zà-ú]+(?:\s+(?:d[aeo]s?\s+)?[A-ZÀ-Ú][a-zà-ú]+)+"),
}

# Intenção de enviar dados ("vou te passar meu endereço"): não há dado ainda, mas é preciso orientar antes.
_INTENCAO_ENVIAR = re.compile(
    r"\b(vou|posso|quero|deixa eu|irei)\s+(te\s+|lhe\s+)?(passar|mandar|enviar|informar|dar|digitar)\b.{0,25}"
    r"\b(meu|minha|meus|minhas|o|a)\b.{0,15}\b(cpf|rg|endereco|endereço|telefone|celular|e-?mail|nome|cnh|titulo|título|"
    r"protocolo|documento|dados|senha|foto)", re.I)


def intencao_de_enviar_dados(texto: str) -> bool:
    return _INTENCAO_ENVIAR.search(texto) is not None


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
    r"\b(a partir de agora|de agora em diante)\b.{0,30}\b(voce|responda|diga|seja|aja)\b",
    r"\bvoce agora (e|sera)\b",
    r"\b(finja|fingir|faz de conta|simule|roleplay|aja como|atue como)\b",
    r"\bmodo (desenvolvedor|dev|deus|admin|livre|irrestrito)\b",
    r"\b(jailbreak|dan mode|prompt do sistema|prompt de sistema|system prompt|suas instrucoes|instrucoes internas|instrucoes ocultas)\b",
    r"\b(mostre|mostra|revele|revela|exiba|imprima|repita|copie)\b.{0,30}\b(prompt|instruc|configurac|regras internas)",
    r"\b(invente|inventa|chute|chuta)\b",
    r"\bresponda (sem|fora d)[ae]s? (fichas|regras)\b",
    r"\bdiga que\b.{0,60}\b(gratuit|gratis|nao precisa|e de graca|custa)",
    r"(^|\s)[\[<(]\s*(sistema|system|admin|administrador|developer|desenvolvedor|instrucao|instruction|assistant)\s*[\]>):]",
    r"^\s*(sistema|system|admin)\s*:",
    r"\bnova(s)? (regra|instruc|politica|diretriz)",
    r"\b(a regra|o valor|o preco|a taxa) (mudou|agora e)\b",
    r"\b(confirme|confirma) que\b",
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
    "ver minha situacao", "minha situacao", "consultar minha", "consulte minha", "verificar minha",
    "voce agendar", "voce pode agendar", "voce marcar", "agendar meu", "agendar minha", "marcar meu",
    "voce consultar", "voce verificar", "voce emitir", "pode ver meu", "pode ver minha", "ver meu cadastro",
]

_SOBRE_ASSISTENTE = [
    r"\bcanal oficial\b", r"\b(e|eh|sao) (da|do) (prefeitura|governo|central|orgao)\b",
    r"\bvoce (e|eh) (um |uma |o |a )?(robo|humano|pessoa|atendente|oficial|ia|inteligencia|chatbot|bot|confiavel|real|site oficial)",
    r"\bquem (e|eh) voce\b", r"\bo que voce (faz|sabe|consegue)\b", r"\bposso confiar\b",
    r"\b(isso|voce|essas informacoes) (e|eh|sao) (oficial|oficiais|confiave)",
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
    sobre_assistente: bool = False


def avaliar(texto: str) -> Avaliacao:
    norm = normalizar(texto)
    a = Avaliacao()
    a.dados_pessoais = detectar_dados_pessoais(texto)
    # padrões com colchetes/dois-pontos precisam do texto sem a limpeza de pontuação
    a.injecao = any(re.search(p, norm) or re.search(p, texto.lower()) for p in _INJECAO)
    a.pedido_acao = contem_algum(norm, _ACAO)
    a.sobre_assistente = any(re.search(p, norm) for p in _SOBRE_ASSISTENTE)
    palavras = norm.replace(",", " ").replace("!", " ").split()
    curto = len(palavras) <= 4
    a.saudacao = curto and contem_algum(norm, _SAUDACOES)
    a.agradecimento = curto and contem_algum(norm, _AGRADECIMENTOS)
    return a


# --- Validação de entrada ---------------------------------------------------------------------
_TECLADO = ["qwer", "wert", "erty", "rtyu", "tyui", "yuio", "uiop", "asdf", "sdfg", "dfgh", "fghj", "ghjk",
            "hjkl", "zxcv", "xcvb", "cvbn", "vbnm", "qwe", "asd", "zxc", "kkkk", "hahaha", "rsrs"]


def _parece_palavra(tok: str) -> bool:
    if any(seq in tok for seq in _TECLADO):
        return False
    vogais = sum(c in "aeiou" for c in tok)
    if len(tok) >= 4 and (vogais / len(tok) < 0.25 or re.search(r"[^aeiou]{4,}", tok)):
        return False
    return vogais > 0


def parece_sem_sentido(texto: str, vocabulario: set[str] | frozenset = frozenset()) -> bool:
    """True quando nenhuma palavra é conhecida (vocabulário das fichas) nem parece uma palavra real."""
    toks = re.findall(r"[a-z]+", normalizar(texto))
    if not toks:
        return True
    if any(t in vocabulario for t in toks):
        return False
    return not any(len(t) >= 3 and _parece_palavra(t) for t in toks)


def validar_entrada(texto: str | None, max_caracteres: int, vocabulario: set[str] | frozenset = frozenset()) -> str | None:
    """Devolve o motivo da recusa ('vazia', 'longa', 'sem_sentido') ou None se a entrada é válida."""
    t = (texto or "").strip()
    if not t:
        return "vazia"
    if len(t) > max_caracteres:
        return "longa"
    if parece_sem_sentido(t, vocabulario):
        return "sem_sentido"
    return None
