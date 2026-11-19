"""Recuperação e composição de respostas a partir das fichas (parte determinística do agente).

Não usa IA: identifica documento e intenção, aplica as regras ao caso e monta a resposta
com trechos literais das fichas, sempre com a ficha de origem e a data de verificação.
"""
from __future__ import annotations

import re

from . import regras
from .base import BaseConhecimento, Campo, Ficha
from .busca import (INTENCOES, INTENCOES_GERAIS, RESUMO_PADRAO, TERMOS_DOCUMENTO, BuscaRelevancia,
                    Consulta, analisar)
from .texto import contem_algum, normalizar, tokens

NOMES_CURTOS = {
    "FC-01": "RG (Carteira de Identidade)",
    "FC-02": "CPF",
    "FC-03": "Título de eleitor",
    "FC-04": "Carteira de Trabalho",
    "FC-05": "Certidões (nascimento, casamento e óbito)",
    "FC-06": "CNH (renovação)",
    "FC-07": "Regras gerais de atendimento",
}

ROTULO_INTENCAO = {
    "custo": "custo", "prazo": "prazo", "documentos": "documentos necessários",
    "agendamento": "agendamento", "passo": "passo a passo", "onde": "local de atendimento",
    "quem": "quem pode pedir", "validade": "validade", "vencimento": "regras de vencimento",
    "isencao": "isenção de taxa", "perda": "o que fazer em caso de perda",
}

GENERICO = "__generico__"

TIPOS = ("resposta", "esclarecimento", "sem_informacao", "recusa", "saudacao", "alerta_privacidade")


def _formatar_campo(campo: Campo) -> str:
    if "\n" in campo.texto or not campo.texto:
        return f"**{campo.rotulo}:**\n{campo.texto}"
    return f"**{campo.rotulo}:** {campo.texto}"


class Recuperador:
    def __init__(self, base: BaseConhecimento | None = None):
        self.base = base or BaseConhecimento()
        self.busca = BuscaRelevancia(self.base)
        self._termos_doc = {t for ts in TERMOS_DOCUMENTO.values() for termo in ts for t in tokens(termo)}

    def menu(self, abertura: str = "Posso ajudar com:") -> str:
        return self._menu(abertura)

    # ------------------------------------------------------------------ núcleo
    PRECISA_LLM = "precisa_llm"

    def decidir(self, c: Consulta, permitir_llm: bool = False):
        """Casos que se resolvem sem recuperar trechos (fora do escopo, ambiguidade, sem informação).
        Devolve None quando a consulta deve seguir para a recuperação, ou PRECISA_LLM quando
        nem as regras nem a busca identificaram o documento e há um LLM para classificar."""
        if c.fora_escopo and not c.fichas:
            termo = c.fora_escopo[0]
            return (f"Não encontrei informações sobre **{termo}** nas fichas da Central do Cidadão de Aurora, "
                    "então não vou arriscar uma resposta. Consulte o órgão competente.\n\n"
                    + self._menu("Posso ajudar com:"), "sem_informacao", [])

        if c.ambiguidade and not c.fichas:
            opcoes = "\n".join(f"- {NOMES_CURTOS[f]}" for f in c.ambiguidade)
            return (f"Para te responder certo, de qual documento você está falando?\n{opcoes}", "esclarecimento", [])

        if not c.fichas and not c.gerais:
            if c.intencoes:
                return (self._menu("De qual documento você está falando?"), "esclarecimento", [])
            achados = self.busca.buscar(c.texto, minimo=4.0, k=2)
            if not achados:
                return self.PRECISA_LLM if permitir_llm else self.sem_informacao()
            fichas_achadas = list(dict.fromkeys(f.codigo for _, f, _ in achados))
            c.fichas = [f for f in fichas_achadas if f != "FC-07"]
            if "FC-07" in fichas_achadas and not c.fichas:
                blocos = [self._bloco(self.base["FC-07"], [cp for _, f, cp in achados if f.codigo == "FC-07"])]
                return ("\n\n".join(blocos), "resposta", ["FC-07"])
        return None

    def sem_informacao(self) -> tuple[str, str, list[str]]:
        return ("Não encontrei essa informação nas fichas da Central do Cidadão de Aurora, então não vou arriscar uma resposta. "
                "Para outros assuntos, consulte o órgão competente.\n\n" + self._menu("Posso ajudar com:"), "sem_informacao", [])

    def compor(self, c: Consulta) -> tuple[str, str, list[str]]:
        fontes: list[str] = []
        partes: list[str] = []

        # 3. Regras aplicadas ao caso
        conclusoes = regras.aplicar(c.norm, c.fichas, c.gerais)
        if conclusoes:
            partes.append("**Para o seu caso:**\n" + "\n".join(f"- {k.texto}" for k in conclusoes))
            for k in conclusoes:
                fontes += [f for f in k.fontes if f not in fontes]

        # 4. Trechos das fichas de documento
        for codigo in c.fichas[:3]:
            ficha = self.base[codigo]
            campos, faltando = self._campos_para(ficha, c)
            if not campos and not faltando:
                continue
            bloco = self._bloco(ficha, campos)
            if GENERICO in faltando:
                bloco = (f"_Não encontrei na ficha {codigo} uma resposta específica para essa pergunta. "
                         "Abaixo estão as informações principais; o que não estiver aqui, confirme no balcão._\n\n" + bloco)
                faltando.remove(GENERICO)
            if faltando:
                bloco += "\n\n_" + "; ".join(
                    f"A ficha {codigo} não informa {ROTULO_INTENCAO.get(i, i)}" for i in faltando) + "._"
            partes.append(bloco)
            fontes.append(codigo)

        # Regras gerais (FC-07)
        campos_gerais = self._campos_gerais(c)
        if campos_gerais:
            partes.append(self._bloco(self.base["FC-07"], campos_gerais, titulo="Regras gerais de atendimento"))
            if "FC-07" not in fontes:
                fontes.append("FC-07")

        # Detalhes que as fichas não trazem
        if contem_algum(c.norm, ["endereco", "telefone", "site", "link", "email", "e-mail", "whatsapp da", "rua do", "cep"]) \
                and not contem_algum(c.norm, ["comprovante de residencia", "comprovante de endereco"]):
            partes.append("_As fichas não trazem endereço, telefone ou link dos locais de atendimento; essa informação eu não tenho._")

        return ("\n\n".join(partes), "resposta", fontes)

    def _campos_para(self, ficha: Ficha, c: Consulta) -> tuple[list[Campo], list[str]]:
        campos: list[Campo] = []
        faltando: list[str] = []
        for intencao in c.intencoes:
            _, prefixos = INTENCOES[intencao]
            achados = ficha.campos_por_prefixo(prefixos)
            if intencao == "perda" and ficha.codigo != "FC-01":
                achados = [a for a in achados if "perd" in a.texto.lower()]
            if intencao == "quem" and not achados:
                achados = [cp for cp in ficha.campos if cp.chave not in ("palavras-chave", "fonte")
                           and contem_algum(normalizar(cp.texto), ["menor*", "responsavel legal"])]
            if not achados and intencao in ("onde", "validade", "isencao", "vencimento", "quem"):
                # tenta um campo relacionado por relevância antes de declarar lacuna
                rel = self.busca.buscar(c.texto, fichas=[ficha.codigo], ignorar=self._termos_doc, k=1, minimo=2.0)
                achados = [r[2] for r in rel]
                if intencao in ("onde", "validade", "isencao") or not achados:
                    faltando.append(intencao)
            if intencao == "prazo" and not any(re.search(r"\d+ dias uteis", normalizar(a.texto)) for a in achados):
                # prazo de entrega às vezes aparece só no passo a passo (ex.: título de eleitor)
                achados += [cp for cp in ficha.campos if cp not in achados and cp.chave != "fonte"
                            and re.search(r"\d+ dias uteis", normalizar(cp.texto))]
            for a in achados:
                if a not in campos:
                    campos.append(a)
        if not campos and not faltando:
            if c.gerais:   # pergunta é sobre regra geral aplicada a um documento (ex.: horário do RG)
                return [], []
            rel = self.busca.buscar(c.texto, fichas=[ficha.codigo], ignorar=self._termos_doc, k=2, minimo=2.5)
            campos = [r[2] for r in rel]
        if not campos:
            campos = ficha.campos_por_prefixo(RESUMO_PADRAO)
            restantes = [t for t in tokens(c.texto) if t not in self._termos_doc and len(t) > 2]
            if restantes and not c.intencoes:
                faltando.append(GENERICO)
        # mantém a ordem original da ficha
        ordem = {id(cp): i for i, cp in enumerate(ficha.campos)}
        return sorted(campos, key=lambda cp: ordem[id(cp)]), [f for f in faltando if f]

    def _campos_gerais(self, c: Consulta) -> list[Campo]:
        fc07 = self.base.fichas.get("FC-07")
        if not fc07:
            return []
        nomes = list(c.gerais)
        if "documentos" in c.intencoes and "copia" not in nomes:
            nomes.append("copia")
        if "custo" in c.intencoes and c.fichas and "pagamento" not in nomes and contem_algum(c.norm, ["pag*"]):
            nomes.append("pagamento")
        campos = []
        for nome in nomes:
            _, prefixo = INTENCOES_GERAIS[nome]
            cp = fc07.campo(prefixo)
            if cp and cp not in campos:
                campos.append(cp)
        return campos

    def _bloco(self, ficha: Ficha, campos: list[Campo], titulo: str | None = None) -> str:
        cab = f"### {titulo or ficha.titulo} ({ficha.codigo})"
        corpo = "\n\n".join(_formatar_campo(cp) for cp in campos)
        return f"{cab}\n{corpo}\n\n_Fonte: {ficha.codigo}, verificada em {ficha.versao}._"

    def _menu(self, abertura: str) -> str:
        itens = "\n".join(f"- {n}" for n in NOMES_CURTOS.values())
        return f"{abertura}\n{itens}\n\nPergunte, por exemplo: *quanto custa a segunda via do RG?* ou *preciso agendar para renovar a CNH?*"
