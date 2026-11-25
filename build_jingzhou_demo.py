"""Generate a separate, reproducible demo without opening classroom databases."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / '荆州参考仿真数据_2025'
DB = ROOT / 'data' / 'jingzhou-demo-20261009.sqlite3'

if __name__ == '__main__':
    if DB.exists() or OUT.exists():
        raise SystemExit('Demo destination already exists; refusing to overwrite.')
    OUT.mkdir()
    with TestClient(create_app(DB, scheduler=False)) as client:
        for months, name in [(12, '彩珐市 · 荆州参考全年示范'), (0, '彩珐市 · 荆州参考期初')]:
            response = client.post('/api/simulations', json={
                'name': name, 'seed': 20260906, 'profile_id': 'jingzhou2025',
                'initial_months': months, 'request_id': f'jingzhou-demo-20261009-{months}'})
            response.raise_for_status()
            sid = response.json()['simulation']['id']
            summary = client.get(f'/api/simulations/{sid}').json()
            assert all(v == 0 for v in summary['invariants'].values())
            export = client.get(f'/api/simulations/{sid}/export')
            export.raise_for_status()
            (OUT / f'彩珐市_荆州参考_{months}月_教学数据.zip').write_bytes(export.content)
            if months == 0:
                (OUT / '公开数据与仿真假设.json').write_text(json.dumps({
                    'reference': summary['reference'], 'parameters': summary['parameters']},
                    ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'months': months, 'events': summary['event_count'],
                              'vouchers': summary['voucher_count'], 'invariants': summary['invariants']}, ensure_ascii=False))
