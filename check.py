"""Run tests in a new project-owned directory, without touching previous runs."""
from pathlib import Path
import uuid
import pytest

if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    parent = root / 'data' / 'test-runs'
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / ('run-' + uuid.uuid4().hex)
    if target.exists():
        raise RuntimeError('Refusing to reuse an existing temporary path')
    raise SystemExit(pytest.main([str(root / 'tests'), '-q', '-p', 'no:cacheprovider',
                                 '--tb=short', '--basetemp', str(target)]))
