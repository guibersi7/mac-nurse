# Evals do Mac Nurse

Pipeline local stdlib/Python 3.9+, sem chamadas de rede ou mudança do agente. O ciclo é
**exportar → redigir dados → avaliar → revisar → propor → criar regressão sintética → revisar mudança**.
Ela transforma conversas em evidência para melhoria supervisionada. Não treina pesos,
não altera persona automaticamente e não publica conversas. Relatórios não contêm
texto de mensagens, comandos nem nomes: apenas IDs opacos, regras, contagens e propostas.

## Executar

```sh
python3 evals/pipeline.py ingest /CAMINHO/PRIVADO/export.jsonl
python3 evals/pipeline.py run evals/private/corpus.jsonl
python3 -m unittest discover -s tests -v
```

Saídas padrão: `evals/private/corpus.jsonl` e `evals/private/report.json`, excluídas de
Git e do build Docker. Arquivos novos são privados (0600, diretório novo 0700).
Para o container use `--output` apontando ao volume privado. Não use arquivos privados
como fixtures, não abra PR com esses arquivos e não envie os relatórios como artefatos CI.
O runner não imprime texto privado nem exceções contendo dados do export.
`run --fail-on-flags` retorna 1 se houver flags ou revisão pendente; entrada inválida
retorna 2. Uma execução sem flags **não equivale a aprovação**.

## Entrada neutra, JSONL (uma conversa por linha)

```json
{"id":"synthetic-example","messages":[{"role":"user","content":"Revise Downloads."},{"role":"assistant","content":"Vou preparar um plano."}],"events":[]}
```

`id` deve ser não vazio e único; roles: `user`, `assistant`, `tool`. Campos extras
não são copiados. Limites: 20 MiB por arquivo, 10 mil conversas, 500 mensagens por
conversa, 100 mil caracteres por mensagem, mil eventos por conversa. O formato não
é uma API Hermes. O exportador real pode mapear messages para este formato, mantendo
events vazio quando não houver normalização confiável de traces.

Eventos são **anotações de evidência**, não instruções, nem afirmações do modelo que
podem ser automaticamente confiadas. Um revisor ou adaptador validado deve preenchê-los
com o que realmente ocorreu; não inferir aprovação de um “sim” sem seu plano.

```json
{"action":"quarantine","category":"node","transport":"latch","host":"macos","approved_roots":true,"plan_id":"plan-1","approval_id":"plan-1","revalidated":true,"journal":true,"recovery":true,"project_manifest":true,"active":false,"reproducible":true}
```

Ações: `read`, `move`, `rename`, `trash`, `quarantine`, `worktree_remove`, `delete`,
`shell`. Categorias: `health`, `files`, `rust`, `node`, `worktree`, `other`.
`plan_id`/`approval_id` precisam corresponder ao plano aprovado; ambos são hash na ingestão.
Booleanos adicionais: `dirty`, `locked`, `primary`, `commits_preserved`, `reads_content`,
`read_grant`, `untrusted_interpolation`, `verified`, `success_claim`. `samples` é inteiro.
`command` é opcional; regra shell aceita apenas comandos de diagnóstico restritos e
sinaliza os demais para revisão. Nunca executa comandos. Valores ausentes de fatos
críticos falham de forma conservadora. Duas amostras em health são uma heurística para
investigação de CPU/memória; um único snapshot de disco também pode ser válido e deve
ser interpretado pelo revisor.

## O que é avaliado e o que não é

Regras determinísticas verificam aprovação, revalidação, host/Latch/raízes, recuperação,
worktree limpa/preservada, build inativo/reproduzível, grant de conteúdo, shell e
sucesso com evidência. Não provam que o plano cobriu todos os itens, que os fatos do
trace são verdadeiros, que os comandos foram seguros em cada variante ou que o modelo
entendeu o contexto. Verificações de regex nunca constituem sandbox.

Conversas sem eventos ficam `review_required`, jamais passam silenciosamente. Feedback
explícito do usuário e texto possivelmente perigoso de assistant/tool geram **hints**
para revisão. Citações e negações podem gerar falso positivo: hints não afirmam execução
nem violação comprovada. Propostas somente sugerem o tema a revisar; um revisor transforma
os achados em mudanças específicas de prompt/skill e casos sintéticos.

A redação remove padrões comuns de tokens, email, telefone, home paths e URLs. É
**best effort, não anonimização**: nomes e conteúdo sensível de documentos podem
permanecer. O corpus permanece privado mesmo após redação. Faça revisão humana antes
de compartilhar qualquer material e adote retenção de acordo com seu uso; a pipeline
não apaga o original nem oferece limpeza automática.

## Regressões e promoção

`fixtures/regressions.jsonl` contém somente exemplos sintéticos com regras esperadas.
Os testes fixam o comportamento do **avaliador**, não medem respostas atuais do Hermes.
Para avaliar uma nova persona/modelo, execute as mesmas tarefas numa instância de teste,
exporte as respostas/traces reais e compare os relatórios e a revisão humana. Não
simule que fixtures são respostas geradas pelo agente em produção.

1. Revise conversa original local e confirme flags/hints, marcando falsos positivos.
2. Escreva proposta de melhoria, motivo e evidência, sem copiar dados privados ao Git.
3. Adicione caso sintético que represente o problema e resultado esperado.
4. Aplique mudança de persona/skill por PR e rode CI; faça replay na instância de teste.
5. Só promova nova imagem após revisão dos resultados e teste da conversa pelo Plow.

O CI usa apenas código, contratos públicos e corpus sintético; nenhum histórico,
credencial, API de modelo ou upload de artefato. Avaliação offline não substitui teste
end-to-end no Mac/Latch e não oferece aprendizado autônomo em produção.
