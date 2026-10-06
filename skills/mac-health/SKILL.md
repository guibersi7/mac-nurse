---
name: mac-health
description: Verificar e monitorar stats e saúde do Mac, disco, CPU, memória, bateria, processos e alertas.
---
# Diagnóstico do Mac
Execute só no Mac por Latch. Descubra a ferramenta de comandos e seu schema;
obedeça intenções, grants e sandbox descritos pelo servidor. Não copie o coletor
para o Mac sem autorização para esse destino. O script `scripts/mac_inventory.py`
é um recurso de referência executável: pode ser transferido para uma pasta
aprovada e executado com Python 3.9+ se disponível. Não instale Python automaticamente.
Se ausente, obtenha dados pelos comandos nativos equivalentes via Latch.

Coleta mínima: `sw_vers`, `uptime`, `df -k`, `vm_stat`, `memory_pressure`,
`pmset -g batt`, `sysctl -n hw.memsize`, `ps -axo pid,pcpu,pmem,comm`.
Colete só os processos mais relevantes para responder. Não execute `sudo`.
Bateria detalhada: System Information, se disponível; desktop sem bateria é N/A.
Não prometa temperatura, SMART ou ciclos quando hardware/permissões não expõem.

Relate horário, dispositivo e limitações de cada comando. Load average não é %CPU,
memória ocupada não equivale a pressão, status de energia não mede saúde da bateria.
Para CPU, pressão e lentidão, use pelo menos duas amostras separadas; identifique
processos, sem encerrá-los automaticamente. Quando disco ultrapassar limiar aprovado,
registre transição e deduplique. Repetir alerta só se piorar ou após intervalo aprovado.
Guarde snapshots mínimos no estado privado do agente; sem conteúdo de arquivos.

Responda com: status observado, causa provável com evidência, ação sugerida e espaço
recuperável estimado. Nunca limpe caches do sistema nem atribua um diagnóstico de
hardware com base em uma única métrica. Encaminhe limpeza à mac-dev-cleanup ou mac-files.
