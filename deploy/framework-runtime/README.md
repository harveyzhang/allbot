# Fixed framework image

This recipe builds the framework from the pinned upstream multi-platform image and the patched source in this branch. The image starts with no 875 accounts or active Assistant configuration. Its Redis listener is bound to loopback. Configure the adapter and plugin when starting an instance. Keep credentials, databases and session backups outside the build context.

Build for Linux AMD64. Create a clean context containing the source paths listed by the Dockerfile, this directory at `deploy/framework-runtime`, the matching Python 3.11 wheels in `wheelhouse/`, and the approved Assistant plugin source at `private/assistant.py`. The wheel manifest fixes the complete offline dependency set. The runtime starts Redis and Python directly.

The pinned image was built from `e8ac4d4`. The integration now tracks upstream `412e3e3`. Place every changed tracked runtime source and document since that base under `release-source/`, using its original repository path. Exclude Git metadata, deployment recipes and the separately supplied Assistant plugin implementation. Include the new Webhook routes, adapter and regression tests. Verify the staged file list and SHA-256 manifest before building.

The optional `wechat_875webhook` transport is disabled in the image at both adapter and protocol levels, and its example accounts are removed. Existing deployments retain their mounted account configuration and use the original 875 transport. The generic inbound Webhook endpoint also remains disabled unless explicitly configured. Upstream raw-message caching uses Redis with its configured expiry; quoted commands must come from the current message title, never from the quoted summary.

```sh
docker build --network=none -f deploy/framework-runtime/Dockerfile \
  --build-arg ASSISTANT_SHA256="$assistant_sha256" \
  --build-arg SOURCE_REVISION="$source_revision" -t "$image_tag" .
```

Compare the final image ID and patched file hashes with the release receipt before promoting it. The protocol service has its own deployment.
