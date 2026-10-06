# Instância de validação dos evals

Imagem: ghcr.io/guibersi7/mac-nurse@sha256:80a89e316e785c2854481906b4ba3c9dee6c1af744aa7678dbbeb41aa2aa2370
Commit: 5c9e9a647aae983fd1bc4bb16d3b5fb16300a34e
Linha: ln_p2, +1 (650) 315-6335
Agente: 33f5f8a2201d7086d21f556ad7e10856

A linha ln_p1 e suas conversas foram preservadas. Esta nova instância começa com
estado próprio; não recebeu as conversas da instância anterior.

## Validação após a primeira mensagem

No chat privado da nova linha, peça ao agente que verifique estes dados no próprio
runtime Hermes (não no Mac/Latch):

1. Presença do serviço s6 mac-nurse-evals e da skill mac-eval-review.
2. Presença do report em /var/lib/hermes/mac-nurse-evals/report.json, horário da
   coleta, número de conversas, missing_trace e omitted_sessions.
3. Após uma conversa de teste sem ações de escrita, aguarde pelo menos dois minutos
   de inatividade e peça uma coleta sob demanda:
   /opt/hermes/.venv/bin/python3 /opt/plow/mac-nurse-evals/runtime/collect.py
   Esse comando local não deve executar ferramentas do Mac nem publicar dados.
4. Confirme novo sampled_at e contagem >0. Sem traces anotados, review_required é
   esperado; não equivale a falha de coleta ou aprovação do comportamento.
5. Peça propostas de melhoria via mac-eval-review, sem modificar as skills ativas.

O primeiro snapshot no boot pode conter zero conversas. O serviço periódico roda
novamente em seis horas. Não diga que houve aprendizado em produção sem verificar
as saídas; running do Plow confirma provisionamento, não o conteúdo dos relatórios.
