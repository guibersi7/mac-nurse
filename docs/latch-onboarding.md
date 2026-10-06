# Onboarding com autorizações persistentes

O Mac Nurse oferece Sob demanda, Monitoramento recorrente e Monitoramento e organização.
O usuário escolhe raízes e uma política concreta antes de qualquer regra persistente.
O template vive em skills/mac-setup/references/latch-policy-template.md.

## O que pode acontecer sem novos pedidos recorrentes
- Diagnósticos de leitura e inventário de metadados no escopo escolhido.
- Organização por política de destinos/contextos já aceita, se esse perfil for escolhido
  e o Gatekeeper efetivamente autorizar as operações.
- Descarte, target/node_modules e worktree removal continuam por lote específico.

A configuração tem duas camadas: instruções e consentimento da tarefa no Mac Nurse;
regras/capabilities e revisão no Latch. Uma conversa 'aceito' não instala um grant.
Permissões macOS de pastas/Automation também são distintas. Não há garantia de zero
prompts. read_paths declara intenção; o sandbox não é um limite completo de leitura.

## Limite da integração atual
No código público Latch consultado, commit 46428fc7eb3d512767511e5af3f688a27afef7ad,
packages/mcp-server/src/tools.ts não expõe gerenciamento de regras/instruções.
O Gatekeeper tem UI própria e Always Allow vincula agent ID e conjunto normalizado de
capabilities. O agente prepara o texto e orienta o dono a aplicá-lo na UI. Não altera
arquivos internos ou configura aprovação global irrestrita. Uma futura API oficial
poderá automatizar a aplicação após consentimento específico e confirmação do Latch.

Fonte: https://github.com/plow-pbc/latch — README, settings.ts, policyEngine.ts,
renderer/main.js, adversarialAgent.ts e mcp-server/src/handler.ts/tools.ts.

## Teste de aceitação da versão instalada
1. Perfil Sob demanda não altera Latch nem cria permissões persistentes.
2. Perfil recorrente produz texto completo para um UID e raízes exatos, sem placeholders.
3. Usuário aplica a seção sem perder restrições existentes; o onboarding distingue
   consentimento, aplicação e verificação, sem afirmar grant por um único completed.
4. Repetir diagnóstico e inventário retorna resultado ou pending/denied explicado.
5. Escrita fora das raízes, shell arbitrário, limpeza e agente com UID diferente não
   recebem aprovação desta seção. Não simular execução destrutiva para testar política.
6. Mudança de UID exige nova autorização; revogação cancela jobs e explica remoção local.

Esses testes de integração Latch precisam ser feitos na versão do usuário. O CI de
instruções e evals não prova que a política persistente foi aplicada ao seu Mac.
