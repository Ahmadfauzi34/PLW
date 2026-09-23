# Security Policy

PLW is a standalone codebase-analysis and agent-tooling binary. Security reports should distinguish vulnerabilities in PLW itself from findings produced by PLW while analyzing a target repository.

## Supported versions

The latest published PLW release is the supported release line. Development commits on `main` may contain unreleased changes and should not be treated as a stable security-support target.

## Reporting a vulnerability

Do not publish exploit details, credentials, private repository contents, or other sensitive material in a public issue.

If GitHub private vulnerability reporting is available for this repository, use the repository **Security** tab to submit the report privately. If a private reporting channel is not available, open a minimal public issue stating that you have a security report and need a private contact path; do not include exploit details in that issue.

A useful report includes:

- affected PLW version and binary platform;
- whether the issue reproduces from the standalone release binary;
- exact command and bounded reproduction steps;
- expected versus observed behavior;
- whether target-repository files, PLW state/cache, browser/runtime execution, or external-repository mutation are involved;
- impact and any known preconditions.

## Security boundaries

PLW intentionally separates analysis evidence from authority. In particular:

```text
candidate != patch
orientation != execution authority
runtime reproduction != root-cause proof
validated local fix != global regression proof
```

The portable-agent discovery/orientation surface is expected to remain read-only with respect to target source. Any unexpected source mutation, target-repository pollution, authority escalation, unsafe external-repository mutation, or bypass of release/binary integrity checks should be treated as security-relevant.
