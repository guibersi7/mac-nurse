# Fontes Plow consultadas — 2026-10-05

Documentação pública aplicável à variante. O backend Plow é privado; não foi possível
ler “toda” a documentação interna. As páginas podem mudar; o Dockerfile usa digest.

- https://aiworthusing.com/agent-index/publish — publicação e caminhos Plow/BYO.
- https://github.com/plow-pbc/plow-hermes-agent — contrato da variante, persona,
  skills, seed/reconcile, boot, relay Latch, credenciais e reporter herdado.
- https://github.com/plow-pbc/plow-agents — login, linhas, deploy, registry e admissão.
- https://github.com/plow-pbc/latch — Mac remoto, intenções, grants, sandbox e auditoria.
- https://github.com/plow-pbc/life-assistant-hermes-agent/blob/main/Dockerfile —
  referência imutável de base publicada por variante oficial.
- https://github.com/plow-pbc/plow-hermes-agent/blob/main/compose.yml — volume e shutdown.
- https://github.com/plow-pbc/agent-index-client — dados enviados e identidade de instalação.

A CLI e a página publish divergem em detalhes históricos. Para o runtime desta
variante, seguimos o contrato da base Hermes; não adicionamos segundo reporter.
Schemas de ferramentas Latch e cron Hermes são descobertos em runtime, evitando
acoplar a skill a nomes de APIs não confirmados. Não instalamos ferramentas Mac
no container Linux para coletar stats do usuário.
