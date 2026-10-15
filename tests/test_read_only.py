"""Trinity is read-only for this app (PRD_shift_guardian.md decision 1, R2): write tools are refused in code."""

import asyncio
import re
from pathlib import Path

import pytest

from notifier.trinity import READ_ONLY_TOOLS, Trinity, TrinityError

WRITE_TOOLS = ["assign_ticket", "assign_team", "update_ticket_status", "set_ticket_level", "add_internal_note",
               "add_ticket_tag", "remove_ticket_tag"]


class Session:
    def __init__(self):
        self.calls = []

    async def call_tool(self, tool, args):
        self.calls.append(tool)
        raise AssertionError("must not reach Trinity")


@pytest.mark.parametrize("tool", WRITE_TOOLS)
def test_write_tools_are_refused_before_reaching_trinity(tool):
    session = Session()
    with pytest.raises(TrinityError, match="only reads"):
        asyncio.run(Trinity(session)._call(tool, {}))
    assert session.calls == []


def test_the_code_only_names_read_tools():
    """Every tool name passed to _call anywhere in the app is on the read-only list."""
    root = Path(__file__).resolve().parent.parent
    used = set()
    for path in [*root.glob("notifier/*.py"), *root.glob("dashboard/*.py"), *root.glob("backend/*.py")]:
        used |= set(re.findall(r"""_call\(\s*["']([a-z_]+)["']""", path.read_text(encoding="utf-8")))
    assert used and used <= READ_ONLY_TOOLS
    assert not used & set(WRITE_TOOLS)
