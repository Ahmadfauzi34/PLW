# Runtime overlays

PLW's current distribution repository keeps the validated v0.1.0 runtime source as a digest-pinned capsule.

Small validated runtime updates are layered on top as digest-pinned overlays before source checks and binary packaging.

An overlay must:

1. live in its own directory;
2. declare the SHA-256 of the reconstructed patch;
3. reconstruct deterministically from committed chunks;
4. pass a dry-run before application;
5. apply only to a freshly unpacked verified capsule;
6. be covered by standalone binary smoke tests.

The `invocation_snapshot_v1` overlay keeps its patch in readable `change.patch`
and pins those exact bytes with `PATCH_SHA256`. The build verifies the digest,
dry-runs the patch, then applies it after the earlier ordered overlays. This
format makes the current invocation and snapshot changes directly reviewable.

The `readiness_version_v1` overlay follows the same readable, digest-pinned
patch format and separates reference-pack readiness from target topology and
action readiness. It also adds direct embedded version discovery.

The `browserless_ui_reference_v1` readable, digest-pinned overlay adds a
source-only Angular UI lookup and embedded skill. It never supplies geometry
or a runtime observation. Its binary smoke checks ambiguous targets, template
digests, inline templates, unavailable styles and explicit authority flags.

The `ui_source_precision_v1` readable, digest-pinned overlay keeps template
text with its immediate element or nearest interactive control, and exposes
the exact label/attribute terms and source ranking policy used for selection.
Its standalone smoke checks nested controls and ambiguous owners.

Candidate-selection updates must also bind exact source sites to the full
discovery candidate-set digest. Internal candidate-capability matching may
return `CAPABILITY_MATCHED`; it must not expose the mutation capability through
the public capability registry or grant authorization, execution, mutation,
correctness, or evidence-acceptance authority.

Shared-graph semantic-usage lists are sorted before hashing so candidate
discovery snapshots remain reproducible across separate Python processes.

Overlays are a transport/build mechanism only. They are never required beside the released `plw` executable and are never copied into target repositories.

The long-term repository cleanup is to normalize the runtime source into ordinary browsable Git files after the binary contract is stable.
