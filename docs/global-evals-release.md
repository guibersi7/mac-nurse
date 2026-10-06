# Release: decisões e limites

## Construir candidata é diferente de promover produto

O workflow publish-image constrói/publica uma imagem após testes offline. Isso permite
preparar candidatas sem declará-las melhores. Ele não atualiza instâncias Plow em uso.
O catálogo/release do produto só deve apontar uma candidata após comparação e piloto
revisados. O processo ainda não faz promoção automática do catálogo.

## Por que a aprovação precisa de identidade imutável

A aprovação humana em release-plan vincula digest da comparação e image@sha256.
Uma etiqueta v1/latest muda de conteúdo, por isso não serve para esse vínculo.
O operador precisa verificar também a correspondência entre commit, instruções usadas
no replay e imagem construída: a pipeline registra hash das instruções, mas não
inspeciona a imagem remota para provar que elas foram empacotadas lá.

## Manifesto mínimo assinado

release_manifest.py valida novamente dataset, respostas revisadas, comparação,
consentimento e aprovação. Só então assina metadata HMAC-SHA256: repo destinatário,
imagem, digest da comparação, validade e escopo pilot-only. Isso evita publicar
conversas ou dataset de usuários no CI só para verificar uma aprovação.

HMAC usa uma chave compartilhada do operador com o verificador. Não autentica a
proveniência da conversa ou chamada do modelo e não substitui revisão humana.
A chave não foi criada/configurada nos secrets GitHub nesta implementação.
Quando houver secret EVAL_RELEASE_SIGNING_KEY, o workflow manual verify-global-release
verifica o manifesto. Nenhum token Plow é necessário: esse workflow NÃO executa deploy.

```sh
# Configure EVAL_RELEASE_SIGNING_KEY via armazenamento privado de secrets;
# nunca coloque a chave no comando, repositório, logs ou imagem.
python3 -m evals.global_evals.release_manifest \
  --repository guibersi7/mac-nurse sign \
  --dataset evals/private/dataset.json \
  --baseline evals/private/baseline-reviewed.json \
  --candidate evals/private/candidate-reviewed.json \
  --image ghcr.io/guibersi7/mac-nurse@sha256:DIGEST_64_HEX \
  --approval evals/private/approval.json \
  --consent-ledger evals/private/consent-ledger.json \
  --output evals/private/pilot-manifest.json
python3 -m evals.global_evals.release_manifest \
  --repository guibersi7/mac-nurse verify --manifest evals/private/pilot-manifest.json
```

## Por que a frota continua bloqueada

A documentação pública Plow diz que promoção muda novas provisões, enquanto instâncias
existentes mantêm suas imagens. Não validamos uma API de atualização in-place com
preservação de conversas, jobs, configuração e identidade/grants Latch.
release-plan marca fleet_rollout como bloqueado por essa dependência; não implementa
revoke/recreate automático. Esse seria um efeito real sobre conversas e permissões.

Fonte: https://github.com/plow-pbc/plow-agents#register-admit-then-promote-an-agent-image

## Piloto e rollback

Antes da expansão: implantar em linha de teste explicitamente inscrita, verificar
resposta iMessage, permissões Latch, coletor, tarefas e erros. Registrar a imagem anterior
por digest, os critérios para interromper e o procedimento de recuperação de estado.
Uma candidata pior em segurança/regressão não é promovida por média de acertos melhor.
Para atualizações que não buscam ganho funcional (ex. manutenção), precisamos de outro
conjunto de critérios; o gate atual de melhoria exige ganho em development.
