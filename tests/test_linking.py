"""Incident decisions are pure; only explicit off clears a remembered source."""

from custom_components.alarmmesh.linking import plan_activations, update_incidents
from custom_components.alarmmesh.status import SourceStatus as S


def group(members, target, enabled=True):
    return {
        "members": members,
        "linking": {
            "enabled": enabled,
            "bindings": [
                {
                    "source": "b",
                    "target": target,
                    "profile": "example",
                    "identity": "identity",
                }
            ],
        },
    }


def test_independent_sources_survive_unknown_unreachable_and_missing():
    active = {"a", "b"}
    for bad in (S.UNKNOWN, S.UNREACHABLE, S.MISSING):
        assert update_incidents(
            active,
            {"a": S.SMOKE_REPORTED, "b": S.SMOKE_REPORTED},
            {"a": S.NO_SMOKE_REPORTED, "b": bad},
            set(),
        ) == {"b"}
    assert update_incidents({"b"}, {}, {"b": S.NO_SMOKE_REPORTED}, set()) == set()


def test_test_on_is_not_replayed_when_test_flag_clears():
    assert update_incidents(set(), {}, {"a": S.SMOKE_REPORTED}, {"a"}) == set()
    assert (
        update_incidents(set(), {"a": S.SMOKE_REPORTED}, {"a": S.SMOKE_REPORTED}, set())
        == set()
    )
    assert update_incidents(set(), {}, {"a": S.SMOKE_REPORTED}, set()) == {"a"}


def test_overlaps_union_origins_but_never_activate_a_local_smoke_source():
    groups = [group(["a", "b"], "command"), group(["c", "b"], "command")]
    actions = plan_activations({"a", "c"}, groups)
    assert len(actions) == 1 and actions[0].origins == {"a", "c"}
    assert plan_activations({"a", "b", "c"}, groups) == ()
    assert plan_activations({"a"}, [group(["a", "b"], "command", False)]) == ()


def test_conflicting_identities_do_not_select_an_arbitrary_target():
    first = group(["a", "b"], "command")
    second = group(["a", "b"], "command")
    second["linking"]["bindings"][0]["identity"] = "different"
    assert plan_activations({"a"}, [first, second, first]) == ()
