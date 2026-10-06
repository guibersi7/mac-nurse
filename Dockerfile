# Official Hermes base verified in public ECR on 2026-10-06.
FROM public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-bfa8922549dca5e40c20523388e66a21ff876ceb@sha256:8adb4d7e6dd94d0eb9ad8662f7840d1535323e3e35559d40790ae383c1716fc5
ENV AGENT_ID=mac-nurse
ENV AGENT_NAME="Mac Nurse"
ENV AGENT_BLURB="Assistente para monitorar a saúde do Mac, organizar arquivos e revisar limpezas de projetos."
COPY --chown=0:0 persona.md /opt/hermes/plow-seed/persona.md
RUN chmod 0644 /opt/hermes/plow-seed/persona.md
COPY --chown=10000:10000 skills/ /var/lib/hermes/skills/
COPY --chown=10000:10000 skills/ /opt/hermes/skills/
