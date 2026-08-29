"""Composition-aware software-engineering tasks for the harness tournament.

These are deliberately small repositories rather than single edit-format probes.  Each
task requires the loop to understand a behavioural contract, inspect existing code, make
an implementation change, and survive held-out tests.  Verifiers use only Python's
standard library so every configured hardened execution backend can run them offline.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from harness_tasks import HarnessTask, HarnessVerification


def _write(workspace: Path, relative: str, content: str) -> None:
    target = workspace / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dedent(content).lstrip(), encoding="utf-8")


def _verified_elsewhere(workspace: Path, final_summary: str) -> tuple[bool, str]:
    del workspace, final_summary
    return False, "this task requires its isolated held-out verifier"


_LOADER = """
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(sys.argv[1]).resolve()

def load(name, relative):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
"""


def _verification(body: str) -> HarnessVerification:
    return HarnessVerification(
        script=dedent(_LOADER).lstrip() + "\n" + dedent(body).lstrip()
    )


def _setup_empty_mean(workspace: Path) -> None:
    _write(
        workspace,
        "stats.py",
        """
        def mean(values):
            # Return the arithmetic mean of a finite iterable of numbers.
            values = list(values)
            return sum(values) / len(values)
        """,
    )
    _write(workspace, "README.md", """# Tiny stats library\n\n`stats.mean` is public API.\n""")


def _setup_slugify(workspace: Path) -> None:
    _write(
        workspace,
        "text_utils.py",
        """
        import re

        def title_case(value):
            return " ".join(part.capitalize() for part in value.split())
        """,
    )


def _setup_config_precedence(workspace: Path) -> None:
    _write(
        workspace,
        "config.py",
        """
        DEFAULTS = {"host": "127.0.0.1", "port": 8000, "debug": False}

        def resolve_config(file_values=None, environ=None):
            # Environment keys use APP_<NAME>.
            file_values = file_values or {}
            environ = environ or {}
            result = dict(DEFAULTS)
            result.update(file_values)
            for key in DEFAULTS:
                env_key = f"APP_{key.upper()}"
                if env_key in environ:
                    result[key] = environ[env_key]
            return result
        """,
    )


def _setup_cross_file_contract(workspace: Path) -> None:
    _write(
        workspace,
        "repository.py",
        """
        USERS = {1: {"first_name": "Ada", "last_name": "Lovelace"}}

        def get_user(user_id):
            return USERS.get(user_id)
        """,
    )
    _write(
        workspace,
        "service.py",
        """
        from repository import get_user

        def greeting(user_id):
            user = get_user(user_id)
            if user is None:
                return "Welcome, guest!"
            return f"Welcome, {user['first_name']}!"
        """,
    )


def _setup_cache_collision(workspace: Path) -> None:
    _write(
        workspace,
        "cache.py",
        """
        class ResultCache:
            def __init__(self):
                self._values = {}

            def _key(self, namespace, item_id):
                return f"{namespace}{item_id}"

            def put(self, namespace, item_id, value):
                self._values[self._key(namespace, item_id)] = value

            def get(self, namespace, item_id):
                return self._values.get(self._key(namespace, item_id))
        """,
    )


def _setup_safe_join(workspace: Path) -> None:
    _write(
        workspace,
        "paths.py",
        """
        from pathlib import Path

        def safe_join(root, user_path):
            # Resolve below root, raising ValueError if the path escapes.
            return Path(root) / user_path
        """,
    )


def _setup_pagination(workspace: Path) -> None:
    _write(
        workspace,
        "pagination.py",
        """
        def page(items, page_number, page_size):
            # Return one 1-based page as a new list.
            start = page_number * page_size
            return list(items[start:start + page_size])
        """,
    )


def _setup_jsonl_reader(workspace: Path) -> None:
    _write(
        workspace,
        "events.py",
        """
        import json

        def read_events(path):
            # Yield decoded JSON objects from a UTF-8 JSONL file.
            with open(path, encoding="utf-8") as stream:
                for line in stream:
                    yield json.loads(line)
        """,
    )


_MUTATION_GRANTS = (("write", "workspace"), ("execute", "workspace"))


SOFTWARE_ENGINEERING_TASKS: list[HarnessTask] = [
    HarnessTask(
        id="swe-empty-mean",
        category="bug_fix",
        objective_template=(
            "Fix the tiny repository in {workspace}. stats.mean must continue to accept any "
            "finite iterable, but an empty iterable must return 0 instead of raising. Preserve "
            "the public function name and do not add dependencies."
        ),
        setup=_setup_empty_mean,
        check=_verified_elsewhere,
        max_steps=12,
        required_grants=_MUTATION_GRANTS,
        verification=_verification(
            """
            stats = load("candidate_stats", "stats.py")
            assert stats.mean([]) == 0
            assert stats.mean(iter(())) == 0
            assert stats.mean([2, 4, 9]) == 5
            assert stats.mean(x for x in [1.5, 2.5]) == 2.0
            print("empty mean contract passed")
            """
        ),
    ),
    HarnessTask(
        id="swe-add-slugify",
        category="feature",
        objective_template=(
            "Add slugify(value) to text_utils.py in {workspace}. It must lowercase Unicode "
            "text, transliterate common accented Latin characters to ASCII, replace every "
            "run of non-alphanumeric characters with one hyphen, and strip edge hyphens. "
            "Existing title_case behaviour must remain unchanged; use only the standard library."
        ),
        setup=_setup_slugify,
        check=_verified_elsewhere,
        max_steps=16,
        required_grants=_MUTATION_GRANTS,
        verification=_verification(
            """
            mod = load("candidate_text_utils", "text_utils.py")
            assert mod.title_case("hello world") == "Hello World"
            assert mod.slugify("  Hello, World!  ") == "hello-world"
            assert mod.slugify("Caf\u00e9 d\u00e9j\u00e0 vu") == "cafe-deja-vu"
            assert mod.slugify("one___two / three") == "one-two-three"
            assert mod.slugify("") == ""
            print("slugify contract passed")
            """
        ),
    ),
    HarnessTask(
        id="swe-config-precedence",
        category="debugging",
        objective_template=(
            "Repair resolve_config in {workspace}/config.py. Precedence must be environment "
            "over file values over defaults. APP_PORT must become int; APP_DEBUG must accept "
            "case-insensitive true/false, 1/0, yes/no and on/off and raise ValueError for any "
            "other value. Do not mutate DEFAULTS or caller dictionaries."
        ),
        setup=_setup_config_precedence,
        check=_verified_elsewhere,
        max_steps=18,
        required_grants=_MUTATION_GRANTS,
        verification=_verification(
            """
            mod = load("candidate_config", "config.py")
            file_values = {"host": "file", "port": 9000, "debug": True}
            env = {"APP_HOST": "env", "APP_PORT": "7001", "APP_DEBUG": "off"}
            got = mod.resolve_config(file_values, env)
            assert got == {"host": "env", "port": 7001, "debug": False}
            assert file_values == {"host": "file", "port": 9000, "debug": True}
            assert mod.DEFAULTS == {"host": "127.0.0.1", "port": 8000, "debug": False}
            for raw, expected in [("TRUE", True), ("yes", True), ("1", True), ("On", True),
                                  ("false", False), ("NO", False), ("0", False)]:
                assert mod.resolve_config(environ={"APP_DEBUG": raw})["debug"] is expected
            try:
                mod.resolve_config(environ={"APP_DEBUG": "maybe"})
            except ValueError:
                pass
            else:
                raise AssertionError("invalid APP_DEBUG must raise ValueError")
            print("configuration contract passed")
            """
        ),
    ),
    HarnessTask(
        id="swe-cross-file-greeting",
        category="multi_file_change",
        objective_template=(
            "Change the repository in {workspace} so repository.get_user returns a User "
            "dataclass (or None) instead of a dictionary, and update service.greeting to use "
            "that typed contract. Preserve the exact greeting outputs and do not duplicate "
            "the user data or lookup logic in service.py."
        ),
        setup=_setup_cross_file_contract,
        check=_verified_elsewhere,
        max_steps=20,
        required_grants=_MUTATION_GRANTS,
        verification=_verification(
            """
            sys.path.insert(0, str(ROOT))
            repo = load("repository", "repository.py")
            service = load("candidate_service", "service.py")
            user = repo.get_user(1)
            assert user is not None
            assert user.first_name == "Ada" and user.last_name == "Lovelace"
            assert not isinstance(user, dict)
            assert service.greeting(1) == "Welcome, Ada!"
            assert service.greeting(999) == "Welcome, guest!"
            assert "USERS" not in vars(service)
            print("cross-file typed contract passed")
            """
        ),
    ),
    HarnessTask(
        id="swe-cache-key-collision",
        category="bug_fix",
        objective_template=(
            "Fix ResultCache in {workspace}/cache.py. Its current key construction aliases "
            "different (namespace, item_id) pairs such as ('ab', '12') and ('ab1', '2'). "
            "Make keys collision-safe for arbitrary string values while preserving put/get "
            "and the ability to retrieve values written before subsequent puts."
        ),
        setup=_setup_cache_collision,
        check=_verified_elsewhere,
        max_steps=14,
        required_grants=_MUTATION_GRANTS,
        verification=_verification(
            """
            mod = load("candidate_cache", "cache.py")
            cache = mod.ResultCache()
            pairs = [("ab", "12"), ("ab1", "2"), ("", "x"), ("x", ""), ("a:b", "c")]
            for index, pair in enumerate(pairs):
                cache.put(*pair, {"index": index})
            for index, pair in enumerate(pairs):
                assert cache.get(*pair) == {"index": index}
            assert cache.get("missing", "key") is None
            print("cache collision contract passed")
            """
        ),
    ),
    HarnessTask(
        id="swe-safe-join",
        category="security",
        objective_template=(
            "Harden safe_join in {workspace}/paths.py. It must return a resolved Path only "
            "when user_path stays beneath root. Reject absolute paths, '..' traversal, sibling "
            "prefix tricks, and symlink escapes with ValueError. Existing descendants, including "
            "a path equal to root after normalization, remain valid."
        ),
        setup=_setup_safe_join,
        check=_verified_elsewhere,
        max_steps=20,
        required_grants=_MUTATION_GRANTS,
        verification=_verification(
            """
            import tempfile
            mod = load("candidate_paths", "paths.py")
            with tempfile.TemporaryDirectory() as temp:
                base = pathlib.Path(temp)
                root = base / "root"
                root.mkdir()
                (root / "child").mkdir()
                outside = base / "outside"
                outside.mkdir()
                assert mod.safe_join(root, "child/file.txt") == (root / "child/file.txt").resolve()
                assert mod.safe_join(root, "child/..") == root.resolve()
                bad = ["../outside/x", str(outside / "x"), "../../rootish/x"]
                for value in bad:
                    try:
                        mod.safe_join(root, value)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError(f"escape accepted: {value}")
                try:
                    (root / "link").symlink_to(outside, target_is_directory=True)
                except OSError:
                    pass
                else:
                    try:
                        mod.safe_join(root, "link/secret")
                    except ValueError:
                        pass
                    else:
                        raise AssertionError("symlink escape accepted")
            print("safe path contract passed")
            """
        ),
    ),
    HarnessTask(
        id="swe-pagination-boundaries",
        category="bug_fix",
        objective_template=(
            "Repair page() in {workspace}/pagination.py. page_number is 1-based. Return a "
            "new list for valid positive page_number/page_size values, including [] beyond "
            "the end. Raise ValueError when either number is zero, negative, non-integer, or bool."
        ),
        setup=_setup_pagination,
        check=_verified_elsewhere,
        max_steps=16,
        required_grants=_MUTATION_GRANTS,
        verification=_verification(
            """
            mod = load("candidate_pagination", "pagination.py")
            items = list(range(7))
            assert mod.page(items, 1, 3) == [0, 1, 2]
            assert mod.page(items, 2, 3) == [3, 4, 5]
            assert mod.page(items, 3, 3) == [6]
            assert mod.page(items, 4, 3) == []
            for args in [(0, 2), (-1, 2), (1, 0), (1, -2), (1.0, 2), (True, 2), (1, False)]:
                try:
                    mod.page(items, *args)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"invalid pagination accepted: {args}")
            print("pagination contract passed")
            """
        ),
    ),
    HarnessTask(
        id="swe-jsonl-resilience",
        category="robustness",
        objective_template=(
            "Improve read_events in {workspace}/events.py. Ignore blank or whitespace-only "
            "lines, keep streaming (do not read the whole file), and when JSON is malformed "
            "raise ValueError that includes the 1-based physical line number while preserving "
            "the original JSON error as the exception cause. Use only the standard library."
        ),
        setup=_setup_jsonl_reader,
        check=_verified_elsewhere,
        max_steps=18,
        required_grants=_MUTATION_GRANTS,
        verification=_verification(
            """
            import json
            import tempfile
            mod = load("candidate_events", "events.py")
            with tempfile.TemporaryDirectory() as temp:
                path = pathlib.Path(temp) / "events.jsonl"
                path.write_text('{"id": 1}\\n  \\n{"id": 2}\\n', encoding="utf-8")
                stream = mod.read_events(path)
                assert iter(stream) is stream
                assert list(stream) == [{"id": 1}, {"id": 2}]
                path.write_text('{"ok": true}\\n\\nnot-json\\n', encoding="utf-8")
                try:
                    list(mod.read_events(path))
                except ValueError as exc:
                    assert "3" in str(exc)
                    assert isinstance(exc.__cause__, json.JSONDecodeError)
                else:
                    raise AssertionError("malformed JSON did not raise ValueError")
            print("JSONL resilience contract passed")
            """
        ),
    ),
]
