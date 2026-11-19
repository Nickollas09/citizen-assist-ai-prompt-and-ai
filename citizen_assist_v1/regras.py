"""Regras determinísticas que aplicam as fichas ao caso concreto da pessoa.

Ex.: "tenho 17 anos, sou obrigado a votar?" -> FC-03 diz que de 16 a 17 anos o voto é facultativo.
Cada conclusão cita a ficha usada. Quando a ficha não cobre o caso (lacuna), o assistente
diz isso em vez de deduzir uma regra que não existe.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .texto import contem_algum

_NUM_EXTENSO = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "quinze": 15,
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
}
_NUM = r"(\d{1,4}|" + "|".join(_NUM_EXTENSO) + r")"


def _n(v: str) -> int:
    return int(v) if v.isdigit() else _NUM_EXTENSO[v]


@dataclass
class Conclusao:
    texto: str
    fontes: list[str]


def extrair_idade(norm: str) -> int | None:
    padroes = [
        r"\b(?:tenho|tem|tera|terei|completei|completou|faco)\s+" + _NUM + r"\s+anos",
        r"\b(?:de|com)\s+" + _NUM + r"\s+anos(?!\s+(?:de\s+)?(?:vencid|atras|que))",
        r"\b" + _NUM + r"\s+anos\s+de\s+idade",
        r"\bidade\s*(?:de|:)?\s*" + _NUM + r"\b",
    ]
    for p in padroes:
        m = re.search(p, norm)
        if m:
            # ignora "vencida há 6 anos" / "faz 6 anos que venceu"
            depois = norm[m.end(): m.end() + 25]
            if re.match(r"\s*(que\s+)?(venc|expir)", depois):
                continue
            return _n(m.group(1))
    return None


def _para_dias(qtd: int, unidade: str) -> int:
    if unidade.startswith("dia"):
        return qtd
    if unidade.startswith("semana"):
        return qtd * 7
    if unidade.startswith("mes"):
        return qtd * 30
    return qtd * 365


_UNID = r"(dias?|semanas?|mes|meses|anos?)"


def extrair_vencida_ha(norm: str) -> int | None:
    """Dias desde o vencimento: 'vencida há 40 dias', 'venceu faz 2 meses', 'faz 6 anos que venceu'."""
    padroes = [
        r"(?:vencid[ao]s?|venceu|expirad[ao]|expirou)\s+(?:ha|faz|a|tem|desde)?\s*(?:mais de\s+|uns?\s+|umas?\s+|quase\s+)?" + _NUM + r"\s+" + _UNID,
        r"(?:ha|faz)\s+(?:mais de\s+|uns?\s+|umas?\s+|quase\s+)?" + _NUM + r"\s+" + _UNID + r"\s+(?:que\s+)?(?:esta\s+)?(?:venc|expir)",
        _NUM + r"\s+" + _UNID + r"\s+(?:de\s+)?(?:vencid|atrasad)",
    ]
    for p in padroes:
        m = re.search(p, norm)
        if m:
            return _para_dias(_n(m.group(1)), m.group(2))
    return None


def extrair_vence_em(norm: str) -> int | None:
    m = re.search(r"vence\s+(?:em|daqui a|daqui|dentro de)\s+" + _NUM + r"\s+" + _UNID, norm) or \
        re.search(r"(?:faltam|falta)\s+" + _NUM + r"\s+" + _UNID + r"\s+para\s+(?:a\s+)?(?:minha\s+)?(?:cnh\s+)?venc", norm)
    return _para_dias(_n(m.group(1)), m.group(2)) if m else None


def extrair_dias_para_eleicao(norm: str) -> int | None:
    m = re.search(r"(?:faltam|falta|faltando)\s+" + _NUM + r"\s+" + _UNID + r"\s+(?:para|pra)\s+(?:a\s+)?(?:proxima\s+)?eleica", norm) or \
        re.search(_NUM + r"\s+" + _UNID + r"\s+antes\s+da\s+(?:proxima\s+)?eleica", norm)
    return _para_dias(_n(m.group(1)), m.group(2)) if m else None


def aplicar(norm: str, fichas: list[str], gerais: list[str]) -> list[Conclusao]:
    out: list[Conclusao] = []
    idade = extrair_idade(norm)

    # --- Título de eleitor: obrigatoriedade do voto (FC-03)
    if idade is not None and "FC-03" in fichas:
        if 18 <= idade <= 69:
            out.append(Conclusao(f"Com {idade} anos, o voto é **obrigatório** (a FC-03 diz: obrigatório de 18 a 69 anos).", ["FC-03"]))
        elif idade in (16, 17):
            out.append(Conclusao(f"Com {idade} anos, o voto é **facultativo**: você pode tirar o título e votar, mas não é obrigado (FC-03).", ["FC-03"]))
        elif idade > 70:
            out.append(Conclusao(f"Com {idade} anos, o voto é **facultativo** (FC-03: facultativo para maiores de 70 anos).", ["FC-03"]))
        elif idade == 70:
            out.append(Conclusao("A FC-03 diz que o voto é obrigatório até 69 anos e facultativo para *maiores de 70*; "
                                 "ela não deixa claro o caso de quem tem exatamente 70 anos. Confirme na Central Eleitoral de Aurora.", ["FC-03"]))
        else:
            out.append(Conclusao(f"A FC-03 só trata do voto a partir dos 16 anos; ela não traz regra para quem tem {idade} anos. "
                                 "Confirme na Central Eleitoral de Aurora.", ["FC-03"]))

    # --- Título: fechamento do cadastro (FC-03)
    dias_eleicao = extrair_dias_para_eleicao(norm)
    if dias_eleicao is not None:
        if dias_eleicao < 150:
            out.append(Conclusao(f"Faltando {dias_eleicao} dias, o cadastro eleitoral **já está fechado** (fecha 150 dias antes da eleição). "
                                 "Um pedido feito agora só vale para a eleição seguinte (FC-03).", ["FC-03"]))
        elif dias_eleicao == 150:
            out.append(Conclusao("O cadastro fecha exatamente 150 dias antes da eleição (FC-03). Como você está no limite, "
                                 "procure a Central Eleitoral hoje mesmo para confirmar se o pedido ainda vale.", ["FC-03"]))
        else:
            out.append(Conclusao(f"Faltando {dias_eleicao} dias, o cadastro ainda está aberto: ele só fecha 150 dias antes da eleição (FC-03).", ["FC-03"]))

    # --- CNH: validade conforme idade e situação de vencimento (FC-06)
    if "FC-06" in fichas:
        if idade is not None and (contem_algum(norm, ["validade", "vale por", "valida", "quanto tempo", "dura", "renov*"])):
            anos = 10 if idade <= 49 else 5 if idade <= 69 else 3
            out.append(Conclusao(f"Com {idade} anos, a CNH renovada terá validade de **{anos} anos** (FC-06).", ["FC-06"]))
        venc = extrair_vencida_ha(norm)
        if venc is not None:
            if venc > 5 * 365:
                out.append(Conclusao("CNH vencida há **mais de 5 anos**: além da renovação, é preciso **refazer o curso e a prova**. "
                                     "Até concluir, não é permitido dirigir (FC-06).", ["FC-06"]))
            elif venc > 30:
                out.append(Conclusao(f"Vencida há cerca de {venc} dias, ou seja, **mais de 30 dias**: você **não pode dirigir** até concluir a renovação (FC-06).", ["FC-06"]))
            else:
                out.append(Conclusao(f"Vencida há {venc} dias: a FC-06 só proíbe dirigir quando a CNH está vencida há **mais de 30 dias**. "
                                     "Faça a renovação logo para não passar desse limite.", ["FC-06"]))
        vence = extrair_vence_em(norm)
        if vence is not None:
            if vence <= 30:
                out.append(Conclusao(f"Faltando {vence} dias para vencer, você **já pode renovar** (a renovação é permitida a partir de 30 dias antes do vencimento — FC-06).", ["FC-06"]))
            else:
                out.append(Conclusao(f"Faltando {vence} dias para vencer, **ainda não dá para renovar**: a renovação abre 30 dias antes do vencimento (FC-06).", ["FC-06"]))

    # --- RG: perda x roubo/furto (FC-01)
    if "FC-01" in fichas:
        roubo = contem_algum(norm, ["roubad*", "roubaram", "roubo", "furt*", "assalt*", "levaram"])
        perda = contem_algum(norm, ["perdi", "perda", "perdeu", "perdido", "perdida", "extravi*", "sumiu"])
        if roubo:
            out.append(Conclusao("Em caso de **roubo ou furto**, a segunda via do RG exige **boletim de ocorrência** (FC-01 e FC-07).", ["FC-01", "FC-07"]))
        elif perda:
            out.append(Conclusao("Em caso de **perda**, o boletim de ocorrência **não é exigido**: basta assinar a **declaração de extravio** no próprio balcão (FC-01).", ["FC-01"]))

    # --- Certidões: isenção só no balcão (FC-05)
    if "FC-05" in fichas and contem_algum(norm, ["baixa renda", "isencao", "isento", "isenta", "gratis", "gratuit*", "de graca"]):
        if contem_algum(norm, ["portal", "internet", "online", "pdf", "site"]):
            out.append(Conclusao("A FC-05 prevê isenção apenas para quem **comprovar baixa renda no balcão**. Para o pedido pelo portal "
                                 "(R$ 49,00), a ficha não prevê isenção.", ["FC-05"]))
        else:
            out.append(Conclusao("Quem comprovar baixa renda **no balcão** do Cartório Central fica isento da taxa da certidão (FC-05).", ["FC-05"]))

    # --- Menores de idade (FC-01, FC-02, FC-04, FC-07)
    if idade is not None and idade < 12 and ({"FC-01", "FC-02"} & set(fichas)):
        fs = sorted({"FC-01", "FC-02"} & set(fichas))
        out.append(Conclusao("Para menores de 12 anos, o **responsável legal** acompanha a criança no atendimento, levando "
                             f"documento original com foto ({' e '.join(fs)}; FC-07).", fs + ["FC-07"]))
    if idade is not None and idade < 18 and "FC-04" in fichas:
        out.append(Conclusao("Menores de 18 anos tiram a Carteira de Trabalho **acompanhados de um responsável legal** (FC-04).", ["FC-04"]))

    # --- Atendimento prioritário (FC-07)
    if idade is not None and idade >= 60:
        out.append(Conclusao(f"Com {idade} anos, há direito a **atendimento prioritário** (vale para pessoas com 60 anos ou mais — FC-07).", ["FC-07"]))
    return out
