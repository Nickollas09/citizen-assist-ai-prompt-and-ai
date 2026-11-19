"""Roda o agente e o juiz nas 26 mensagens do golden dataset e grava a evidência.

    python avaliacao/rodar_avaliacao.py --versao v2                 # juiz LLM se houver provedor, senão régua de regras
    python avaliacao/rodar_avaliacao.py --versao v1 --juiz regras
    python avaliacao/rodar_avaliacao.py --comparar                  # tabela antes (v1) x depois (v2)

Versões:
  v1  primeira versão do agente, congelada em `citizen_assist_v1/` (antes da análise de erros)
  v2  versão atual, em `citizen_assist/` (depois da melhoria)

Saídas em avaliacao/resultados/:  <versao>_<juiz>.csv  e  <versao>_<juiz>.md
Nenhum dado pessoal real é usado: o golden dataset só tem dados fictícios.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "avaliacao"))

from juiz import JuizLLM, julgar  # noqa: E402
from citizen_assist.protecao import mascarar  # noqa: E402

PASTA = RAIZ / "avaliacao" / "resultados"
GOLDEN = json.loads((RAIZ / "avaliacao" / "golden_dataset.json").read_text(encoding="utf-8"))
PACOTES = {"v1": "citizen_assist_v1", "v2": "citizen_assist"}


def carregar_agente(versao: str, provedor: str | None):
    pac = importlib.import_module(PACOTES[versao])
    cfg = pac.Config(provedor=provedor) if provedor else pac.Config()
    return pac.AgenteCidadao(cfg), cfg


def criar_juiz(tipo: str, cfg):
    if tipo == "regras":
        return None
    from citizen_assist.modelos import criar_modelo
    modelo = criar_modelo(cfg, "juiz")
    if modelo is None:
        if tipo == "llm":
            raise SystemExit("Juiz LLM pedido, mas nenhum provedor configurado (defina GROQ_API_KEY ou CITIZEN_LLM=ollama).")
        return None
    return JuizLLM(modelo)


def rodar(versao: str, tipo_juiz: str = "auto", provedor: str | None = None, verbose: bool = True) -> list[dict]:
    agente, cfg = carregar_agente(versao, provedor)
    juiz = criar_juiz(tipo_juiz, cfg)
    nome_juiz = "llm" if juiz else "regras"
    linhas = []
    for caso in GOLDEN:
        t0 = time.perf_counter()
        r = agente.responder(caso["mensagem"])          # cada mensagem em conversa nova
        ms = (time.perf_counter() - t0) * 1000
        j = julgar(caso, r.texto, juiz)
        linhas.append({
            # saídas (CSV, MD, notebook) nunca mostram dados pessoais, nem os fictícios do golden
            "id": caso["id"], "tipo": caso["tipo"], "mensagem": mascarar(caso["mensagem"]), "esperado": caso["esperado"],
            "resposta": mascarar(r.texto), "fontes_agente": " ".join(r.fontes), "modo_agente": r.modo,
            "nota": j["nota"], "veredito": j["veredito"], "juiz": j["origem"],
            "concorda_com_regras": j["concorda_com_regras"], "aviso": j["aviso"],
            "faltando": "; ".join(j["faltando"]), "proibidos": "; ".join(j["proibidos"]),
            "justificativa": j["criterios"].get("justificativa", ""), "ms": round(ms, 1),
        })
        if verbose:
            print(f"#{caso['id']:>2} {j['veredito']:<9} {mascarar(caso['mensagem'])[:60]}")
    salvar(versao, nome_juiz, linhas, cfg)
    return linhas


def resumo(linhas: list[dict]) -> dict:
    n = len(linhas)
    corretos = sum(l["veredito"] == "CORRETO" for l in linhas)
    por_tipo: dict[str, list[int]] = {}
    for l in linhas:
        por_tipo.setdefault(l["tipo"], [0, 0])
        por_tipo[l["tipo"]][0] += l["veredito"] == "CORRETO"
        por_tipo[l["tipo"]][1] += 1
    return {"n": n, "corretos": corretos, "acerto": corretos / n, "nota_media": sum(l["nota"] for l in linhas) / n,
            "aviso": sum(l["aviso"] for l in linhas), "por_tipo": por_tipo,
            "ms_medio": sum(l["ms"] for l in linhas) / n}


def salvar(versao: str, nome_juiz: str, linhas: list[dict], cfg):
    PASTA.mkdir(exist_ok=True)
    base = PASTA / f"{versao}_{nome_juiz}"
    with open(f"{base}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    r = resumo(linhas)
    modelo = f"{cfg.provedor}/{cfg.modelo_agente}" if cfg.usa_llm else "sem LLM (extrativo)"
    md = [f"# Golden dataset — versão {versao} — juiz: {nome_juiz}", "",
          f"Executado em {time.strftime('%d/%m/%Y %H:%M')} · agente: {modelo}"
          + (f" · juiz: {cfg.provedor}/{cfg.modelo_juiz}" if nome_juiz == "llm" else " · juiz: régua determinística"), "",
          f"**Acerto: {r['corretos']}/{r['n']} ({r['acerto']:.0%})** · nota média {r['nota_media']:.2f}/2 · "
          f"aviso presente em {r['aviso']}/{r['n']} · tempo médio {r['ms_medio']:.0f} ms", "",
          "| # | Tipo | Mensagem | Veredito | Nota | Fontes | Observação |", "|---|---|---|---|---|---|---|"]
    for l in linhas:
        obs = "; ".join(x for x in [l["faltando"] and f"faltou: {l['faltando']}", l["proibidos"] and f"proibido: {l['proibidos']}",
                                    l["justificativa"]] if x)
        md.append(f"| {l['id']} | {l['tipo']} | {l['mensagem']} | {l['veredito']} | {l['nota']} | {l['fontes_agente'] or '—'} | {obs} |")
    Path(f"{base}.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def comparar(nome_juiz: str | None = None) -> str:
    def ler(versao):
        cands = [PASTA / f"{versao}_{nome_juiz}.csv"] if nome_juiz else [PASTA / f"{versao}_llm.csv", PASTA / f"{versao}_regras.csv"]
        for c in cands:
            if c.exists():
                with open(c, encoding="utf-8") as f:
                    return c.stem.split("_", 1)[1], list(csv.DictReader(f))
        raise SystemExit(f"Rode antes: python avaliacao/rodar_avaliacao.py --versao {versao}")
    j1, a = ler("v1")
    j2, d = ler("v2")
    linhas = [f"# Antes (v1, juiz {j1}) × depois (v2, juiz {j2})", "",
              "| # | Tipo | Mensagem | v1 | v2 | Mudou |", "|---|---|---|---|---|---|"]
    for x, y in zip(a, d):
        mudou = "✅ corrigido" if x["veredito"] != "CORRETO" and y["veredito"] == "CORRETO" else (
            "❌ regrediu" if x["veredito"] == "CORRETO" and y["veredito"] != "CORRETO" else "")
        linhas.append(f"| {x['id']} | {x['tipo']} | {x['mensagem']} | {x['veredito']} | {y['veredito']} | {mudou} |")
    ca = sum(r["veredito"] == "CORRETO" for r in a)
    cd = sum(r["veredito"] == "CORRETO" for r in d)
    linhas += ["", f"**Acerto: {ca}/{len(a)} ({ca / len(a):.0%}) → {cd}/{len(d)} ({cd / len(d):.0%})**"]
    texto = "\n".join(linhas) + "\n"
    (PASTA / "comparacao_antes_depois.md").write_text(texto, encoding="utf-8")
    return texto


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--versao", choices=["v1", "v2"], default="v2")
    ap.add_argument("--juiz", choices=["auto", "llm", "regras"], default="auto")
    ap.add_argument("--provedor", choices=["groq", "ollama", "nenhum"])
    ap.add_argument("--comparar", action="store_true")
    a = ap.parse_args()
    if a.comparar:
        print(comparar())
    else:
        linhas = rodar(a.versao, a.juiz, a.provedor)
        r = resumo(linhas)
        print(f"\nAcerto {r['corretos']}/{r['n']} ({r['acerto']:.0%}) · nota média {r['nota_media']:.2f}")
