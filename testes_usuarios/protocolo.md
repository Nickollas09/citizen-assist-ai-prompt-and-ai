# Protocolo do teste com usuários

Objetivo: medir **tempo para encontrar a informação** e **facilidade de uso** (Seção 4.3 do enunciado) com pelo menos **5 pessoas de fora do grupo**.

## Regras de privacidade (Seção 3)

- **Não anote nome, idade, e-mail, telefone nem nada que identifique o participante.** Use só o código P1, P2, P3...
- Não grave tela, voz ou rosto.
- Antes de começar, diga ao participante: *"É um protótipo com dados fictícios. Não digite nenhum dado seu de verdade."*
- Registre apenas: código do participante, tempo, se concluiu a tarefa e as notas do questionário.

## Preparação

1. Rode `python app_web.py` e abra http://localhost:8000 numa aba anônima.
2. Tenha um cronômetro (o do celular serve).
3. Leia as tarefas em voz alta, uma por vez. Não ajude durante a tarefa.

## As 3 tarefas

| # | Tarefa lida ao participante | Resposta certa (para conferir) |
|---|---|---|
| T1 | "Descubra o que você precisa levar para tirar a segunda via do RG." | Certidão de nascimento ou casamento; comprovante de residência (90 dias); BO em roubo/furto ou declaração de extravio em perda (FC-01) |
| T2 | "Sua CNH venceu há 45 dias. Descubra se você pode dirigir." | Não pode dirigir até renovar (FC-06) |
| T3 | "Descubra se a Central atende aos sábados." | Não; segunda a sexta, 8h às 17h (FC-07) |

- **Tempo:** comece quando terminar de ler a tarefa; pare quando a pessoa disser a resposta.
- **Concluiu:** `sim` se a resposta dita estiver correta; `nao` se errou ou desistiu (limite de 3 minutos).
- Anote em `registro_tempos.csv`, uma linha por tarefa. Exemplo de formato: `P1,T1,42,sim,usou o menu`.

## Questionário (depois das 3 tarefas)

Escala de 1 (discordo totalmente) a 5 (concordo totalmente). Anote em `questionario_respostas.csv`.

| # | Afirmação |
|---|---|
| q1 | Foi fácil encontrar a informação que eu procurava. |
| q2 | As respostas estavam em linguagem clara e fácil de entender. |
| q3 | Eu confiei na resposta porque ela mostrava de onde veio a informação. |
| q4 | Consegui usar o assistente sem precisar de ajuda. |
| q5 | Eu usaria este assistente de novo para tirar dúvidas sobre documentos. |

## Depois do teste

```bash
python testes_usuarios/calcular_indicadores.py
```

O script gera `testes_usuarios/resultado_indicadores.md` com tempo médio e mediano por tarefa, taxa de conclusão e nota média de facilidade de uso. Cole essa tabela no relatório.
