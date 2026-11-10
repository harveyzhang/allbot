# Fixed framework image

This recipe builds the framework from the pinned upstream multi-platform image and the patched source in this branch. The image starts with no 875 accounts or active Assistant configuration. Its Redis listener is bound to loopback. Configure the adapter and plugin when starting an instance. Keep credentials, databases and session backups outside the build context.

Build for Linux AMD64. Create a clean context containing the source paths listed by the Dockerfile, this directory at `deploy/framework-runtime`, the matching Python 3.11 wheels in `wheelhouse/`, and the approved Assistant plugin source at `private/assistant.py`. The wheel manifest fixes the complete offline dependency set. The runtime starts Redis and Python directly.

The pinned image was built from `e8ac4d4`. Upstream `8fc3fa4` additionally updates Markdown files. Place those files under `release-docs/` using their original repository paths. Verify the snapshot with `git diff --name-status e8ac4d4 8fc3fa4` before building.

```sh
docker build --network=none -f deploy/framework-runtime/Dockerfile \
  --build-arg ASSISTANT_SHA256="$assistant_sha256" \
  --build-arg SOURCE_REVISION="$source_revision" -t "$image_tag" .
```

Compare the final image ID and patched file hashes with the release receipt before promoting it. The protocol service has its own deployment.
