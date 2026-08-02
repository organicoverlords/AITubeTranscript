from __future__ import annotations

import re
from pathlib import Path

ACTION_USE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def test_github_actions_are_pinned_to_full_commit_shas() -> None:
    roots = [Path(".github/workflows"), Path("templates")]
    violations: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.y*ml")):
            text = path.read_text(encoding="utf-8")
            for target in ACTION_USE.findall(text):
                if target.startswith("./"):
                    continue
                repository, separator, reference = target.rpartition("@")
                if not separator:
                    violations.append(f"{path}: missing ref: {target}")
                    continue
                if repository.startswith("actions/") and not FULL_SHA.fullmatch(reference):
                    violations.append(f"{path}: mutable action ref: {target}")
    assert not violations, "\n" + "\n".join(violations)
