"""Interface web local (biblioteca padrão do Python).

    python app_web.py                 -> http://localhost:8000
    python app_web.py --porta 9000

Endpoints:  GET /  ·  GET /api/menu  ·  POST /api/perguntar {"pergunta": "...", "contexto": ["FC-06"]}

Privacidade: o servidor NÃO guarda perguntas, respostas, IPs nem sessões. O único "histórico" é
a lista de códigos de ficha da última resposta, que fica no navegador e volta em cada pedido.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from citizen_assist import USANDO_LANGGRAPH, AgenteCidadao
from citizen_assist import menu as menu_mod

PAGINA = Path(__file__).resolve().parent / "web" / "index.html"
CODIGOS = {f"FC-0{i}" for i in range(1, 8)}


def criar_handler(agente: AgenteCidadao):
    class Handler(BaseHTTPRequestHandler):
        def _enviar(self, corpo: bytes, tipo: str, status=200):
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def _json(self, dados, status=200):
            self._enviar(json.dumps(dados, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._enviar(PAGINA.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/api/menu":
                self._json({"versao": agente.base.versao, "categorias": menu_mod.como_dict(),
                            "llm": agente.modelo is not None, "langgraph": USANDO_LANGGRAPH})
            else:
                self._json({"erro": "não encontrado"}, 404)

        def do_POST(self):
            if self.path != "/api/perguntar":
                return self._json({"erro": "não encontrado"}, 404)
            try:
                tamanho = min(int(self.headers.get("Content-Length", 0)), 20_000)
                dados = json.loads(self.rfile.read(tamanho) or b"{}")
            except (ValueError, json.JSONDecodeError):
                dados = {}
            pergunta = str(dados.get("pergunta", ""))[:5000]   # o agente responde "longa demais" acima do limite
            contexto = [c for c in dados.get("contexto", []) if c in CODIGOS][:3]
            try:
                r = agente.responder(pergunta, contexto)
                self._json(r.to_dict())
            except Exception:  # nunca mostrar erro técnico ao cidadão
                self._json({"texto": "Desculpe, tive um problema para responder agora. Tente de novo em instantes "
                                     "ou escolha um tema no menu.", "tipo": "erro", "fontes": [], "alertas": [], "fichas": []})

        def log_message(self, *a):  # sem log de acesso: ele registraria o conteúdo e o IP
            pass

    return Handler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--porta", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    agente = AgenteCidadao()
    srv = ThreadingHTTPServer((a.host, a.porta), criar_handler(agente))
    llm = f"{agente.cfg.provedor}/{agente.cfg.modelo_agente}" if agente.modelo else "sem LLM (modo extrativo)"
    print(f"Citizen Assist AI em http://{a.host}:{a.porta}  · {llm} · LangGraph: {'sim' if USANDO_LANGGRAPH else 'substituto local'}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
