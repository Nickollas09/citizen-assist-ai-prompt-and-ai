"""Calcula os indicadores do teste com usuários a partir das planilhas anonimizadas.

    python testes_usuarios/calcular_indicadores.py
Lê registro_tempos.csv e questionario_respostas.csv e grava resultado_indicadores.md.
"""
import csv
import re
import statistics
from pathlib import Path

PASTA = Path(__file__).resolve().parent
PERGUNTAS = {
    "q1": "Foi fácil encontrar a informação",
    "q2": "Linguagem clara",
    "q3": "Confiança pela fonte citada",
    "q4": "Usou sem ajuda",
    "q5": "Usaria de novo",
}


def ler(nome):
    with open(PASTA / nome, encoding="utf-8") as f:
        return [l for l in csv.DictReader(f) if any((v or "").strip() for v in l.values())]


def main():
    tempos, quest = ler("registro_tempos.csv"), ler("questionario_respostas.csv")
    for l in tempos + quest:  # garante que só há códigos anônimos
        if not re.fullmatch(r"P\d+", l["participante"].strip()):
            raise SystemExit(f"Use apenas códigos P1, P2... (encontrado: {l['participante']!r}). Não registre nomes.")
    if not tempos or not quest:
        print("Planilhas vazias: aplique o protocolo (protocolo.md) e preencha os CSVs antes de rodar.")
        return
    participantes = sorted({l["participante"] for l in tempos}, key=lambda p: int(p[1:]))
    md = ["# Resultado do teste com usuários", "",
          f"Participantes: **{len(participantes)}** (anônimos: {', '.join(participantes)})", ""]
    if len(participantes) < 5:
        md += [f"> ⚠️ O enunciado pede pelo menos 5 pessoas; há {len(participantes)}.", ""]

    md += ["## Tempo para encontrar a informação", "",
           "| Tarefa | Tempo médio (s) | Mediana (s) | Mín–máx (s) | Concluíram |", "|---|---|---|---|---|"]
    for t in sorted({l["tarefa"] for l in tempos}):
        ls = [l for l in tempos if l["tarefa"] == t]
        ts = [float(l["tempo_segundos"]) for l in ls]
        ok = sum(l["concluiu"].strip().lower() in ("sim", "s", "1", "true") for l in ls)
        md.append(f"| {t} | {statistics.mean(ts):.0f} | {statistics.median(ts):.0f} | {min(ts):.0f}–{max(ts):.0f} | {ok}/{len(ls)} ({ok / len(ls):.0%}) |")
    total_ok = sum(l["concluiu"].strip().lower() in ("sim", "s", "1", "true") for l in tempos)
    md += ["", f"**Taxa de conclusão geral: {total_ok}/{len(tempos)} ({total_ok / len(tempos):.0%})**", ""]

    md += ["## Facilidade de uso (1 a 5)", "", "| Pergunta | Média | Mediana |", "|---|---|---|"]
    medias = []
    for q, rotulo in PERGUNTAS.items():
        notas = [int(l[q]) for l in quest if l.get(q, "").strip()]
        if notas:
            medias.append(statistics.mean(notas))
            md.append(f"| {q}. {rotulo} | {statistics.mean(notas):.1f} | {statistics.median(notas):.1f} |")
    if medias:
        md += ["", f"**Nota média de facilidade de uso: {statistics.mean(medias):.2f} / 5**"]
    (PASTA / "resultado_indicadores.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
