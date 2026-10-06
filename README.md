# Mac Nurse — agente Plow para macOS

Variante Hermes para monitorar saúde do Mac e organizar arquivos e projetos.
O agente roda em Linux/Docker; o Mac é acessado exclusivamente pelo Plow Latch.
Persona e quatro skills estão implementadas. Não é um daemon macOS independente.

## Capacidades
- Stats de disco, memória e bateria; investigação de CPU/processos sob demanda.
- Alertas com limiares configuráveis, deduplicação e horários silenciosos.
- Planos para organizar Downloads/Documents e renomear por contexto.
- Auditoria de Rust target, node_modules e Git worktrees.
- Mudanças aprovadas via Latch; Lixeira/quarentena para arquivos e journal para desfazer.

Nenhuma limpeza ou reorganização acontece ao iniciar. Onboarding define raízes,
permissões e agenda. Agendamento precisa ser configurado pelo agente na API Hermes;
sem um job confirmado não existe monitoramento periódico. Mac dormindo, desligado
ou Latch desconectado impede coleta. Não há previsão de falha de hardware.

## Deploy hospedado

Identidade: `mac-nurse` / **Mac Nurse**. Linha: `ln_p1`, +1 (650) 346-6610.
Imagem pública: `ghcr.io/guibersi7/mac-nurse:v1`. Deploy hospedado no Plow por digest.
O Docker local não precisa ficar aberto; o Latch no Mac continua necessário.
Volume local preservado para recuperação do histórico; estado não foi transferido à nuvem.
Credenciais ficam fora do Git e da imagem. Não compartilhe esses arquivos.

## Rodar
Requer Docker em execução, Python 3.11+ para CLI Plow, uma linha Plow disponível,
conta ativada por mensagem e Plow Latch conectado ao Mac do usuário.

```sh
git clone https://github.com/plow-pbc/plow-agents.git /tmp/mac-care-plow-cli
export PATH="/tmp/mac-care-plow-cli/bin:$PATH"
plow-agents login
plow-agents lines
# Substituir pelo ID real de uma linha disponível:
plow-agents deploy --local --line ln_SEU_ID
docker compose logs -f
```

Envie à linha: “Configure o Mac Nurse. Comece só com diagnóstico de saúde e inventário.
Minhas pastas de projetos são ...”. O Latch exibirá os pedidos de permissão.
O compose preserva sessões em volume próprio e não monta arquivos do Mac.
Não use `docker compose down -v` para atualizar; isso apaga o estado do agente.
Após editar persona/skills: `docker compose up -d --build`.

## Coletor somente leitura
O script precisa rodar **no Mac**, por Latch após aprovar a transferência/execução,
ou manualmente. Requer Python 3.9+. Ele não organiza ou apaga arquivos:

```sh
python3 skills/mac-health/scripts/mac_inventory.py --projects /caminho/aprovado/projetos
python3 -m unittest discover -s tests -v
```

Inventário limitado a 10 mil entradas, profundidade 6 e 15s por raiz; não segue links
nem atravessa volumes. Candidatos não são automaticamente elegíveis para apagar.
A implementação de mudanças é conduzida pelo Hermes usando as operações Latch;
não existe motor local de exclusão automática neste projeto.

## Publicar depois de testar
```sh
plow-agents image build ghcr.io/SEU_USUARIO/mac-nurse:v1
plow-agents image push ghcr.io/SEU_USUARIO/mac-nurse:v1
```

Torne a imagem pública e use a referência por digest retornada para deploy cloud.
Antes de publicar no Agent Index, escolha slug e configure a licença do projeto.
A base oficial fornece o reporter: `AGENT_ID`, `AGENT_NAME`, `AGENT_BLURB` no arquivo
local plow-credentials ativam o registro/uso público. Deixe AGENT_ID ausente em testes
privados. Habilitar instalação em um clique requer admissão inicial por admin Plow.
Nunca inclua credenciais, documentos, screenshots ou relatórios privados na imagem.

Veja [arquitetura e critérios de aceitação](docs/architecture.md) e
[fontes oficiais consultadas](docs/plow-sources.md).
