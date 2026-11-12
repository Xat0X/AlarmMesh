# Guideline review and publication readiness

Core guideline review: 2026-11-10. Marketplace/HACS repository, installation and
publication guidance rechecked against official sources on **2026-11-12**.

## Applied guidelines

- [Home Assistant integration structure](https://contributors.home-assistant.io/core/integrations/file-structure/):
  named integration directory, manifest, config flow, and lifecycle module.
- [Manifest reference](https://contributors.home-assistant.io/core/integrations/manifest/):
  stable domain, sorted metadata, own documentation URL, custom integration
  version, code owner, config flow support, and single-entry declaration.
- [Config flow](https://contributors.home-assistant.io/core/integrations/config-flow/):
  domain-bound ConfigFlow class, versioned entry, asynchronous user step, and
  translated confirmation/abort text. Custom integrations ship translations.
- [Marketplace repository structure](https://contributors.home-assistant.io/marketplace/reference/repository-structure/):
  public GitHub repository, root README and `hacs.json`, one self-contained
  integration and manifest metadata. Catalog requirements are a separate step.
- [Marketplace metadata reference](https://contributors.home-assistant.io/marketplace/reference/hacs-json/):
  the existing `hacs.json` remains the repository metadata, including minimum HA
  version. No minimum or package version was changed for these checks.
- [Custom integration guide](https://contributors.home-assistant.io/marketplace/guides/integrations/):
  manifest, shipped translations, restart behavior and local brand assets.
- [HACS validation action](https://hacs.dev/docs/publish/action/):
  official validation exists and is distinct from Home Assistant hassfest.

## Deferred publication work

Custom-repository installation does not imply catalog admission, approval or a
published release. The built-in Marketplace is the route from HA 2026.11; HACS
is the older 2026.10.4 route. See [installation](installation.md) for the reviewed
owner-operated installation/update/removal steps. The reported pilot installation
is recorded separately from independently tested compatibility.

Before any catalog request, review current rules, repository description/topics,
issue access, releases, branding and official HACS validation against the intended
remote revision. Current custom-integration guidance places images in the
integration's `brand/` folder; the old blanket instruction to submit custom
branding to `home-assistant/brands` is superseded. The owner's supplied images
are already packaged; this review adds no design. Their provenance and technical
checks are recorded in [branding](../assets/branding/README.md).
Default-branch installation without a release can identify a commit hash; catalog
admission requires releases. No release, metadata or catalog change is part of
this package.
([Official release requirements](https://contributors.home-assistant.io/marketplace/guides/releases/))

The included CI uses hassfest for Home Assistant structure. Successful tests,
compatibility checks or hassfest do not establish store approval. No catalog
validation/submission is introduced. The new independent compatibility
matrix is described in [development](development.md#complete-local-validation).

[GitHub workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
and [artifact handling](https://github.com/actions/upload-artifact) were checked
on 2026-11-12: read-only contents permission, bounded job timeouts, matrix
`fail-fast: false` and failure-time upload of only sanitized summaries. The
workflow has not run on GitHub for these local changes.

No license was selected on behalf of the owner. Choose a project license before
inviting reuse or publishing a distributable release.
