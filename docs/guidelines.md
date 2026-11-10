# Guideline review and publication readiness

Reviewed against official documentation on 2026-11-10.

## Applied guidelines

- [Home Assistant integration structure](https://contributors.home-assistant.io/core/integrations/file-structure/):
  named integration directory, manifest, config flow, and lifecycle module.
- [Manifest reference](https://contributors.home-assistant.io/core/integrations/manifest/):
  stable domain, sorted metadata, own documentation URL, custom integration
  version, code owner, config flow support, and single-entry declaration.
- [Config flow](https://contributors.home-assistant.io/core/integrations/config-flow/):
  domain-bound ConfigFlow class, versioned entry, asynchronous user step, and
  translated confirmation/abort text. Custom integrations ship translations.
- [HACS integration requirements](https://hacs.dev/docs/publish/integration/):
  one integration per repo, self-contained runtime directory, and required
  manifest fields, including issue tracker and version.
- [HACS general requirements](https://hacs.dev/docs/publish/start/):
  root `hacs.json` with name and `render_readme: true` so a separate `info.md`
  is unnecessary. The repository README explains available behavior.
- [HACS validation action](https://hacs.dev/docs/publish/action/):
  official validation exists and is distinct from Home Assistant hassfest.

## Deferred publication work

This foundation is not a HACS approval or release. Before publication, review
current rules again, provide the required integration branding in
`home-assistant/brands`, verify public GitHub description/topics and issue access,
and run official HACS validation against the intended remote branch or release.
Brand submission is deliberately not part of a local foundation change.
Releases are optional for branch-based installation but should be planned with
version consistency before distributing usable functionality.

No HACS workflow bypasses branding or claims successful store validation. The
included CI uses hassfest for Home Assistant structure. A successful local test
run or hassfest check is not evidence that HACS publication requirements are met.

No license was selected on behalf of the owner. Choose a project license before
inviting reuse or publishing a distributable release.
