import argparse

import pytest

from content_monitor.prune import positive_int


def test_zero_days_is_rejected():
    with pytest.raises(argparse.ArgumentTypeError):
        positive_int("0")
