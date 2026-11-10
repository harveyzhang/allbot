FROM ghcr.io/sxkiss/allbot-protocol875@sha256:41a6e57872b11c3be1c3f041cd5990f98a4f3fffa20b834fdf20cece1f8f83ae
COPY deploy/protocol875-runtime/configure.py /opt/protocol-runtime/configure.py
RUN printf '%s  /app/entrypoint.sh\n' 88d335c5ad8d381d4e6cdb77dfd99b4c543ade06ba834e26874d537221ae2eec | sha256sum -c - \
    && python /opt/protocol-runtime/configure.py --patch-entrypoint && bash -n /app/entrypoint.sh
ARG SOURCE_REVISION
LABEL org.opencontainers.image.revision=$SOURCE_REVISION \
      org.opencontainers.image.base.digest="sha256:41a6e57872b11c3be1c3f041cd5990f98a4f3fffa20b834fdf20cece1f8f83ae"
