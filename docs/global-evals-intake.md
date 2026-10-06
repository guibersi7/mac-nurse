# Recepção privada e consentimento — decisões e operação

Esta fase implementa um piloto controlado. Nenhuma conversa real foi transmitida,
nenhum serviço público foi implantado e nenhum modelo pago foi chamado. Código de
harness permite replay explícito após configurar modelo, chave, destino e orçamento.

## Decisão 1 — identidade do usuário vem da autenticação

O operador cria tenant opaco e credencial aleatória. O servidor guarda somente o hash
da credencial; o token só aparece no arquivo privado escolhido (0600). Um envelope não
pode escolher tenant_id. Isso impede trocar o tenant no corpo para misturar dados.
O consentimento registra referência opaca da prova, validade e retenção. A referência
não comprova o clique por si só: o operador precisa verificar a autorização do usuário.
Não existe UI de consentimento público neste MVP, nem OAuth de usuários implantado.

## Decisão 2 — coleta local não implica compartilhamento central

O coletor Hermes atual continua local. Seu arquivo corpus tratado NÃO é enviado por
default. O usuário aceita finalidade, dados mínimos, destino privado e retenção antes
do operador preparar um lote. Redaction por regex não torna a conversa pública.
Um consentimento adicional registra destinos exatos de providers para replays com LLM.
A credencial central nunca é a credencial Plow, GitHub ou do Mac.

## Decisão 3 — SQLite privado para validar o fluxo sem escolher infraestrutura

O piloto usa SQLite em diretório 0700, banco 0600. Isso reduz dependências e permite
validar consentimento, isolamento lógico, idempotência e quotas antes de contratar
infraestrutura. Não é isolamento por processo ou criptografia por tenant. O operador
do hub pode ler todos os dados. Produção exige armazenamento protegido/encriptado,
backups com retenção, autenticação do operador, auditoria e isolamento compatível.
Não temos um endpoint central remoto disponível para usuários externos nesta etapa.

## Decisão 4 — rede restrita até escolher o host

`serve` só escuta 127.0.0.1. Há POST /v1/intake e GET /healthz sem dados privados; sem endpoints de export/admin.
Authorization Bearer identifica tenant e o consentimento é consultado do servidor.
O servidor não registra URL/body/header. Request limitado a 1MiB e 100 conversas,
10 mil fontes por tenant. O sender recusa redirects, credenciais no URL e HTTP remoto.
Para produção: terminar TLS em proxy autenticado, rate/concurrency limits, proteção de
rede, secret manager e logging sem payload. O servidor stdlib não é o servidor público
final. Compartilhar o destino exato exige aceite, não basta ligar um proxy.

## Decisão 5 — revogação se propaga até a release

Revogar bloqueia intake/export e remove registros/batches daquele tenant do hub.
O registro de source_ids opacos permanece para marcar fontes derivadas como proibidas
no ledger. O gate de replay/release consulta ledger novo (máximo 24h) e bloqueia fontes
revogadas/expiradas. `purge-expired` remove registros com retenção/consentimento expirado.
O operador deve agendar purge na infraestrutura escolhida; não há cron central ativo.
Cópias exportadas, backups e datasets já produzidos precisam de remoção separada.
O ledger bloqueia uma próxima release, mas não recolhe automaticamente imagem publicada.

## Comandos do piloto (dados sintéticos ou consentimento efetivamente verificado)

Escolha caminhos dentro de evals/private, que está fora de Git/build. Todos os exemplos
abaixo são templates; substitua o timestamp por uma validade UTC futura e os IDs por
identificadores opacos. Nunca coloque nomes/email/documentos na referência de prova.

```sh
python3 -m evals.global_evals.ingestion --store evals/private/hub register \
  --tenant pilot-001 --consent-id consent-001 --proof-ref proof-001 \
  --expires-at TIMESTAMP_UTC_FUTURO --retention-days 30 \
  --token-file evals/private/pilot-001.token

# Só acrescentar --provider-endpoint URL_HTTPS_EXATA se o usuário consentiu esse envio.
python3 -m evals.global_evals.transfer package \
  --corpus evals/private/corpus.jsonl --consent-id consent-001 \
  --agent-version COMMIT_40_HEX_OU_sha256:DIGEST \
  --output evals/private/batch.json

# Intake CLI, sem rede; requer a credencial daquele tenant:
python3 -m evals.global_evals.ingestion --store evals/private/hub ingest \
  --token-file evals/private/pilot-001.token --input evals/private/batch.json

# Alternativa local HTTP, em outro terminal:
python3 -m evals.global_evals.ingestion --store evals/private/hub serve
python3 -m evals.global_evals.transfer send \
  --input evals/private/batch.json --token-file evals/private/pilot-001.token \
  --destination http://127.0.0.1:8789/v1/intake --confirm-consented-transfer

# Export privado para curadoria, disponível só ao operador local:
python3 -m evals.global_evals.ingestion --store evals/private/hub export \
  --tenant pilot-001 --output evals/private/review.jsonl
python3 -m evals.global_evals.ingestion --store evals/private/hub consent-ledger \
  --output evals/private/consent-ledger.json
python3 -m evals.global_evals.ingestion --store evals/private/hub purge-expired
python3 -m evals.global_evals.ingestion --store evals/private/hub revoke --tenant pilot-001
```

Token/exports novos nunca sobrescrevem destinos existentes. Renovação de consentimento
e rotação de credenciais ainda precisam de fluxo administrativo dedicado; o MVP registra
novos tenants e revoga os anteriores, não oferece auto-renovação silenciosa.

Após export, crie dataset curado conforme [desenho global](global-evals-design.md).
Datasets de usuário e runs de modelos continuam em evals/private. Ao produzir casos
sintéticos públicos, o revisor precisa conferir desidentificação e origem explicitamente.
