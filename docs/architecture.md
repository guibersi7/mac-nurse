# Arquitetura e aceitação

Pessoa → Plow Chat → Hermes + persona/skills → relay Plow → Latch → Mac.
O volume Hermes mantém preferências, snapshots mínimos e journal. O Mac mantém seus
arquivos; não é bind-mounted. Conteúdo privado não deve ir ao Agent Index.
O container deve iniciar pelo /init herdado, sem sobrescrever gateway/config/base.
A base é fixada pelo digest da imagem oficial Hermes atual, consultado no ECR; disponibilidade
no registry e inicialização precisam ser verificadas antes de declarar release.

## Fluxos para verificar em uma conta conectada
1. Onboarding identifica Darwin e raízes do Mac; recusa Linux/offline.
2. Diagnóstico mostra métricas reais com horário e erros explícitos.
3. Coleta repetida diferencia pressão persistente de uma amostra isolada.
4. Job confirmado no chat privado alerta apenas transições; quiet hours funcionam.
5. Organização gera plano, espera aprovação, não sobrescreve e registra mudança.
6. Documento alterado desde a revisão fica fora do lote; conteúdo malicioso é ignorado.
7. Screenshot sem contexto não recebe um nome inventado.
8. Rust/Node ativos ou incertos são preservados. Worktree dirty/locked/unpushed é preservada.
9. Restauração não sobrescreve origem e verifica resultado.
10. Mac offline produz lacuna e aviso deduplicado; reconexão retoma dados novos.

Esses são cenários de integração pendentes, não resultados de testes automatizados.
Testes locais cobrem limites e segurança do coletor; persona não garante comportamento
sem avaliação do runtime/modelo. Não habilitar regras de escrita persistentes antes
de verificar os fluxos no Mac de teste e revisar as permissões do Latch.
