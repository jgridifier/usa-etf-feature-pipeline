"""Exercise the actual offline browser chart engine when Node is available."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_hub_charts_ssr():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for chart SVG regression tests')
    subprocess.run([node, str(ROOT / 'tests/hub_charts_ssr.cjs')], cwd=ROOT, check=True)


def test_hub_charts_runtime():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for chart runtime tests')
    subprocess.run([node, str(ROOT / 'tests/hub_charts_runtime.cjs')], cwd=ROOT, check=True)
