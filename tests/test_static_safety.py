"""Static machine-safety rules over every Python file in the repository (see SAFETY.md).

These fail the build if code appears that could talk to the projector over USB/HID, change LED currents,
open the DMD window or camera outside rig/, or take the rig without releasing it."""
import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FILES = sorted(p for p in REPO.rglob("*.py") if ".git" not in p.parts and "__pycache__" not in p.parts)
RIG = REPO / "rig"

# Python packages that reach the DLPC350 over USB/HID (pycrafter4500 is the common one)
FORBIDDEN_IMPORTS = {"hid", "hidapi", "usb", "pyusb", "pywinusb", "pycrafter4500", "dmd_control", "libusb",
                     "libusb1", "usb1"}
# DLPC350 command ids (DLPU010): LED current, LED enable, display mode, input source, pattern start/stop,
# power control. None of them belongs in this code base.
DLPC350_COMMANDS = re.compile(r"\b0x(0B01|1A07|1A1B|1A00|1A24|0200)\b", re.I)
LED_NAME = re.compile(r"led_?current|set_?led|led_?enable|ledcurrent", re.I)
WINDOW_CALLS = {"namedWindow", "imshow", "setWindowProperty", "moveWindow"}


def _tree(p):
    return ast.parse(p.read_text(encoding="utf-8-sig"), filename=str(p))


def _rel(p):
    return p.relative_to(REPO).as_posix()


def _in_rig(p):
    return RIG in p.parents


def test_there_are_files_to_check():
    assert len(FILES) > 40 and any(_in_rig(p) for p in FILES)


@pytest.mark.parametrize("p", FILES, ids=_rel)
def test_no_usb_hid_imports(p):
    for node in ast.walk(_tree(p)):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        for n in names:
            assert n.split(".")[0] not in FORBIDDEN_IMPORTS, f"{_rel(p)} imports {n}: HDMI only, no USB/HID"


@pytest.mark.parametrize("p", FILES, ids=_rel)
def test_no_dlpc350_commands_or_led_code(p):
    src = p.read_text(encoding="utf-8-sig")
    m = DLPC350_COMMANDS.search(src)
    assert not m, f"{_rel(p)} contains DLPC350 command id {m.group(0)}"
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


@pytest.mark.parametrize("p", [p for p in FILES if not _in_rig(p) and p.parent.name != "tests"], ids=_rel)
def test_hardware_only_through_rig(p):
    """Outside rig/ (and the tests, which run with DLP_NO_HARDWARE and a private lock): no PySpin, no OpenCV
    display windows, no direct HDMIWindow / Camera / RigLock."""
    for node in ast.walk(_tree(p)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            assert not any(m.split(".")[0] == "PySpin" for m in mods), f"{_rel(p)} imports PySpin"
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            assert name not in WINDOW_CALLS, f"{_rel(p)}:{node.lineno} calls cv2.{name}: use rig.bench.Bench"
            assert name not in ("HDMIWindow", "Camera", "RigLock"), \
                f"{_rel(p)}:{node.lineno} constructs {name} directly: use rig.bench.Bench / open_rig"


def _calls(node, attr):
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == attr
               for n in ast.walk(node))


@pytest.mark.parametrize("p", FILES, ids=_rel)
def test_open_rig_is_always_released_in_finally(p):
    for fn in ast.walk(_tree(p)):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and _calls(fn, "open_rig"):
            ok = any(isinstance(t, ast.Try) and any(_calls(s, "release") for s in t.finalbody)
                     for t in ast.walk(fn))
            assert ok, f"{_rel(p)}:{fn.lineno} {fn.name}() takes the rig without lock.release() in a finally"


def test_bench_is_entered_with_a_context_manager():
    """Bench(...) outside rig/ must be used as `with Bench(...)` so the DMD goes dark and the lock is freed."""
    for p in FILES:
        if _in_rig(p) or p.parent.name == "tests":
            continue
        tree = _tree(p)
        with_ctx = {id(i.context_expr) for n in ast.walk(tree) if isinstance(n, ast.With) for i in n.items}
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                f = n.func
                name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
                if name == "Bench":
                    assert id(n) in with_ctx, f"{_rel(p)}:{n.lineno} Bench(...) outside a with-statement"
