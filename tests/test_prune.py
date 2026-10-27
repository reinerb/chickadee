import argparse

import pytest

from chickadee.prune import positive_int


def test_zero_days_is_rejected():
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("0")
