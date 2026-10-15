"""Renders the real forged "payment failed" screenshots (the same Pillow renderer the agent uses) for the landing page.
   python -m scripts.render_samples   (from backend/)  -> ../public/img/"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sentinel.media import forge_screenshot

OUT = Path(__file__).resolve().parents[2] / "public" / "img"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    when = datetime(2026, 3, 14, 10, 42, tzinfo=timezone.utc)
    for name, vpa, amount, code in (("payment-failed-a", "refund.dept@ybl", "500", "U30"), ("payment-failed-b", "kyc.update@okaxis", "1200", "U16")):
        png, meta = forge_screenshot(vpa, amount, code, now=when)
        (OUT / f"{name}.png").write_bytes(png)
        print(name, len(png), "bytes", meta.get("sha256", "")[:12])


if __name__ == "__main__":
    main()