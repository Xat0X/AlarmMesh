"""Pure incident and activation planning, separate from smoke interpretation."""

from dataclasses import dataclass

from .status import SourceStatus


def update_incidents(
    active: set[str],
    previous: dict[str, SourceStatus],
    current: dict[str, SourceStatus],
    tests: set[str],
) -> set[str]:
    """Only a new smoke report starts; only explicit off clears. No restored truth."""
    result = active & current.keys()
    for source, status in current.items():
        if status is SourceStatus.NO_SMOKE_REPORTED:
            result.discard(source)
        elif (
            status is SourceStatus.SMOKE_REPORTED
            and previous.get(source) is not status
            and source not in tests
        ):
            result.add(source)
    return result


@dataclass(frozen=True)
class Activation:
    binding: dict
    origins: frozenset[str]


def plan_activations(active: set[str], groups: list[dict]) -> tuple[Activation, ...]:
    """Union overlapping groups, excluding each locally alarming target itself."""
    targets: dict[str, Activation] = {}
    ambiguous = set()
    for group in groups:
        linking = group.get("linking", {})
        if not linking.get("enabled"):
            continue
        origins = active.intersection(group["members"])
        for binding in linking.get("bindings", ()):
            if not origins or binding["source"] in active:
                continue
            key = binding["target"]
            if key in ambiguous:
                continue
            old = targets.get(key)
            # Conflicting persisted identities are never arbitrarily selected.
            if old and old.binding != binding:
                targets.pop(key)
                ambiguous.add(key)
                continue
            targets[key] = Activation(
                binding, frozenset(origins | (old.origins if old else set()))
            )
    return tuple(targets[key] for key in sorted(targets))
