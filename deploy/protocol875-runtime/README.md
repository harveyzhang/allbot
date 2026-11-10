# Protocol runtime companion

The base image supplies the unchanged protocol and face verification executables. This overlay preserves the upstream Redis, web console and native startup stages. It renders credentials without printing them and accepts a read-only file at `WX_TOKEN_KEY_FILE` in addition to the existing `WX_TOKEN_KEY` setting. File values take precedence. Supply the protocol's original config and its Redis data independently of the framework's message queue. Keep the original CA directory for the verification proxy.

Build this Dockerfile with its `deploy/protocol875-runtime` directory in the context. Verify the two executable hashes and test the startup script with a substitute executable and a disposable credential before using live data.
