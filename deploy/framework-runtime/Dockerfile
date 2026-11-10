FROM docker.io/sxkiss/allbot@sha256:ddf39b3c28ce0a793d6f782f232f5ce2a36159c945af9f377e46c09f2ebbef64 AS wheels
COPY wheelhouse/ /opt/wheelhouse/
COPY deploy/framework-runtime/wheels.sha256 /opt/wheels.sha256
RUN cd /opt/wheelhouse && sha256sum -c /opt/wheels.sha256 >/dev/null \
    && test "$(find . -type f | wc -l)" -eq "$(wc -l < /opt/wheels.sha256)" \
    && python -m pip install --disable-pip-version-check --no-cache-dir --no-index \
       --only-binary=:all: --find-links=/opt/wheelhouse --prefix=/opt/installed \
       --ignore-installed -r /app/requirements.txt

FROM docker.io/sxkiss/allbot@sha256:ddf39b3c28ce0a793d6f782f232f5ce2a36159c945af9f377e46c09f2ebbef64
COPY --from=wheels /opt/installed/ /usr/local/
COPY release-docs/ /app/
COPY admin/routes/adapter_routes.py /app/admin/routes/adapter_routes.py
COPY admin/routes/INDEX.md /app/admin/routes/INDEX.md
COPY adapter/wechat_875/adapter.py /app/adapter/wechat_875/adapter.py
COPY adapter/wechat_875/wx875client/core.py /app/adapter/wechat_875/wx875client/core.py
COPY adapter/wechat_875/wx875client/protocol875.py /app/adapter/wechat_875/wx875client/protocol875.py
COPY tests/test_875_access_and_media.py /app/tests/test_875_access_and_media.py
COPY tests/test_quoted_media_upload.py /app/tests/test_quoted_media_upload.py
COPY plugins/AssistantPlugin/INDEX.md /app/plugins/AssistantPlugin/INDEX.md
COPY private/assistant.py /app/plugins/AssistantPlugin/main.py
COPY deploy/framework-runtime/image_defaults.py /opt/framework-image/defaults.py
COPY deploy/framework-runtime/start.sh /opt/framework-image/start.sh
ARG ASSISTANT_SHA256
RUN test -n "$ASSISTANT_SHA256" \
    && printf '%s  %s\n' "$ASSISTANT_SHA256" /app/plugins/AssistantPlugin/main.py | sha256sum -c - \
    && python /opt/framework-image/defaults.py && python -m pip check
ARG SOURCE_REVISION
LABEL org.opencontainers.image.revision=$SOURCE_REVISION \
      org.opencontainers.image.base.digest="sha256:ddf39b3c28ce0a793d6f782f232f5ce2a36159c945af9f377e46c09f2ebbef64"
WORKDIR /app
CMD ["sh", "/opt/framework-image/start.sh"]
