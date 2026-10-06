---
name: mac-dev-cleanup
description: Auditar e limpar candidatos Rust target, node_modules e Git worktrees sem perder trabalho local no Mac.
---
# Artefatos de desenvolvimento
Inventarie por Latch apenas raízes de projetos aprovadas, com limites de profundidade,
itens e duração. Não siga links nem procure no home inteiro. `scripts/mac_inventory.py`
na skill mac-health fornece candidatos somente leitura. Idade do diretório não mede
último uso: liste como indício, não prova. Nunca limpe automaticamente por idade.

## Rust
Considere `target` somente quando existir Cargo.toml no projeto pai. Descubra
CARGO_TARGET_DIR ou cargo metadata apenas quando usuário aprovar execução no projeto;
metadados podem invocar ferramentas, não suponha caminho padrão. Não remova toolchains
rustup, registry/cache Cargo nem fontes. Mostre custo de recompilar. Projetos recentes,
processos cargo/rustc ativos ou uso incerto devem ficar fora da limpeza.

## Node
Considere node_modules com package.json no pai. Identifique lockfile e workspace;
node_modules pode conter conteúdo editado e dependências locais, não é comprovadamente
reproduzível só por existir package.json. Não toque se for link, houver servidor/build
ativo ou não houver confirmação de que pode ser reinstalado. Não execute npm install
para validar: scripts de pacote podem executar código.

## Worktrees
Descubra repositórios e execute `git -C <repo> worktree list --porcelain` via Latch.
Por worktree: `git status --porcelain=v1 --untracked-files=all`, alterações staged,
ignorados (`git ls-files --others --ignored --exclude-standard`), lock/prunable,
branch e commits não enviados; determine remotes/upstream sem fetch automático.
Upstream ausente ou situação remota incerta impede afirmar que tudo está salvo.
Nunca remova worktree principal, locked, com alterações, arquivos não rastreados,
ignorados úteis ou commits não preservados. Ignorados podem ser dados importantes.
Worktrees gerenciadas pelo Codex devem ser arquivadas por sua ferramenta própria,
quando disponível, para preservar snapshot; não remova pastas gerenciadas à mão.
Outras worktrees limpas podem ser removidas com `git worktree remove <path>` após
aprovação específica e revalidação, sem --force, preservando a branch. Explique que
essa remoção não usa Lixeira. Se houver dados locais, pare e proponha backup revisável.
`git worktree prune --dry-run` só identifica metadados órfãos; prune não limpa arquivos.

## Executar
Apresente lote com caminho, categoria, tamanho (estimativa), evidência de atividade,
riscos e comando/operação. Reconfirme atividade antes de mudar. Rust/Node vão para
Lixeira ou quarentena aprovada com journal e instruções de restauração. Plano antigo,
processo ativo, conflito, falha de leitura ou symlink encontrado: pule e reporte.
Nunca encerre processos para viabilizar limpeza. Nunca use rm -rf ou worktree --force.
