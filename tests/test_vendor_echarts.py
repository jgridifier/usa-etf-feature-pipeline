"""The offline chart bundle must match its provenance and pinned build inputs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vendor_integrity_and_pins():
    vendor = ROOT / 'docs/assets/vendor'
    manifest = json.loads((vendor / 'VENDOR.json').read_text())
    assert manifest['version'] == '6.1.0'
    assert hashlib.sha256((vendor / manifest['file']).read_bytes()).hexdigest() == manifest['sha256']
    build = ROOT / 'tools/echarts-build'
    assert json.loads((build / 'package.json').read_text())['devDependencies']['echarts'] == '6.1.0'
    assert 'ECharts 6.1.0' in (build / 'entry.js').read_text()
