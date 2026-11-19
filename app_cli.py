"""Chat no terminal, com menu por categorias e pergunta livre.

    python app_cli.py                               (menu + perguntas)
    python app_cli.py "quanto custa o RG?"          (pergunta única)
"""
import re
import sys

from citizen_assist import AgenteCidadao
from citizen_assist.menu import CATEGORIAS


def _terminal(md: str) -> str:
    md = re.sub(r"^### (.+)$", lambda m: f"\n\033[1;36m{m.group(1)}\033[0m", md, flags=re.M)
    md = re.sub(r"\*\*(.+?)\*\*", "\033[1m\\1\033[0m", md)
    md = re.sub(r"(?<![*\w])\*(?!\*)(.+?)\*", "\\1", md)
    return re.sub(r"(?m)^_(.+)_$", "\033[2m\\1\033[0m", md)


def mostrar_menu():
    print("\n\033[1mMenu\033[0m (digite o número, ou escreva sua pergunta; 'sair' encerra)")
    for i, (_, (nome, _)) in enumerate(CATEGORIAS.items(), 1):
        print(f"  {i}. {nome}")


def escolher_opcao(indice: int) -> str | None:
    cod = list(CATEGORIAS)[indice]
    nome, opcoes = CATEGORIAS[cod]
    print(f"\n\033[1m{nome}\033[0m")
    for i, (rotulo, _) in enumerate(opcoes, 1):
        print(f"  {i}. {rotulo}")
    print("  0. Voltar")
    esc = input("Opção: ").strip()
    if esc.isdigit() and 1 <= int(esc) <= len(opcoes):
        return opcoes[int(esc) - 1][1]
    return None


def main():
    agente = AgenteCidadao()
    conversa = agente.nova_conversa()
    if len(sys.argv) > 1:
        print(_terminal(conversa.perguntar(" ".join(sys.argv[1:])).texto))
        return
    print("Citizen Assist AI · Central do Cidadão de Aurora (protótipo educacional, não é canal oficial)")
    print("Não digite CPF, endereço, telefone ou outros dados pessoais.")
    mostrar_menu()
    while True:
        try:
            q = input("\n\033[1mVocê:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if q.lower() in ("sair", "exit", "quit"):
            break
        if q.lower() in ("menu", "m"):
            mostrar_menu()
            continue
        if q.isdigit() and 1 <= int(q) <= len(CATEGORIAS):
            q = escolher_opcao(int(q) - 1)
            if not q:
                mostrar_menu()
                continue
            print(f"\033[2m→ {q}\033[0m")
        print("\n\033[1mAssistente:\033[0m " + _terminal(conversa.perguntar(q).texto))
        print("\033[2m(digite 'menu' para ver as categorias)\033[0m")


if __name__ == "__main__":
    main()
