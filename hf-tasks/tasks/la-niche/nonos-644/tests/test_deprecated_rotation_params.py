import inspect

import pytest

from nonos.api._angle_parsing import _resolve_rotate_by


def _resolve_rotate_by_call(**kwargs):
    signature = inspect.signature(_resolve_rotate_by)
    supported = signature.parameters
    filtered = {key: value for key, value in kwargs.items() if key in supported}
    return _resolve_rotate_by(**filtered)


def test_resolve_rotate_by_error_message_for_conflicting_args():
    with pytest.raises(TypeError) as excinfo:
        _resolve_rotate_by_call(
            rotate_by=0.5,
            rotate_with="planet2.dat",
            planet_number_argument=("planet_corotation", None),
            planet_azimuth_finder=lambda planet_file: 0.0,
            stacklevel=1,
        )

    message = str(excinfo.value)
    assert "rotate_by" in message
    assert "cannot be specified" in message


def test_resolve_rotate_by_rejects_planet_number_argument():
    with pytest.raises(TypeError) as excinfo:
        _resolve_rotate_by(
            rotate_by=None,
            rotate_with=None,
            planet_number_argument=("planet_corotation", 1),
            planet_azimuth_finder=lambda planet_file: 0.0,
            stacklevel=1,
        )

    message = str(excinfo.value)
    assert "planet_number_argument" in message or "planet_corotation" in message
    assert "unexpected" in message or "keyword" in message
