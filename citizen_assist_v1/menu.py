"""Menu por categorias (navegação guiada). Cada opção gera uma pergunta em texto, que segue
pelo mesmo grafo do agente que as perguntas livres."""

CATEGORIAS = {
    "FC-01": ("RG (carteira de identidade)", [
        ("Quanto custa", "Quanto custa a segunda via do RG?"),
        ("Documentos", "Que documentos preciso para a segunda via do RG?"),
        ("Prazo", "Em quanto tempo fica pronto o RG?"),
        ("Agendamento", "Preciso agendar para fazer o RG?"),
        ("Perdi ou fui roubado", "Perdi meu RG. Preciso levar boletim de ocorrência?"),
    ]),
    "FC-02": ("CPF", [
        ("Como fazer", "Como faço para me inscrever no CPF?"),
        ("Quanto custa", "Quanto custa o CPF?"),
        ("Documentos", "Que documentos preciso para o CPF?"),
    ]),
    "FC-03": ("Título de eleitor", [
        ("Quanto custa", "O título de eleitor é pago?"),
        ("Quem deve votar", "Quem é obrigado a votar?"),
        ("Prazo antes da eleição", "Até quando posso tirar ou transferir o título antes da eleição?"),
        ("Documentos", "Que documentos preciso para o título de eleitor?"),
    ]),
    "FC-04": ("Carteira de trabalho", [
        ("Como fazer", "Como faço a carteira de trabalho digital?"),
        ("Quanto custa e prazo", "Quanto custa e quanto demora a carteira de trabalho?"),
    ]),
    "FC-05": ("Certidões", [
        ("Quanto custa e prazo", "Quanto custa e quanto demora a segunda via de certidão?"),
        ("Pedir para outra pessoa", "Posso pedir a certidão de outra pessoa?"),
        ("Isenção", "Quem tem isenção na certidão?"),
    ]),
    "FC-06": ("CNH (renovação)", [
        ("Quanto custa", "Quanto custa renovar a CNH?"),
        ("Quando renovar", "Com quanto tempo de antecedência posso renovar a CNH?"),
        ("Documentos", "Que documentos preciso para renovar a CNH?"),
        ("Validade", "Por quanto tempo vale a CNH renovada?"),
    ]),
    "FC-07": ("Atendimento geral", [
        ("Horário", "Qual o horário de atendimento?"),
        ("Procuração", "Outra pessoa pode ir no meu lugar?"),
        ("Pagamento", "Como pago as taxas?"),
        ("Prioridade e Libras", "Como funciona o atendimento prioritário e o intérprete de Libras?"),
    ]),
}


def como_texto() -> str:
    linhas = []
    for i, (cod, (nome, opcoes)) in enumerate(CATEGORIAS.items(), 1):
        linhas.append(f"{i}. {nome}")
    return "\n".join(linhas)


def como_dict() -> list[dict]:
    return [{"codigo": cod, "nome": nome, "opcoes": [{"rotulo": r, "pergunta": p} for r, p in ops]}
            for cod, (nome, ops) in CATEGORIAS.items()]
