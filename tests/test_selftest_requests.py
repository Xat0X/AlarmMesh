"""Request ownership regressions with actual HA fixtures and mock buttons only."""

import asyncio
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from test_incident_features import add_test_device, setup
from test_incident_features import catalog_devices as catalog_devices

from homeassistant.core import Event, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.alarmmesh import self_test


async def prepare(hass, catalog_devices, *, halo=False):
    add, calls = catalog_devices
    d = (
        add_test_device(add, "HALO", "Halo Smart Labs")
        if halo
        else add_test_device(add)
    )
    entry = await setup(hass, [d["source"]])
    runner = entry.runtime_data.panel.selftests
    return d, calls, entry, runner


async def queue_request(hass, entry, runner, d, **kwargs):
    for _ in range(8):
        await entry.runtime_data.panel.linking._semaphore.acquire()
    task = asyncio.create_task(
        runner.start(
            d["source"],
            runner.resolve(d["source"])["identity"],
            True,
            request_id=uuid4().hex,
            **kwargs,
        )
    )
    await hass.async_block_till_done()
    return task


def release_slots(entry):
    for _ in range(8):
        entry.runtime_data.panel.linking._semaphore.release()


async def test_expired_queued_request_cannot_borrow_new_confirmation(
    hass, catalog_devices
):
    """Independent review reproduction: A expires, only confirmed B may dispatch."""
    add, calls = catalog_devices
    d = add_test_device(add)

    async def press(call):
        calls.append(dict(call.data))

    hass.services.async_register("button", "press", press)
    entry = await setup(hass, [d["source"]])
    panel = entry.runtime_data.panel
    runner = panel.selftests
    for _ in range(8):
        await panel.linking._semaphore.acquire()
    identity = runner.resolve(d["source"])["identity"]
    old_id, new_id = uuid4().hex, uuid4().hex
    old = asyncio.create_task(
        runner.start(d["source"], identity, True, request_id=old_id)
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
    await hass.async_block_till_done()
    assert runner.record["status"] == "outcome_unknown"
    newer = asyncio.create_task(
        runner.start(d["source"], identity, True, request_id=new_id)
    )
    await hass.async_block_till_done()
    assert runner.record["request_id"] == new_id
    assert runner.record["status"] == "sending"
    panel.linking._semaphore.release()
    try:
        old_result = await old
    finally:
        for _ in range(7):
            panel.linking._semaphore.release()
        new_result = await newer
    assert len(calls) == 1, f"Only B may dispatch; observed {len(calls)} calls"
    assert old_result["request_id"] == old_id
    assert old_result["status"] == "outcome_unknown"
    assert new_result["request_id"] == new_id
    assert new_result["status"] == "request_sent"
    assert runner.record == new_result


async def test_deadline_blocks_dispatch_even_before_timeout_callback_runs(
    hass, catalog_devices, freezer
):
    d, calls, entry, runner = await prepare(hass, catalog_devices)

    async def press(call):
        calls.append(dict(call.data))

    hass.services.async_register("button", "press", press)
    # Deliberately delayed callback: the dispatch gate must check the deadline too.
    with patch.object(self_test, "async_call_later", return_value=lambda: None):
        old = await queue_request(hass, entry, runner, d)
    freezer.move_to(dt_util.utcnow() + timedelta(seconds=121))
    assert runner.record["status"] == "sending"
    release_slots(entry)
    result = await old
    assert not calls
    assert result["status"] == "outcome_unknown"
    assert await runner.store.async_load() == result


@pytest.mark.parametrize("completion", ["success", "failure", "cancel"])
async def test_late_dispatch_completion_cannot_modify_or_return_successor(
    hass, catalog_devices, completion
):
    d, calls, entry, runner = await prepare(hass, catalog_devices, halo=True)
    entered, finish = asyncio.Event(), asyncio.Event()
    original = hass.services.async_call

    async def mock_call(_registry, domain, service, data, **kwargs):
        if (domain, service) != ("select", "select_option"):
            return await original(domain, service, data, **kwargs)
        assert data == {"entity_id": d["test_target"], "option": "start"}
        calls.append(dict(data))
        if len(calls) == 1:
            entered.set()
            try:
                await finish.wait()
            except asyncio.CancelledError:
                # Model a provider that ignores the initial service timeout.
                # A must remain harmless even if that call really returns late.
                await finish.wait()
            if completion == "failure":
                raise RuntimeError("Deliberate mock late failure")

    identity = runner.resolve(d["source"])["identity"]
    a_id, b_id = uuid4().hex, uuid4().hex
    with patch.object(type(hass.services), "async_call", new=mock_call):
        old = asyncio.create_task(
            runner.start(d["source"], identity, True, request_id=a_id)
        )
        await entered.wait()
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
        await hass.async_block_till_done()
        assert runner.record["status"] == "outcome_unknown"
        assert not old.done()
        newer = await runner.start(d["source"], identity, True, request_id=b_id)
        assert newer["status"] == "request_sent"
        assert (
            len(calls) == 2
        )  # A really dispatched before expiry; B is separately confirmed.
        before = deepcopy(runner.record)
        if completion == "cancel":
            old.cancel()
            with pytest.raises(asyncio.CancelledError):
                await old
        else:
            finish.set()
            result = await old
            assert result["request_id"] == a_id
            assert result["status"] == "outcome_unknown"
        assert runner.record == before
        assert await runner.store.async_load() == before
        # Old cleanup must not detach B's observation subscription or timer.
        hass.states.async_set(d["result"], "running")
        await hass.async_block_till_done()
        assert runner.record["status"] == "test_active"
        hass.states.async_set(d["result"], "success")
        await hass.async_block_till_done()
        assert runner.record["status"] == "device_success"
        assert runner.record["request_id"] == b_id
        assert await runner.store.async_load() == runner.record


async def test_old_callbacks_and_deferred_save_cannot_touch_new_request(
    hass, catalog_devices
):
    d, calls, entry, runner = await prepare(hass, catalog_devices)
    observers, timers = [], []
    track, later = self_test.async_track_state_change_event, self_test.async_call_later

    def subscribe(hass, entities, action):
        observers.append(action)
        return track(hass, entities, action)

    def timer(hass, seconds, action):
        timers.append(action)
        return later(hass, seconds, action)

    async def press(call):
        calls.append(dict(call.data))

    hass.services.async_register("button", "press", press)
    with (
        patch.object(
            self_test, "async_track_state_change_event", side_effect=subscribe
        ),
        patch.object(self_test, "async_call_later", side_effect=timer),
    ):
        old = await queue_request(hass, entry, runner, d)
        old_context = runner._request
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
        await hass.async_block_till_done()
        new_id = uuid4().hex
        newer = asyncio.create_task(
            runner.start(
                d["source"],
                runner.resolve(d["source"])["identity"],
                True,
                request_id=new_id,
            )
        )
        await hass.async_block_till_done()
    before = deepcopy(runner.record)
    with patch.object(
        runner.store, "async_save", wraps=runner.store.async_save
    ) as save:
        timers[0](None)
        observers[0](
            Event(
                "state_changed",
                {"entity_id": d["flag"], "new_state": State(d["flag"], "on")},
            )
        )
        await runner._save(old_context)  # Already queued by A, acquired after B.
        await hass.async_block_till_done()
        save.assert_not_called()
        assert runner.record == before
    release_slots(entry)
    old_result, newer_result = await asyncio.gather(old, newer)
    assert old_result["status"] == "outcome_unknown"
    assert newer_result["request_id"] == new_id
    assert len(calls) == 1
    # B's own timer still works after all late A callbacks/finally blocks.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=122))
    await hass.async_block_till_done()
    assert runner.record["status"] == "outcome_unknown"
    assert runner.record["request_id"] == new_id


@pytest.mark.parametrize("change", ["identity", "admin"])
async def test_waiting_request_rechecks_identity_and_admin_before_dispatch(
    hass, catalog_devices, change
):
    d, calls, entry, runner = await prepare(hass, catalog_devices)
    authorized = True

    async def press(call):
        calls.append(dict(call.data))

    hass.services.async_register("button", "press", press)
    task = await queue_request(hass, entry, runner, d, authorized=lambda: authorized)
    if change == "identity":
        er.async_get(hass).async_update_entity(
            d["test_target"], new_unique_id="replacement"
        )
    else:
        authorized = False
    await hass.async_block_till_done()
    release_slots(entry)
    result = await task
    assert not calls and result["status"] == "outcome_unknown"
    assert await runner.store.async_load() == result


@pytest.mark.parametrize("lifecycle", ["reload", "unload"])
@pytest.mark.parametrize("phase", ["queued", "dispatching"])
async def test_lifecycle_drains_owned_requests_without_stale_watches(
    hass, catalog_devices, lifecycle, phase
):
    d, calls, entry, runner = await prepare(hass, catalog_devices)
    entered, finish = asyncio.Event(), asyncio.Event()
    original = hass.services.async_call

    async def mock_call(_registry, domain, service, data, **kwargs):
        if (domain, service) != ("button", "press"):
            return await original(domain, service, data, **kwargs)
        calls.append(dict(data))
        entered.set()
        await finish.wait()

    with patch.object(type(hass.services), "async_call", new=mock_call):
        hass.services.async_register("button", "press", lambda _call: None)
        if phase == "queued":
            task = await queue_request(hass, entry, runner, d)
        else:
            task = asyncio.create_task(
                runner.start(
                    d["source"],
                    runner.resolve(d["source"])["identity"],
                    True,
                    request_id=uuid4().hex,
                )
            )
            await entered.wait()
        saved_id = runner.record["request_id"]
        if lifecycle == "reload":
            assert await hass.config_entries.async_reload(entry.entry_id)
        else:
            assert await hass.config_entries.async_unload(entry.entry_id)
        with pytest.raises(asyncio.CancelledError):
            await task
        assert runner.closed and not runner.requests and not runner.tasks
        assert runner.record["status"] == "outcome_unknown"
        assert runner._request.unsubscribe is runner._request.cancel_timer is None
        assert len(calls) == (phase == "dispatching")
        before = deepcopy(runner.record)
        hass.states.async_set(d["flag"], "on")
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=121))
        await hass.async_block_till_done()
        assert runner.record == before
        if lifecycle == "reload":
            restored = entry.runtime_data.panel.selftests
            assert restored is not runner
            assert restored.record["request_id"] == saved_id
            assert restored.record["status"] == "outcome_unknown"
            assert await restored.store.async_load() == restored.record
