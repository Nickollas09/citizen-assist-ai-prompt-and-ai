"""Recuperação: descobre de qual documento a pessoa fala (ficha) e o que ela quer saber (intenção).

Estratégia em duas camadas, ambas explicáveis:
1. Regras de vocabulário: termos específicos de cada documento e gatilhos de intenção.
2. Busca por relevância (TF-IDF) sobre os campos das fichas, usada quando nenhuma
   intenção explícita é reconhecida.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field

from .base import BaseConhecimento, Campo, Ficha
from .texto import contem, contem_algum, normalizar, tokens

# Termos que identificam cada documento com segurança.
TERMOS_DOCUMENTO = {
    "FC-01": ["rg", "identidade", "carteira de identidade", "registro geral", "posto de identificacao"],
    "FC-02": ["cpf", "cadastro de pessoa fisica", "cadastro de pessoas fisicas"],
    "FC-03": ["titulo", "eleitor", "eleitoral", "votar", "voto", "eleicao", "zona eleitoral"],
    "FC-04": ["carteira de trabalho", "ctps", "primeiro emprego", "carteira profissional", "emprego"],
    "FC-05": ["certidao", "certidoes", "obito", "cartorio", "certidao de nascimento",
              "certidao de casamento", "registro de nascimento"],
    "FC-06": ["cnh", "habilitacao", "carteira de motorista", "motorista", "dirigir", "exame medico",
              "renovar", "renovacao", "carta de motorista", "clinica credenciada"],
}

# Termos que mencionam um documento de forma ambígua.
AMBIGUOS = {
    "carteira": ["FC-01", "FC-04", "FC-06"],
    "segunda via": ["FC-01", "FC-03", "FC-05"],
    "2a via": ["FC-01", "FC-03", "FC-05"],
}

# Documentos que não estão nas fichas (para responder "não sei" com clareza).
FORA_DO_ESCOPO = [
    "passaporte", "reservista", "certificado de reservista", "cartao sus", "sus", "nis", "pis",
    "pasep", "bolsa familia", "iptu", "ipva", "multa", "multas", "licenciamento", "rne", "crnm",
    "fgts", "seguro desemprego", "aposentadoria", "inss", "mei", "cnpj", "alvara", "imposto de renda",
    "carteira de estudante", "porte de arma", "visto", "cartao de vacina", "vacina",
]

# intenção -> (gatilhos, prefixos de campo nas fichas de documento)
INTENCOES = {
    "custo": (["quanto custa", "custa", "custo", "preco", "valor", "taxa", "pagar", "paga", "pago",
               "gratis", "gratuit*", "de graca", "cobra*", "dinheiro", "reais", "corrigir", "correcao"],
              ["custo", "isencao"]),
    "prazo": (["prazo", "quanto tempo", "demora*", "fica pronto", "fica pronta", "quando fica",
               "dias uteis", "quando sai", "leva quanto", "em quantos dias", "rapido", "retirar",
               "retiro", "recebo", "receber", "disponivel"],
              ["prazo", "custo e prazo"]),
    "documentos": (["documentos necessarios", "quais documentos", "que documentos", "o que levar",
                    "preciso levar", "devo levar", "tenho que levar", "levar o que", "o que precisa",
                    "o que eu preciso", "o que preciso", "documentos para", "documentacao",
                    "comprovante de residencia", "comprovante de endereco", "boletim de ocorrencia", "bo"],
                   ["documentos necessarios"]),
    "agendamento": (["agend*", "marcar", "hora marcada", "sem marcar"], ["agendamento"]),
    "passo": (["como faco", "como fazer", "como tiro", "como tirar", "como pedir", "como peco",
               "como solicit*", "passo a passo", "como funciona", "como renovo", "como renovar",
               "procedimento", "etapas", "como emitir", "como emito", "como consigo", "como obter",
               "pelo portal", "pela internet", "online", "aplicativo", "app", "celular", "corrigir", "correcao"],
              ["passo a passo", "onde"]),
    "onde": (["onde", "local", "qual o endereco", "qual endereco", "endereco do", "endereco da", "lugar", "qual posto"], ["onde"]),
    "quem": (["quem pode", "quem deve", "menor", "crianca", "filho", "filha", "bebe", "idade",
              "obrigatori*", "facultativ*", "responsavel", "sou obrigad*"],
             ["quem pode pedir", "quem deve ter"]),
    "validade": (["validade", "vale por", "valida por", "dura quanto", "quanto tempo vale",
                  "por quanto tempo"], ["validade"]),
    "vencimento": (["vencid*", "venceu", "vence", "vencimento", "quando renovar", "quando posso renovar",
                    "antes de vencer", "posso dirigir"], ["quando renovar"]),
    "isencao": (["baixa renda", "isencao", "isento", "isenta", "nao posso pagar", "sem dinheiro",
                 "sem condicoes de pagar"], ["isencao", "custo"]),
    "perda": (["perdi", "perda", "perdeu", "extravi*", "roubad*", "roubaram", "roubo", "furt*",
               "assalt*", "levaram"], ["documentos necessarios"]),
}

# intenções respondidas pela ficha de regras gerais (FC-07): intenção -> (gatilhos, prefixo do campo)
INTENCOES_GERAIS = {
    "horario": (["horario", "que horas", "abre", "fecha", "sabado", "domingo", "feriado",
                 "fim de semana", "final de semana", "aberto"], "horario"),
    "terceiros": (["procuracao", "outra pessoa", "terceiro*", "por mim", "no meu lugar", "buscar para",
                   "representar", "pedir para", "tirar para", "para minha mae", "para meu pai",
                   "para o meu pai", "para a minha mae", "para outra"], "atendimento por terceiros"),
    "pagamento": (["pix", "boleto", "guia", "banco", "cartao de credito", "cartao de debito",
                   "como pago", "forma de pagamento", "formas de pagamento", "pagamento", "compensa*"],
                  "pagamento"),
    "prioritario": (["prioridade", "prioritari*", "idoso", "idosa", "gestante", "gravida",
                     "deficien*", "libras", "surdo", "surda", "cadeirante", "acessib*", "preferencial",
                     "interprete"], "atendimento prioritario"),
    "copia": (["xerox", "copia", "copias", "fotocopia", "autenticad*", "original"], "documentos"),
    "perda": (["perdi", "perda", "extravi*", "roubad*", "roubaram", "roubo", "furt*", "assalt*"],
              "perda, roubo ou furto"),
    "privacidade": (["golpe", "mensagem pedindo", "pediram minha senha", "pediram meu", "pedindo meus dados",
                     "pede senha", "privacidade", "dados pessoais", "whatsapp", "seguro passar"],
                    "privacidade"),
    "agendamento_geral": (["agend*"], "agendamento"),
}

RESUMO_PADRAO = ["custo", "prazo", "agendamento", "documentos necessarios"]


@dataclass
class Consulta:
    texto: str
    norm: str
    fichas: list[str] = field(default_factory=list)       # fichas de documento identificadas
    ambiguidade: list[str] = field(default_factory=list)  # candidatas quando o termo é ambíguo
    intencoes: list[str] = field(default_factory=list)
    gerais: list[str] = field(default_factory=list)
    fora_escopo: list[str] = field(default_factory=list)


def analisar(texto: str, contexto_fichas: list[str] | None = None) -> Consulta:
    norm = normalizar(texto)
    c = Consulta(texto, norm)

    for codigo, termos in TERMOS_DOCUMENTO.items():
        if contem_algum(norm, termos):
            c.fichas.append(codigo)

    # 'certidão de nascimento' como documento exigido para RG/CPF não é pedido de certidão.
    if "FC-05" in c.fichas and len(c.fichas) > 1 and not contem_algum(
        norm, ["certidoes", "pedir certidao", "tirar certidao", "segunda via da certidao",
               "emitir certidao", "certidao de obito", "obito", "cartorio"]):
        c.fichas.remove("FC-05")
    # 'renovar' só indica CNH se nenhum outro documento for citado.
    if "FC-06" in c.fichas and len(c.fichas) > 1 and not contem_algum(
        norm, [t for t in TERMOS_DOCUMENTO["FC-06"] if t not in ("renovar", "renovacao")]):
        c.fichas.remove("FC-06")

    if not c.fichas:
        for termo, candidatas in AMBIGUOS.items():
            if contem(norm, termo):
                c.ambiguidade = candidatas
                break
        c.fora_escopo = [t for t in FORA_DO_ESCOPO if contem(norm, t)]
        if not c.fora_escopo and not c.ambiguidade and contexto_fichas:
            c.fichas = list(contexto_fichas)   # pergunta de continuação ("e quanto custa?")

    for nome, (gatilhos, _) in INTENCOES.items():
        if contem_algum(norm, gatilhos):
            c.intencoes.append(nome)
    for nome, (gatilhos, _) in INTENCOES_GERAIS.items():
        if contem_algum(norm, gatilhos):
            c.gerais.append(nome)
    # agendamento geral só quando não há documento específico
    if c.fichas and "agendamento_geral" in c.gerais:
        c.gerais.remove("agendamento_geral")
    # "documento original/cópia" é regra geral; não confundir com lista de documentos
    return c


class BuscaRelevancia:
    """TF-IDF simples sobre os campos das fichas (cada campo é um 'documento' de busca)."""

    def __init__(self, base: BaseConhecimento):
        self.itens: list[tuple[Ficha, Campo, Counter]] = []
        df: Counter = Counter()
        for ficha in base:
            for campo in ficha.campos:
                if campo.chave in ("palavras-chave", "fonte"):
                    continue
                tf = Counter(tokens(campo.rotulo + " " + campo.texto))
                self.itens.append((ficha, campo, tf))
                df.update(set(tf))
        n = len(self.itens)
        self.idf = {t: math.log((n + 1) / (d + 0.5)) for t, d in df.items()}

    def buscar(self, texto: str, fichas: list[str] | None = None, ignorar: set[str] | None = None,
               k: int = 3, minimo: float = 1.5):
        q = [t for t in tokens(texto) if not ignorar or t not in ignorar]
        resultados = []
        for ficha, campo, tf in self.itens:
            if fichas and ficha.codigo not in fichas:
                continue
            total = sum(tf.values()) or 1
            s = sum(self.idf.get(t, 0) * (1 + math.log(tf[t])) for t in q if tf.get(t))
            s = s / math.sqrt(total) * 3 if s else 0
            if s >= minimo:
                resultados.append((s, ficha, campo))
        resultados.sort(key=lambda r: -r[0])
        return resultados[:k]
