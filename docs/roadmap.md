# Proposed next steps — no implementation authorization

The repo already has extensive source/lifecycle regressions. Hosted a300d39 and
the fresh simulation UI are now verified; see the [current acceptance matrix](acceptance-matrix.md).
The remaining gaps concern installer/backup acceptance, physical observations
and owner release decisions, not another runtime layer.
Each step below requires its own scope approval; none adds preparatory product
code in this review. Exact supported versions stay explicit.

| Step | User goal and exact scope | Dependencies | Acceptance and simulation checks | Separate physical acceptance | Outside the step |
| --- | --- | --- | --- | --- | --- |
| 1. Finish installer/recovery acceptance | Exercise the actual installer and supported HA backup/restore in a disposable instance. Existing UI and hosted a300d39 evidence is complete within its recorded scope. | Separately authorized installer/GitHub session, chosen candidate; fresh hosted run after future reviewed changes. | Install/update/uninstall through the installer; saved selection/custom identity retained and supported backup returns to the recorded state. Existing file-copy tests are supporting evidence only. | None; passive pilot stays separately recorded. | Product changes, catalog submission, release publication, live installation access. |
| 2. Extend the passive pilot record | Record naturally occurring source/overview changes and recovery, with aliases and timestamps; clarify what is actually observed. | Owner observations under the existing passive protocol. | Reports distinguish HA state, upstream availability and unobserved periods; simulation continues to cover precedence and recovery. Never treat a cached off value or self-test as smoke detection proof. | Any manufacturer-prescribed physical test is a separate, explicitly planned activity; no commands supplied here. | Forced smoke, battery removal, MQTT/Zigbee interruption, new thresholds or services. |
| 3. Review a release candidate | Select license/revision/version; perform packaging and installer acceptance in a disposable instance with a backup/rollback record. | Owner legal/release decisions; preceding review evidence. | Full validation on the chosen revision, exactly two entities, preserved options/identity on update, supported removal and backup restoration; no metadata/schema drift. | No additional physical claim; publish only the pilot limits actually supported. | Automatic publication, production deployment and catalog admission. |
| 4. Add one explicit compatibility target | When a specific HA release is requested, verify its APIs and add that exact version after reproducing existing scenarios. | Named version and review of upstream changes. | Existing baseline stays; fresh image/config, version assertion, source/options/reload/unload and image tests pass; failures remain visible independently. | None unless a separate device issue is being investigated. | Arbitrary future-version promises, dependency upgrades without a reason, product features. |
| 5. Decide whether another read-only view is useful | First collect a concrete user problem and design the smallest independently testable read-only improvement; no implementation is included now. | A new feature request with specified display/semantics and acceptance. | A separate proposal must preserve current status rules, identity/schema contracts and failure behavior; define fixtures before changing code. | Explicitly identify whether real observations are needed; simulation is not a substitute. | Sirens, actions, notifications, adapters added speculatively. |

Sirens, notifications or alarm propagation would each need a **new assignment**,
explicit user intent, a dedicated design and independent simulation/physical
acceptance boundaries. No action interface, adapter, capability field or runtime
hook for those proposals is created here.
