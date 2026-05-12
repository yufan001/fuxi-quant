from __future__ import annotations

import subprocess
from pathlib import Path


def capture_screenshot(output_path: str | Path, adb_path: str = "adb") -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([adb_path, "exec-out", "screencap", "-p"], check=True, capture_output=True)
    output.write_bytes(result.stdout)
    return output
