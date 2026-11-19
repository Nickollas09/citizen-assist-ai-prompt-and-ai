"""Agente Citizen Assist AI construído com LangGraph.

Grafo (um único agente; cada nó é uma etapa com responsabilidade única):

  validar_entrada ─┬─(inválida)──────────────────────────────────────────────┐
                   └─► proteger_dados ─► detectar_manipulacao ─┬─(manipulação)─► responder_manipulacao ─┤
                                                               └─► rotear ─┬─(direto)──────────────────┤
                                                                           ├─(llm)─► classificar_llm ─┐ │
                                                                           └─► recuperar ◄────────────┘ │
                                                                                 ├─(llm)─► redigir_llm ─► verificar ─┤
                                                                                 └────────────────────────────────────► finalizar

IA (LLM) só em classificar_llm e redigir_llm. Todo o resto é algoritmo: validação,
regex de dados pessoais, detecção de manipulação, busca nas fichas, regras de caso e verificação.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, TypedDict

from . import protecao
from .base import BaseConhecimento
from .busca import analisar
from .config import AVISO, Config
from .modelos import classificar, criar_modelo, redigir
from .recuperacao import Recuperador
from .verificacao import verificar

try:  # LangGraph de verdade (pip install -r requirements.txt)
    from langgraph.graph import END, START, StateGraph
    USANDO_LANGGRAPH = True
except ImportError:  # ambiente sem internet: substituto com a mesma API
    from ._minigrafo import END, START, StateGraph
    USANDO_LANGGRAPH = False


class Estado(TypedDict, total=False):
    entrada: str | None          # texto bruto: só existe até o nó proteger_dados
    mensagem: str                # texto com dados pessoais mascarados
    contexto: list[str]          # fichas da pergunta anterior (sem texto do usuário)
    motivo_invalida: str | None
    alertas: list[str]
    prefixos: list[str]
    manipulacao: bool
    consulta: Any
    rota: str
    corpo: str
    tipo: str
    fontes: list[str]
    fichas: list[str]
    modo: str
    saudacao: bool
    agradecimento: bool
    rascunho_llm: str | None
    texto: str


@dataclass
class Resposta:
    texto: str
    tipo: str = "resposta"
    fontes: list[str] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    fichas: list[str] = field(default_factory=list)
    modo: str = "extrativo"

    def to_dict(self):
        return asdict(self)


EXEMPLOS = "Exemplos: *Quanto custa a segunda via do RG?* · *Preciso agendar para renovar a CNH?*"

MSG_INVALIDA = {
    "vazia": "Você não escreveu nada. Escolha um tema no menu ou digite sua dúvida.",
    "longa": "Sua mensagem ficou longa demais. Escreva a dúvida em uma ou duas frases curtas, por favor.",
    "sem_sentido": "Não entendi sua mensagem. Pode escrever de outro jeito?",
}


class AgenteCidadao:
    def __init__(self, cfg: Config | None = None, base: BaseConhecimento | None = None, modelo=None):
        self.cfg = cfg or Config()
        self.base = base or BaseConhecimento()
        self.rec = Recuperador(self.base)
        if modelo is None and self.cfg.usa_llm:
            modelo = criar_modelo(self.cfg, "agente")
        self.modelo = modelo
        self.grafo = self._montar_grafo()

    # ------------------------------------------------------------------ nós
    def _validar_entrada(self, s: Estado) -> Estado:
        return {"motivo_invalida": protecao.validar_entrada(s.get("entrada"), self.cfg.max_caracteres),
                "alertas": [], "prefixos": [], "fontes": [], "modo": "extrativo"}

    def _proteger_dados(self, s: Estado) -> Estado:
        bruto = s["entrada"].strip()
        achados = protecao.detectar_dados_pessoais(bruto)
        alertas, prefixos = list(s["alertas"]), list(s["prefixos"])
        if achados:
            alertas.append("dados_pessoais")
            prefixos.append(
                f"🔒 **Proteja seus dados:** sua mensagem parece ter dados pessoais ({', '.join(achados)}). "
                "Não envie esse tipo de informação por chat. Eu não guardei nem usei esses dados. "
                "A Central do Cidadão não pede dados pessoais por chat ou mensagem (FC-07).")
        # daqui em diante só circula o texto mascarado; o bruto é descartado do estado
        return {"entrada": None, "mensagem": protecao.mascarar(bruto), "alertas": alertas, "prefixos": prefixos,
                "fontes": ["FC-07"] if achados else []}

    def _detectar_manipulacao(self, s: Estado) -> Estado:
        av = protecao.avaliar(s["mensagem"])
        alertas, prefixos = list(s["alertas"]), list(s["prefixos"])
        if av.pedido_acao:
            alertas.append("pedido_de_acao")
            prefixos.append("ℹ️ Eu não acesso cadastros nem faço consultas, agendamentos ou emissões. "
                            "Isso é feito por você no portal da Central do Cidadão ou no balcão. Veja como:")
        return {"manipulacao": av.injecao, "alertas": alertas, "prefixos": prefixos,
                "saudacao": av.saudacao, "agradecimento": av.agradecimento}

    def _responder_manipulacao(self, s: Estado) -> Estado:
        return {"tipo": "recusa", "alertas": s["alertas"] + ["tentativa_de_manipulacao"],
                "corpo": "Não posso fazer isso. Eu só respondo com base nas fichas da Central do Cidadão de Aurora "
                         "e não mudo, ignoro nem invento regras.\n\nPosso ajudar com custo, prazo, documentos ou "
                         "agendamento de RG, CPF, título de eleitor, carteira de trabalho, certidões e CNH."}

    def _rotear(self, s: Estado) -> Estado:
        c = analisar(s["mensagem"], s.get("contexto") or None)
        if (s.get("saudacao") or s.get("agradecimento")) and not (c.fichas or c.intencoes or c.gerais):
            corpo = ("De nada! Se tiver outra dúvida, é só perguntar." if s.get("agradecimento")
                     else self.rec.menu("Olá! Eu tiro dúvidas sobre documentos. Escolha um tema ou escreva sua pergunta:"))
            return {"consulta": c, "rota": "direto", "tipo": "saudacao", "corpo": corpo}
        decisao = self.rec.decidir(c, permitir_llm=self.modelo is not None)
        if decisao == Recuperador.PRECISA_LLM:
            return {"consulta": c, "rota": "llm"}
        if decisao is not None:
            corpo, tipo, fontes = decisao
            return {"consulta": c, "rota": "direto", "corpo": corpo, "tipo": tipo, "fontes": s["fontes"] + fontes}
        return {"consulta": c, "rota": "recuperar"}

    def _classificar_llm(self, s: Estado) -> Estado:
        c = s["consulta"]
        try:
            c.fichas = classificar(self.modelo, s["mensagem"])
        except Exception:
            c.fichas = []
        return {"consulta": c, "alertas": s["alertas"] + (["classificado_por_llm"] if c.fichas else [])}

    def _recuperar(self, s: Estado) -> Estado:
        c = s["consulta"]
        if not c.fichas and not c.gerais:
            corpo, tipo, fontes = self.rec.sem_informacao()
        else:
            corpo, tipo, fontes = self.rec.compor(c)
        return {"corpo": corpo, "tipo": tipo, "fontes": list(dict.fromkeys(s["fontes"] + fontes)),
                "fichas": c.fichas}

    def _redigir_llm(self, s: Estado) -> Estado:
        try:
            texto = redigir(self.modelo, s["mensagem"], s["corpo"])
        except Exception as e:  # rede, chave, limite de uso: segue com a resposta extrativa
            return {"rascunho_llm": None, "alertas": s["alertas"] + [f"llm_indisponivel:{type(e).__name__}"]}
        return {"rascunho_llm": texto}

    def _verificar(self, s: Estado) -> Estado:
        texto = s.get("rascunho_llm")
        if not texto:
            return {"modo": "extrativo"}   # LangGraph: todo nó devolve ao menos uma chave
        problemas = verificar(texto, self.base, s["fontes"])
        if problemas:
            return {"alertas": s["alertas"] + ["llm_rejeitado:" + "; ".join(problemas)]}
        rodape = ", ".join(f"{f} (verificada em {self.base[f].versao})" for f in s["fontes"] if f in self.base.fichas)
        return {"corpo": f"{texto}\n\n_Fontes: {rodape}._", "modo": "generativo"}

    def _finalizar(self, s: Estado) -> Estado:
        if s.get("motivo_invalida"):
            corpo = (f"{MSG_INVALIDA[s['motivo_invalida']]}\n\n" + self.rec.menu("Posso ajudar com:"))
            return {"tipo": "entrada_invalida", "corpo": corpo, "texto": f"{corpo}\n\n{AVISO}"}
        prefixos = s.get("prefixos", [])
        corpo, tipo = s.get("corpo", ""), s.get("tipo", "resposta")
        if prefixos and tipo in ("sem_informacao", "esclarecimento"):
            corpo = "Como posso ajudar? Pergunte sobre custo, prazo, documentos ou agendamento de um documento."
            tipo = "alerta_privacidade" if "dados_pessoais" in s["alertas"] else tipo
        texto = "\n\n".join(p for p in prefixos + [corpo, AVISO] if p)
        return {"tipo": tipo, "texto": texto}

    # ------------------------------------------------------------------ grafo
    def _montar_grafo(self):
        g = StateGraph(Estado)
        for nome in ("validar_entrada", "proteger_dados", "detectar_manipulacao", "responder_manipulacao",
                     "rotear", "classificar_llm", "recuperar", "redigir_llm", "verificar", "finalizar"):
            g.add_node(nome, getattr(self, "_" + nome))
        g.add_edge(START, "validar_entrada")
        g.add_conditional_edges("validar_entrada", lambda s: "invalida" if s.get("motivo_invalida") else "ok",
                                {"invalida": "finalizar", "ok": "proteger_dados"})
        g.add_edge("proteger_dados", "detectar_manipulacao")
        g.add_conditional_edges("detectar_manipulacao", lambda s: "manipulacao" if s.get("manipulacao") else "ok",
                                {"manipulacao": "responder_manipulacao", "ok": "rotear"})
        g.add_edge("responder_manipulacao", "finalizar")
        g.add_conditional_edges("rotear", lambda s: s["rota"],
                                {"direto": "finalizar", "llm": "classificar_llm", "recuperar": "recuperar"})
        g.add_edge("classificar_llm", "recuperar")
        g.add_conditional_edges("recuperar", self._precisa_redigir, {"llm": "redigir_llm", "ok": "finalizar"})
        g.add_edge("redigir_llm", "verificar")
        g.add_edge("verificar", "finalizar")
        g.add_edge("finalizar", END)
        return g.compile()

    def _precisa_redigir(self, s: Estado) -> str:
        return "llm" if self.modelo is not None and s.get("tipo") == "resposta" and not s.get("alertas") else "ok"

    # ------------------------------------------------------------------ API
    def responder(self, pergunta: str, contexto: list[str] | None = None) -> Resposta:
        s = self.grafo.invoke({"entrada": pergunta, "contexto": contexto or []})
        return Resposta(s["texto"], s.get("tipo", "resposta"), list(dict.fromkeys(s.get("fontes", []))),
                        s.get("alertas", []), s.get("fichas", []), s.get("modo", "extrativo"))

    def nova_conversa(self) -> "Conversa":
        return Conversa(self)

    def mermaid(self) -> str:
        return self.grafo.get_graph().draw_mermaid()


class Conversa:
    """Guarda só os códigos das fichas da última resposta (para "e quanto custa?").
    Nenhum texto do usuário é armazenado."""

    def __init__(self, agente: AgenteCidadao):
        self.agente = agente
        self.contexto: list[str] = []

    def perguntar(self, texto: str) -> Resposta:
        r = self.agente.responder(texto, self.contexto)
        if r.fichas:
            self.contexto = r.fichas
        return r
