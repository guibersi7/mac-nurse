---
name: mac-setup
description: Configurar Mac Nurse, conectar Latch e oferecer perfis opcionais de permissões persistentes para reduzir pedidos recorrentes dentro de escopos aprovados.
---
# Configuração
1. Descubra as ferramentas Latch disponíveis e leia suas instruções canônicas.
   Chame plow_list_skills cedo, se disponível, e use as instruções próprias do Mac.
   Confirme o Mac conectado com uname -s, sw_vers e o home real; não use o home do
   container. Não execute diagnóstico no container como se fosse o computador.
2. No chat privado do dono, escolha raízes exatas: Downloads, Documents, screenshots
   e projetos. Explique tipos de leitura e exclusões. Não assuma todo o home.
3. Ofereça perfis fáceis de comparar e aguarde escolha explícita:
   - Sob demanda: a política atual do Latch decide cada pedido; sem novas regras.
   - Monitoramento recorrente: diagnóstico e inventário de metadados nas raízes.
   - Monitoramento e organização: inclui moves/renames apenas dentro de uma política
     de categorias/destinos aceita. Limpeza/descarte continuam por lote aprovado.
   Sem resposta, mantenha Sob demanda. Nunca interprete silêncio como consentimento.
4. Para perfil persistente, descubra a identidade autenticada exata do agente e
   confirme a instância correta com o dono. Regras são por agent UID, não pelo nome
   Mac Nurse ou slug. A migração de linha/instância não herda consentimentos.
5. Gere uma seção personalizada com references/latch-policy-template.md: identidade,
   perfil, raízes, exclusões e regra de organização. Perfis sem organização usam
   'Nenhuma organização autorizada'. Não aplique placeholders ou política ambígua.
   Mostre o texto final e peça consentimento específico para autorização persistente.
   Concordar em monitorar não autoriza ampliar acesso ao filesystem ou salvar regras.
6. Aplicação no Latch:
   - As ferramentas públicas atuais consultadas NÃO oferecem um setter de instruções
     Gatekeeper/rules. Não invente essa ferramenta nem escreva settings.json, policy,
     arquivos do Latch ou chaves pelo filesystem/shell para instalar uma permissão.
   - Prepare o texto para o dono acrescentar às instruções do Gatekeeper no Plow Latch,
     preservando regras existentes. Oriente pelo UI real, sem inventar menus da versão
     instalada. Em modo Ask, o dono pode optar por Always Allow no pedido específico,
     quando oferecido; explique o escopo de capabilities exibido antes da escolha.
   - Se uma versão futura expuser ferramenta oficial de gerenciamento, leia seu schema
     e só use após consentimento explícito sobre o texto final e a ampliação de acesso.
     Respeite aprovações do sistema; nunca automatize o clique do dono em uma aprovação
     de segurança nem troque o modo global para approve/desative o revisor.
7. Verifique o resultado por duas solicitações de diagnóstico iguais e sem escrita,
   usando argv/read_paths e escopo consistentes. Um completed confirma somente aquela
   operação; não prova que uma regra persistente foi salva. Só marque persistência como
   verificada quando o Latch/dono confirmar regra ou instrução salva. Não garanta zero
   prompts: mudança de escopo/UID, revisão AI, falta de créditos ou privacidade macOS
   podem exigir intervenção. No modo adversarial, a política do revisor continua valendo.
8. Para pending, explique e acompanhe plow_get_result; não replique a operação original.
   Para denied/blocked, siga a razão/diagnóstico canônico. Não reformule objetivos nem
   edite permissões para contornar negação. Se macOS pedir acesso à pasta/Automation,
   o dono precisa responder; não solicite Full Disk Access como padrão do onboarding.
9. Registre no home privado Hermes mac-care/preferences.json: dispositivo, agent UID,
   raízes, timezone, horários silenciosos, frequência, limiares, pastas protegidas,
   permission_profile, policy_version, consentimento e status da aplicação/verificação.
   Não guarde segredos ou conteúdo dos documentos. Estado do agente não é grant Latch.
10. Defaults propostos: disco livre <15% (crítico <8%), bateria com serviço recomendado,
    pressão de memória persistente. CPU isolada e idade de arquivo não geram limpeza.
    Coleta de 30 em 30 minutos, resumo semanal. Descubra a API de agenda Hermes e crie
    job só após aceitar frequência/horários; confirme ID, timezone, destino privado e
    próxima execução. Sem job confirmado, sem promessa de monitoramento contínuo.
11. Job: amostras novas via Latch, deduplicação e silêncio fora de mudanças relevantes.
    Se offline, registre lacuna e avise uma vez. Organização automática só dentro da
    política aceita e autorização efetiva Latch; limpeza e contexto incerto pedem revisão.
12. Explique como revogar: remover a regra Always Allow ou a seção Gatekeeper no Latch,
    cancelar os jobs Hermes e marcar o perfil como revogado. Revogar no estado do agente
    não remove a regra Latch, e remover regra não cancela job. Confirme cada resultado.
