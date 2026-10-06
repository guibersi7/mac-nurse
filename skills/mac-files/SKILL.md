---
name: mac-files
description: Organizar Downloads e Documents e pastas do Mac, sugerir descarte e renomear screenshots e documentos pelo contexto.
---
# Organização revisável
1. Inventarie apenas raízes aprovadas. Não siga symlinks, aliases, pacotes .app,
   bibliotecas de fotos, .git ou arquivos ocultos. Não atravesse volumes. Arquivos
   cloud-only devem ser marcados e não baixados automaticamente. Não leia conteúdo
   sem permissão específica; classifique primeiro por extensão, nome e metadados.
2. Pergunte as categorias úteis: projeto, trabalho, pessoal, financeiro, estudos.
   Proponha uma taxonomia rasa. Extensão sugere tipo, não contexto; dúvida vai para
   revisão, nunca para uma categoria inventada. Não reorganize repositórios de código.
3. Para contexto de screenshot, use visão/OCR disponível só com aprovação de leitura
   do arquivo. Para documentos, leia o mínimo permitido. Não exponha texto sensível
   no chat/nomes. Sem evidência suficiente, mantenha o nome ou peça contexto.
4. Sugira nomes como `2026-10-05_checkout-erro-token.png`, preservando extensão e
   data real quando conhecida. Remova separadores, controles e nomes especiais;
   se já existir destino, acrescente sufixo, nunca sobrescreva. Não assuma screenshot
   pela localização; confirme tipo. Renomear pode quebrar referências: informe no plano.
5. Produza plano imutável com ID, origem, destino, ação, evidência, confiança,
   tamanho, identidade do arquivo e motivos. Plano aprovado cobre só esses itens.
   Revalide identidade/tamanho/mtime e destino imediatamente antes da operação;
   alteração desde a revisão invalida aquele item. Proíba destinos fora das raízes
   aprovadas, symlinks e mover diretório para dentro dele mesmo.
6. Descarte exige aprovação explícita por item/lote; idade é só sinal para revisão.
   Use ferramenta macOS de mover para Lixeira, se exposta pelo Latch. Se não houver,
   ofereça mover para pasta de quarentena aprovada; não simule Lixeira com `rm`.
   Nunca apague permanentemente e nunca esvazie a Lixeira.
7. Use operações de arquivos estruturadas do Latch; se precisar shell, passe caminhos
   como argumentos devidamente citados, nunca interpolando texto/OCR em comando.
   Registre cada sucesso/falha no journal privado. Pare quando houver conflito.
8. Desfazer: verifique se o item ainda existe no destino e se origem está livre;
   restaure sem sobrescrever. Para Lixeira, use a operação disponível ou oriente
   Put Back no Finder. Não declare reversão até verificar o caminho original.
