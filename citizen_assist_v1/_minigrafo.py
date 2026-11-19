"""Substituto mínimo da API do LangGraph, usado SOMENTE quando `langgraph` não está instalado.

O agente é escrito contra a API real (`StateGraph`, `START`, `END`, `add_node`, `add_edge`,
`add_conditional_edges`, `compile().invoke()`, `get_graph().draw_mermaid()`). Com
`pip install -r requirements.txt` o LangGraph de verdade é usado automaticamente; este
arquivo existe para que os testes rodem em ambientes sem acesso à internet.
"""
from __future__ import annotations

START = "__start__"
END = "__end__"


class _Desenho:
    def __init__(self, nos, arestas, condicionais):
        self.nos, self.arestas, self.condicionais = nos, arestas, condicionais

    def draw_mermaid(self) -> str:
        linhas = ["graph TD;", f"\t{START}([<p>__start__</p>]):::first"]
        linhas += [f"\t{n}({n})" for n in self.nos]
        linhas.append(f"\t{END}([<p>__end__</p>]):::last")
        for a, b in self.arestas:
            linhas.append(f"\t{a} --> {b};")
        for origem, (_, mapa) in self.condicionais.items():
            for rotulo, destino in mapa.items():
                linhas.append(f"\t{origem} -. &nbsp;{rotulo}&nbsp; .-> {destino};")
        return "\n".join(linhas)


class _Compilado:
    def __init__(self, g: "StateGraph"):
        self.g = g

    def invoke(self, estado: dict, config=None) -> dict:
        estado = dict(estado)
        atual = self.g.arestas[START]
        passos = 0
        while atual != END:
            passos += 1
            if passos > 50:
                raise RuntimeError("ciclo no grafo")
            atualizacao = self.g.nos[atual](estado) or {}
            estado.update(atualizacao)
            if atual in self.g.condicionais:
                roteador, mapa = self.g.condicionais[atual]
                atual = mapa[roteador(estado)]
            else:
                atual = self.g.arestas[atual]
        return estado

    def get_graph(self):
        return _Desenho(list(self.g.nos), [(a, b) for a, b in self.g.arestas.items()], self.g.condicionais)


class StateGraph:
    def __init__(self, schema=None):
        self.nos, self.arestas, self.condicionais = {}, {}, {}

    def add_node(self, nome, fn):
        self.nos[nome] = fn

    def add_edge(self, origem, destino):
        self.arestas[origem] = destino

    def add_conditional_edges(self, origem, roteador, mapa):
        self.condicionais[origem] = (roteador, dict(mapa))

    def compile(self):
        return _Compilado(self)
