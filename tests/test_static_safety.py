"""Static machine-safety rules over every Python file in the repository (see SAFETY.md).

These fail the build if code appears that could talk to the projector over USB/HID, change LED currents,
open the DMD window or camera outside rig/, or take the rig without releasing it. They are a tripwire for
ordinary code, not a sandbox against deliberate obfuscation."""
import ast
import re
import subprocess
from pathlib import Path

import pytest

from rig.safety import FORBIDDEN_MODULES

REPO = Path(__file__).resolve().parents[1]
RIG = REPO / "rig"
TESTS = REPO / "tests"
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "env", "build", "dist", "site-packages", "runs", "out",
             ".pytest_cache", ".tox", "node_modules"}


def _repo_files():
    """Tracked and untracked-but-not-ignored .py files; outside git, a walk that skips environments and output."""
    try:
        out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "*.py"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout.split()
        if out:
            return sorted(REPO / f for f in out if (REPO / f).exists())
    except (OSError, subprocess.CalledProcessError):
        pass
    return sorted(p for p in REPO.rglob("*.py") if not SKIP_DIRS & set(p.relative_to(REPO).parts))


FILES = _repo_files()
OUTSIDE_RIG = [p for p in FILES if RIG not in p.parents and TESTS not in p.parents]

# Python packages that reach the DLPC350 over USB/HID (pycrafter4500 is the common one)
FORBIDDEN_IMPORTS = {m.split(".")[0] for m in FORBIDDEN_MODULES} | {"pyhid", "hidraw", "easyhid"}
# DLPC350 command ids (DLPU010): LED current, LED enable, display mode, input source, pattern start/stop,
# power control - as one 16-bit literal or as the two bytes the USB drivers send.
DLPC350_COMMANDS = re.compile(r"\b0x(0B01|1A07|1A1B|1A00|1A24|0200)\b"
                              r"|\b0x0?1A\s*,\s*0x(07|1B|00|24)\b|\b0x0B\s*,\s*0x0?1\b", re.I)
LED_NAME = re.compile(r"led_?current|set_?led|led_?enable|ledcurrent", re.I)
WINDOW_CALLS = {"namedWindow", "imshow", "setWindowProperty", "moveWindow"}
DEVICE_CLASSES = {"HDMIWindow", "Camera", "RigLock"}
# Outside rig/: no other route to devices or other programs (process launch, native calls, dynamic imports,
# other display toolkits). Add a narrow exception here, with a reason, if one is ever really needed.
BANNED_MODULES_OUTSIDE_RIG = {"subprocess", "ctypes", "cffi", "importlib", "pygame", "pyglet", "tkinter", "PyQt5",
                              "PyQt6", "PySide2", "PySide6", "wx", "serial", "socket", "PySpin"}
BANNED_CALLS_OUTSIDE_RIG = {"__import__", "system", "startfile", "popen", "spawnl", "spawnv", "execv", "execl"}


def _tree(p):
    return ast.parse(p.read_text(encoding="utf-8-sig"), filename=str(p))


def _rel(p):
    return p.relative_to(REPO).as_posix()


def _name(func):
    return func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield node, a.name, a.asname, None
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for a in node.names:
                yield node, node.module, a.asname, a.name


def test_there_are_files_to_check():
    assert len(FILES) > 40 and any(RIG in p.parents for p in FILES) and len(OUTSIDE_RIG) > 30


@pytest.mark.parametrize("p", FILES, ids=_rel)
def test_no_usb_hid_imports(p):
    for node, mod, _, _ in _imports(_tree(p)):
        assert mod.split(".")[0] not in FORBIDDEN_IMPORTS, f"{_rel(p)}:{node.lineno} imports {mod}: HDMI only"


@pytest.mark.parametrize("p", FILES, ids=_rel)
def test_no_dlpc350_commands_or_led_code(p):
    src = p.read_text(encoding="utf-8-sig")
    m = DLPC350_COMMANDS.search(src)
    assert not m, f"{_rel(p)} contains DLPC350 command id {m.group(0)!r}"
    for node in ast.walk(_tree(p)):
        name = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.Name):
            name = node.id
        if name and LED_NAME.search(name):
            raise AssertionError(f"{_rel(p)}:{node.lineno} '{name}': code must not change LED currents")


@pytest.mark.parametrize("p", OUTSIDE_RIG, ids=_rel)
def test_hardware_only_through_rig(p):
    """Outside rig/ and tests/: no PySpin or other device / process routes, no OpenCV display windows, and the
    device classes are never imported or built directly (only `with Bench(...)` or open_rig())."""
    tree = _tree(p)
    for node, mod, asname, name in _imports(tree):
        assert mod.split(".")[0] not in BANNED_MODULES_OUTSIDE_RIG, f"{_rel(p)}:{node.lineno} imports {mod}"
        if mod.split(".")[0] == "rig":
            assert name not in DEVICE_CLASSES, f"{_rel(p)}:{node.lineno} imports {name}: use rig.bench.Bench"
            assert not (asname and name in ("Bench", "open_rig")), \
                f"{_rel(p)}:{node.lineno} imports {name} as {asname}: keep the name so the checks can see it"
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            n = _name(node.func)
            assert n not in WINDOW_CALLS, f"{_rel(p)}:{node.lineno} calls cv2.{n}: use rig.bench.Bench"
            assert n not in DEVICE_CLASSES, f"{_rel(p)}:{node.lineno} constructs {n}: use rig.bench.Bench"
            assert n not in BANNED_CALLS_OUTSIDE_RIG, f"{_rel(p)}:{node.lineno} calls {n}()"


def _calls(node, name):
    return any(isinstance(n, ast.Call) and _name(n.func) == name for n in ast.walk(node))


def _enclosing_functions(tree):
    """(function or None for module level, call node) for every open_rig() call."""
    found = []

    def visit(node, fn):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child)
            else:
                if isinstance(child, ast.Call) and _name(child.func) == "open_rig":
                    found.append((fn, child))
                visit(child, fn)
    visit(tree, None)
    return found


@pytest.mark.parametrize("p", OUTSIDE_RIG, ids=_rel)
def test_open_rig_is_always_closed_and_released_in_finally(p):
    for fn, call in _enclosing_functions(_tree(p)):
        assert fn is not None, f"{_rel(p)}:{call.lineno} open_rig() at module level"
        ok = any(isinstance(t, ast.Try) and any(_calls(s, "close") for s in t.finalbody)
                 and any(_calls(s, "release") for s in t.finalbody) for t in ast.walk(fn))
        assert ok, f"{_rel(p)}:{fn.lineno} {fn.name}() takes the rig without sync.close() and lock.release() " \
                   "in a finally"


@pytest.mark.parametrize("p", OUTSIDE_RIG, ids=_rel)
def test_bench_is_entered_with_a_context_manager(p):
    """Bench(...) outside rig/ must be used as `with Bench(...)` so the DMD goes dark and the lock is freed."""
    tree = _tree(p)
    with_ctx = {id(i.context_expr) for n in ast.walk(tree) if isinstance(n, (ast.With, ast.AsyncWith))
                for i in n.items}
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _name(n.func) == "Bench":
            assert id(n) in with_ctx, f"{_rel(p)}:{n.lineno} Bench(...) outside a with-statement"
