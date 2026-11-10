import re
from pathlib import Path

import pytest

from chickadee.cli import COMMANDS

WORKFLOWS = sorted((Path(__file__).parents[1] / ".github" / "workflows").glob("*.yml"))
RUNS = re.compile(r"uv run chickadee ([\w-]+)")


def test_workflows_are_found():
    assert WORKFLOWS


@pytest.mark.parametrize("workflow", WORKFLOWS, ids=lambda path: path.name)
def test_workflows_run_real_commands(workflow: Path):
    for command in RUNS.findall(workflow.read_text()):
        assert command in COMMANDS, f"{workflow.name} runs '{command}'"
