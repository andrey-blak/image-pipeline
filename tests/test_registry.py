from dataclasses import dataclass

import pytest

from imgpipe.errors import ConfigError
from imgpipe.steps import REGISTRY, Step, create_step, register


def test_builtin_steps_are_registered():
    assert {"resize", "rnd_saturation", "trim_borders"} <= set(REGISTRY)


def test_create_step_by_name():
    step = create_step("resize", {"size": 300})
    assert type(step) is REGISTRY["resize"]
    assert step.size == 300


def test_unknown_step_lists_known_ones():
    with pytest.raises(ConfigError, match="unknown step 'nope'.*resize.*saturation.*trim_borders"):
        create_step("nope", {})


def test_unknown_option():
    with pytest.raises(ConfigError, match="step 'resize': unknown option.*sizee"):
        create_step("resize", {"size": 1, "sizee": 2})


def test_missing_required_option():
    with pytest.raises(ConfigError, match="step 'resize': missing required option 'size'"):
        create_step("resize", {})


@pytest.mark.parametrize("value", ["300", 3.5, True])
def test_wrong_type_for_int_option(value):
    with pytest.raises(ConfigError, match="option 'size' must be int"):
        create_step("resize", {"size": value})


def test_int_accepted_for_float_option_but_bool_is_not():
    assert create_step("rnd_saturation", {"min_percent": 3, "max_percent": 5}).max_percent == 5
    with pytest.raises(ConfigError, match="must be float"):
        create_step("rnd_saturation", {"min_percent": True, "max_percent": 5})


def test_invalid_value_becomes_config_error():
    with pytest.raises(ConfigError, match="step 'resize'"):
        create_step("resize", {"size": 0})


def test_duplicate_registration_rejected():
    with pytest.raises(ValueError, match="already registered"):

        @register("resize")
        @dataclass
        class Other(Step):
            pass


def test_new_step_can_be_registered_and_removed():
    @register("noop-test")
    @dataclass
    class Noop(Step):
        pass

    try:
        assert isinstance(create_step("noop-test", {}), Noop)
    finally:
        del REGISTRY["noop-test"]
