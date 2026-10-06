# Coleta hospedada de conversas para evals

A imagem inclui o serviço s6 `mac-nurse-evals`, dependente de `plow-init`.
Roda no boot e a cada seis horas como usuário hermes. O código é root-owned em
`/opt/plow/mac-nurse-evals`, fora do home que o agente pode editar. Não usa rede,
credenciais, API de modelo ou ferramentas de escrita do Mac.

Lê `/var/lib/hermes/state.db` com SQLite `mode=ro`, `query_only` e uma transação.
Verifica as colunas reais de sessions/messages antes de coletar; formato inesperado
falha com erro genérico e preserva o relatório anterior. Filtra `source=plow_chat`.
Fonte verificada: NousResearch/hermes-agent, commit
`a036b13793a2275a71617d4e9bc2b7a78b2be42d`, hermes_state_common.py e gateway/session_recovery.py;
plow-pbc/hermes-plugin-plow, commit `a60f0c4e53dfffe9cbd9e11597d4e5085024cb16`, plataforma plow_chat.
O schema da imagem instalada é validado em runtime; a verificação de fonte não prova
que todas as imagens usam a mesma versão.

No máximo 100 sessões recentes sem novas mensagens nos últimos 120 segundos,
500 mensagens por conversa e 20 MiB totais. Sessões maiores são omitidas e contadas.
Não exporta reasoning, system_prompt, usuário, chat, cwd ou credenciais do ambiente.
Chamadas de ferramentas são texto não confiável; não inferimos grants, aprovação ou
sucesso como fatos. Conversas sem traces anotados exigem revisão.

Escreve corpus tratado e relatório em `/var/lib/hermes/mac-nurse-evals/` (0700),
arquivos 0600. O snapshot é sobrescrito a cada execução; não mantém export bruto
em disco. O corpus tratado continua privado porque regex não anonimiza tudo.
O relatório não inclui texto de conversa. O log do serviço só mostra contagens e
erro genérico. O estado não entra em Git, imagem, CI público ou Agent Index.

No chat privado: “Revise os relatórios de evals do Mac Nurse e proponha melhorias
com casos de regressão.” A skill mac-eval-review interpreta os relatórios e solicita
revisão do trace e do comportamento. Sem sinais comprovados, não inventa aprendizado.

## Ativação e rollback

A coleta só estará ativa depois que a nova imagem for implantada no Plow.
Publicar o código ou a imagem não atualiza a instância hospedada existente.
A pipeline pode ser testada sem Docker e não exige reabrir Docker local.
Para desativar, publique imagem sem o serviço e redeploy; preserve o estado privado
para auditoria. Nunca promova mudanças de comportamento com base somente em hints.
