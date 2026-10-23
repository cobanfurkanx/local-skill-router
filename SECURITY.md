# Security and local data

The router reads locally configured skill files and writes an index/state directory. Treat skill text as untrusted input. A relevance score is not an instruction, safety verdict, installation permission, or proof that required tools exist.

Do not use a shared writable state directory across untrusted users. Keep skill libraries and this program in locations controlled by the intended local user. The tool is not a sandbox; returned paths and snippets can be sensitive and can enter the host agent's ordinary logs.

Learning/feedback are opt-in and may retain task terms, evidence and local paths. Hooks store hashed session identity and signatures, but the index still contains local metadata. Setup journals contain prior application settings and can therefore be private. Do not commit or upload state. Local retrieval/hooks make no network requests; remote discovery explicitly sends short queries to skills.sh and downloads public GitHub content. No analytics or additional model service is implemented.

Remote content is untrusted even when pinned and hashed. Inspect its instructions, helper code, invocation policy, license and tool fit. `reviewed` is owner permission to accept the calling agent's review, not a guarantee that review is correct. Archive/file limits, path/symlink checks, no-overwrite installs, immutable commits and undo reduce risks but cannot prove a skill is safe. Installation never executes downloaded helpers; a host agent may later choose to run one under its own permissions. Do not enable unattended global installation for an agent you do not trust.

For a suspected vulnerability, use the repository's private vulnerability reporting when available. Avoid putting secrets, native settings backups or private skill contents in a public issue. If that channel is unavailable, ask the owner for a private channel with a minimal non-sensitive description.
