# Install and remove AlarmMesh

Reviewed against the linked official documentation on **2026-11-11**. These are
instructions for the owner; this documentation task performed no live installation,
update, restart or removal. AlarmMesh is a community integration, not a certified
fire alarm system. No smoke reported is not a safety guarantee.

## Home Assistant 2026.11 and later: built-in Marketplace

1. As administrator, open **Settings > Marketplace** (Dutch: **Instellingen >
   Marktplaats**). Review its community-content warning.
2. Choose **Add from link**, enter `https://github.com/Xat0X/AlarmMesh`, and add
   it as an **Integration** if asked. Connect GitHub through HA's own authorization
   screen if prompted; never paste credentials into an issue or configuration file.
3. Open AlarmMesh, select **Install**, review the offered revision, and confirm.
   Follow a restart repair if shown; a first installation can load immediately.
4. Continue with configuration below.

Updates appear under **Settings > Updates**. Review the offered revision before
installing; restart HA after an integration update using the repair guidance.

To remove it, delete the AlarmMesh entry under **Settings > Devices & services**,
then use **Marketplace > AlarmMesh > ⋮ > Uninstall** to remove installed files.
The Marketplace also offers **Delete and uninstall** when configuration remains.
Follow any restart repair. Removing a repository from **Add from link > Added from
links** only removes that link; it is not an uninstall.
([Official Marketplace instructions](https://www.home-assistant.io/integrations/marketplace/))

Adding a custom repository is separate from admission to the public catalog and
does not imply Home Assistant review or approval. Starting in 2026.11 the built-in
Marketplace replaces the HACS integration; use HACS only on the older baseline.
([Marketplace architecture](https://contributors.home-assistant.io/marketplace/how-it-works/),
[repository types and HACS transition](https://contributors.home-assistant.io/marketplace/reference/repository-structure/))

## Older baseline: Home Assistant 2026.10.4 with HACS

With HACS already installed and configured, open **HACS > ⋮ > Custom repositories**.
Add `https://github.com/Xat0X/AlarmMesh` with type **Integration**. Open AlarmMesh
in HACS, download it, follow the restart prompt, then configure it below.
([HACS custom repositories](https://hacs.dev/docs/faq/custom_repositories/),
[HACS integration installation](https://www.hacs.dev/docs/use/repositories/type/integration/))

For an update, use HACS's offered download/update and restart when requested.
To uninstall, first delete the AlarmMesh entry in **Devices & services**; then
use the repository's **⋮ > Remove** in HACS to remove its downloaded content and
restart HA. Removing a custom-repository listing alone does not remove its files.
([HACS repository dashboard](https://www.hacs.dev/docs/use/repositories/dashboard/))

Do not manage the same files through both installers. Developers can instead
copy the integration into a disposable instance as described in
[development](development.md); that is a separate manual-file installation.

## Configure and check the two overviews

Open **Settings > Devices & services > Add integration > AlarmMesh**. Select one
existing smoke source (`binary_sensor`, device class `smoke`) and submit. Only one
AlarmMesh configuration is supported. No `alarmmesh:` YAML is needed. Open the
entry's two entities:

| Overview | With that source explicitly `off` |
| --- | --- |
| Smoke | `off`, displayed in Dutch as “Niet gedetecteerd”: no smoke reported |
| Source availability | `complete`, “Alle bronnen melden een status” |

An active source yields smoke `on`. An unknown, unreachable or missing source
without another active source yields smoke `unavailable`, never `off`, and
availability `incomplete`. Do not force a real source to test these instructions.
Use **Configure** to inspect or replace the selection. Invalid input or cancelling
keeps the current selection; saved changes reload AlarmMesh. IDs are fixed:
renaming a source requires selecting its new ID yourself. Overview names/IDs
can be customized without changing their identity. See the
[simulated acceptance guide](mvp-acceptance.md) and [passive pilot](read-only-pilot.md).

## Repository metadata and publication boundaries

The supported layout is one self-contained integration in
`custom_components/alarmmesh/`, with root `README.md` and `hacs.json`. The manifest
needs domain/version; HACS additionally requires name, documentation, issue
tracker and code owners. Description, topics, issue access and published GitHub
releases are catalog requirements, not proof that this repository was admitted.
([Official repository requirements](https://contributors.home-assistant.io/marketplace/reference/repository-structure/))

Without a published release, link-based installation can use the default branch's
commit; the installer's revision can differ from the integration's manifest
version `0.0.1`. Record the actual revision, rather than assuming that version
identifies a release. No release or catalog submission is made by this work.
([Official release rules](https://contributors.home-assistant.io/marketplace/guides/releases/))

The minimum remains 2026.10.4; tests separately verify exact 2026.11.1. This is no
claim about every newer version. Licensing, branding and catalog readiness remain
separate owner decisions; see [guidelines](guidelines.md).
