"""Configuração do agente (modelo, provedor e limites). Tudo pode vir de variáveis de ambiente.

    CITIZEN_LLM            groq | ollama | nenhum      (padrão: groq se GROQ_API_KEY existir, senão nenhum)
    CITIZEN_MODELO_AGENTE  padrão groq: llama-3.1-8b-instant   · ollama: llama3.1:8b
    CITIZEN_MODELO_JUIZ    padrão groq: llama-3.3-70b-versatile · ollama: qwen2.5:14b
    OLLAMA_BASE_URL        padrão http://localhost:11434
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

PADROES = {
    "groq": {"agente": "llama-3.1-8b-instant", "juiz": "llama-3.3-70b-versatile"},
    "ollama": {"agente": "llama3.1:8b", "juiz": "qwen2.5:14b"},
}

AVISO = ("⚠️ *Protótipo educacional: não é um canal oficial. Confirme sempre a informação no site "
         "ou no balcão do órgão responsável.*")

MAX_CARACTERES = 500


def _provedor_padrao() -> str:
    p = os.environ.get("CITIZEN_LLM")
    if p:
        return p.lower()
    return "groq" if os.environ.get("GROQ_API_KEY") else "nenhum"


@dataclass
class Config:
    provedor: str = field(default_factory=_provedor_padrao)
    modelo_agente: str | None = None
    modelo_juiz: str | None = None
    max_caracteres: int = MAX_CARACTERES

    def __post_init__(self):
        pad = PADROES.get(self.provedor, {})
        self.modelo_agente = self.modelo_agente or os.environ.get("CITIZEN_MODELO_AGENTE") or pad.get("agente")
        self.modelo_juiz = self.modelo_juiz or os.environ.get("CITIZEN_MODELO_JUIZ") or pad.get("juiz")

    @property
    def usa_llm(self) -> bool:
        return self.provedor in PADROES
