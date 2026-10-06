---
name: mac-setup
description: Configurar Mac Nurse no primeiro uso, conectar Latch, escolher pastas, limites e agenda de monitoramento macOS.
---
# Configuração
1. Descubra as ferramentas Latch disponíveis e leia suas instruções. Confirme o Mac
   conectado com `uname -s`, `sw_vers` e o home real; não use o home do container.
2. Explique o inventário somente leitura e confirme escopo: Downloads, Documents,
   pasta de screenshots e raízes de projetos. Não assuma acesso a todo o home.
3. Registre no home privado Hermes `mac-care/preferences.json`: dispositivo,
   raízes aprovadas, timezone, horários silenciosos, frequência, limiares, pastas
   protegidas e regras de organização aprovadas. Não guarde conteúdo dos documentos.
   Use as ferramentas de filesystem do runtime para esse estado, nunca para o Mac.
4. Defaults propostos: disco livre <15% (crítico <8%), bateria com serviço recomendado,
   pressão de memória persistente. CPU isolada e idade de arquivo não geram limpeza.
   Coleta de 30 em 30 minutos, resumo semanal, sem mudanças automáticas por padrão.
5. Descubra a API nativa de agendamento Hermes. Crie um job somente após usuário
   aceitar frequência/horários, direcionado ao chat privado do dono e à skill
   mac-health. Confirme ID, timezone, destino e próxima execução na resposta.
   Não invente a sintaxe de cron nem crie automação Codex para o agente.
6. Job: obter amostra via Latch; aplicar silêncio e deduplicação; avisar só mudança
   relevante, falha nova ou ação necessária. Em indisponibilidade, registrar lacuna,
   avisar uma vez e suspender avaliações; recuperar ao voltar. Não alertar com dados antigos.
7. Permissões sempre passam pelo Latch. Se o usuário não quiser agendamento, oferecer
   diagnóstico sob demanda. Nunca declare um job criado sem retorno de sucesso.
