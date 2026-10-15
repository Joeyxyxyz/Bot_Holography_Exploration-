"""E0: the vendored OGR DMD math package validates (31/31 on 2026-09-29)."""
import sys
from pathlib import Path

OGR = Path(__file__).resolve().parents[1] / "third_party" / "OGR_DMD_MathPackage_v1.0"


def test_ogr_self_validation_passes():
    sys.path.insert(0, str(OGR))
    try:
        from ogr import validate
        rows = validate.run_all()
    finally:
        sys.path.remove(str(OGR))
    failed = [r["check"] for r in rows if not r["pass"]]
    assert len(rows) == 31 and not failed, failed
