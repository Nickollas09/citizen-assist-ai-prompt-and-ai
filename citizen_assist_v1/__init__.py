"""Citizen Assist AI — VERSÃO 1 CONGELADA (antes da análise de erros do golden dataset). Não editar."""
from .agente import USANDO_LANGGRAPH, AgenteCidadao, Conversa, Resposta
from .base import BaseConhecimento
from .config import Config

__all__ = ["AgenteCidadao", "Conversa", "Resposta", "BaseConhecimento", "Config", "USANDO_LANGGRAPH"]
__version__ = "2.0.0"
