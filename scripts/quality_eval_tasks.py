"""A small, deliberately deterministic quality-evaluation task suite.

Answers F-005's "requires_quality_eval": throughput alone (benchmark_brains.py) says
nothing about whether a candidate brain can actually do the work. This suite trades scale
for certainty -- every task is graded by a programmatic check, never an LLM judge, matching
the project's own principle that "deterministic code runs before both whenever a
deterministic solution exists" (docs/ARCHITECTURE.md). A handful of tasks graded exactly
beats a large set graded approximately for deciding which of a small number of candidates
is the deep brain.

Each Task's `check(completion)` returns (passed: bool, detail: str) so a failure is
diagnosable, not just a number.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    id: str
    category: str
    prompt: str
    check: Callable[[str], tuple[bool, str]]
    max_tokens: int = 512


def _extract_code_block(completion: str) -> str | None:
    """Pull the first fenced code block, or fall back to the whole reply if it looks like
    bare code (no fences at all, common with smaller/less chat-tuned models)."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", completion, re.DOTALL)
    if match:
        return match.group(1)
    if "def " in completion and "```" not in completion:
        return completion
    return None


def _run_python(code: str, harness: str, timeout: float = 10.0) -> tuple[bool, str]:
    """Execute model-produced code plus a test harness in a separate process.

    Isolation note, stated honestly: this is a subprocess with a timeout, not a sandbox.
    It is adequate for benchmarking our own crafted, non-adversarial prompts against a
    small number of trusted candidate models on a local machine -- it is NOT the boundary
    this project would use for arbitrary untrusted code (that is ExecutionBroker, backed by
    OpenShell/Docker, used by the agent loop's run_command tool). Wiring this benchmark
    through ExecutionBroker instead is a reasonable future improvement, not done here to
    keep this suite runnable without a registered workspace.
    """
    full_source = f"{code}\n\n{harness}\n"
    try:
        result = subprocess.run(
            [sys.executable, "-c", full_source],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, "timed out"
    if result.returncode != 0:
        return False, f"exit {result.returncode}: {result.stderr.strip()[-500:]}"
    return True, result.stdout.strip()


def _check_is_palindrome(completion: str) -> tuple[bool, str]:
    code = _extract_code_block(completion)
    if code is None:
        return False, "no code found in reply"
    harness = """
cases = [("racecar", True), ("A man a plan a canal Panama", True), ("hello", False), ("", True)]
for s, expected in cases:
    got = is_palindrome(s)
    assert got == expected, f"is_palindrome({s!r}) = {got!r}, expected {expected!r}"
print("ALL_PASSED")
"""
    ok, detail = _run_python(code, harness)
    return (ok and "ALL_PASSED" in detail), detail


def _check_fix_off_by_one(completion: str) -> tuple[bool, str]:
    code = _extract_code_block(completion)
    if code is None:
        return False, "no code found in reply"
    harness = """
assert sum_range(1, 5) == 15, f"sum_range(1,5) = {sum_range(1, 5)}, expected 15"
assert sum_range(1, 1) == 1, f"sum_range(1,1) = {sum_range(1, 1)}, expected 1"
assert sum_range(3, 3) == 3, f"sum_range(3,3) = {sum_range(3, 3)}, expected 3"
print("ALL_PASSED")
"""
    ok, detail = _run_python(code, harness)
    return (ok and "ALL_PASSED" in detail), detail


def _check_numeric_answer(expected: int) -> Callable[[str], tuple[bool, str]]:
    def check(completion: str) -> tuple[bool, str]:
        numbers = re.findall(r"-?\d+", completion.replace(",", ""))
        if not numbers:
            return False, "no number found in reply"
        # The final number in the reply is taken as the answer -- matches how these
        # prompts are phrased ("...what is the total?") and tolerates working shown first.
        got = int(numbers[-1])
        return got == expected, f"got {got}, expected {expected}"

    return check


def _check_exact_bullet_count(n: int) -> Callable[[str], tuple[bool, str]]:
    def check(completion: str) -> tuple[bool, str]:
        bullets = [
            line for line in completion.splitlines()
            if line.strip().startswith(("-", "*", "•"))
        ]
        return len(bullets) == n, f"found {len(bullets)} bullet lines, expected {n}"

    return check


TASKS: list[Task] = [
    Task(
        id="coding-palindrome",
        category="coding",
        prompt=(
            "Write a Python function `def is_palindrome(s: str) -> bool` that returns "
            "True if s reads the same forwards and backwards, ignoring case, spaces and "
            "punctuation. Reply with only the function in a python code block."
        ),
        check=_check_is_palindrome,
    ),
    Task(
        id="coding-fix-off-by-one",
        category="coding",
        prompt=(
            "This function has an off-by-one bug -- it should sum all integers from `a` "
            "to `b` inclusive, but excludes `b`:\n\n"
            "```python\ndef sum_range(a: int, b: int) -> int:\n"
            "    total = 0\n    for i in range(a, b):\n        total += i\n"
            "    return total\n```\n\n"
            "Reply with only the corrected function in a python code block."
        ),
        check=_check_fix_off_by_one,
    ),
    Task(
        id="reasoning-multi-step",
        category="reasoning",
        prompt=(
            "A warehouse has 84 boxes. Each box holds 12 items. 3 boxes are damaged and "
            "discarded entirely. Of the remaining items, 15% are defective and removed. "
            "How many usable items are left? Show your work, then give the final number "
            "as the very last thing in your reply."
        ),
        check=_check_numeric_answer(int((84 - 3) * 12 * 0.85)),
    ),
    Task(
        id="reasoning-simple-arithmetic",
        category="reasoning",
        prompt=(
            "If a train travels at 60 km/h for 2.5 hours, then at 80 km/h for 1.5 hours, "
            "how many total kilometers did it travel? Show your work, then give the final "
            "number as the very last thing in your reply."
        ),
        check=_check_numeric_answer(int(60 * 2.5 + 80 * 1.5)),
    ),
    Task(
        id="instruction-following-bullets",
        category="instruction_following",
        prompt=(
            "List exactly 3 advantages of running AI models locally instead of via a cloud "
            "API. Reply with exactly 3 bullet points (using '-'), nothing else -- no "
            "introduction, no summary, no numbering."
        ),
        check=_check_exact_bullet_count(3),
        max_tokens=200,
    ),
]
