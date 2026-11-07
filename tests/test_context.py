import random

from imgpipe.steps import Context


def test_record_stores_change():
    ctx = Context(rng=random.Random(1))
    ctx.record("saturation", "+4.0%")
    assert ctx.changes == {"saturation": "+4.0%"}


def test_recording_same_key_again_appends():
    ctx = Context(rng=random.Random(1))
    ctx.record("saturation", "+4.0%")
    ctx.record("saturation", "+3.2%")
    ctx.record("other", "x")
    assert ctx.changes == {"saturation": "+4.0%, +3.2%", "other": "x"}


def test_contexts_do_not_share_changes():
    first, second = Context(rng=random.Random(1)), Context(rng=random.Random(1))
    first.record("a", "1")
    assert second.changes == {}
