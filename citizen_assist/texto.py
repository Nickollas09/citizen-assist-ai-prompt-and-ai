"""Normalização de texto em português (minúsculas, sem acentos) e tokenização."""
import re
import unicodedata

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das", "dos",
    "e", "ou", "em", "no", "na", "nos", "nas", "para", "pra", "pro", "por", "pelo",
    "pela", "com", "sem", "que", "se", "eu", "meu", "minha", "meus", "minhas", "me",
    "mim", "voce", "vc", "ele", "ela", "isso", "esse", "essa", "este", "esta", "e",
    "ao", "aos", "qual", "quais", "como", "quando", "onde", "quanto", "quanta",
    "preciso", "posso", "pode", "quero", "gostaria", "saber", "tem", "ter", "tenho",
    "ja", "nao", "sim", "mais", "muito", "ai", "la", "aqui", "sobre", "favor", "oi",
    "ola", "bom", "dia", "boa", "tarde", "noite", "obrigado", "obrigada", "sou", "fazer",
}


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples. 'Certidão 2ª via' -> 'certidao 2a via'."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w\s/$,.\-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def tokens(texto: str, sem_stopwords: bool = True) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", normalizar(texto))
    if sem_stopwords:
        toks = [t for t in toks if t not in STOPWORDS and len(t) > 1]
    return toks


def contem(texto_norm: str, termo: str) -> bool:
    """Procura um termo (já normalizado) como palavra/expressão inteira; aceita plural simples.
    Termos terminados em '*' são tratados como prefixo (ex.: 'agend*')."""
    if termo.endswith("*"):
        padrao = r"\b" + re.escape(termo[:-1])
    else:
        padrao = r"\b" + re.escape(termo) + r"(s|es)?\b"
    return re.search(padrao, texto_norm) is not None


def contem_algum(texto_norm: str, termos) -> bool:
    return any(contem(texto_norm, t) for t in termos)
