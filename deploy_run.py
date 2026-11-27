"""Deployment entry point for WorkBuddy app publishing.

The original run.py is a desktop launcher: it binds 127.0.0.1, opens a local
browser and defaults to port 8765. A published app runs behind a reverse proxy
and must bind 0.0.0.0 on the injected PORT, and the app's TrustedHostMiddleware
must accept the public hostname.

This wrapper sets runtime environment, adapts reverse-proxy headers, performs a
one-off data wipe that rebuilds every account book at its opening position, and
applies an opening-deposit migration to books created before the policy change.
It does not change the application's database schema.
"""
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

os.environ['CAIFA_HOST'] = '0.0.0.0'
os.environ['CAIFA_AUTH_REQUIRED'] = '1'
# TrustedHostMiddleware: enumerate concrete hosts instead of a wildcard.
# The assigned app domain is caifa-city-simulator.app.workbuddy.host;
# zfkj.app.workbuddy.host is kept for the domain requested by the owner.
# localhost / 127.0.0.1 / testserver keep the sandbox health check working.
os.environ['CAIFA_ALLOWED_HOSTS'] = (
    'caifa-city-simulator.app.workbuddy.host,'
    'zfkj.app.workbuddy.host,'
    'localhost,127.0.0.1,testserver'
)
# SQLite lives inside the sandbox, next to the app, so it needs no external DB.
os.environ['CAIFA_DB'] = str(ROOT / 'data' / 'caifa.sqlite3')
# Close public self-registration and seed the first teacher at startup.
# initialize_deployment_teacher() validates via Credentials, whose password
# min_length is 10 -- keep this value at 10+ characters or startup fails.
os.environ['CAIFA_DISABLE_BOOTSTRAP'] = '1'
os.environ['CAIFA_INITIAL_TEACHER_USERNAME'] = 'teacher'
os.environ['CAIFA_INITIAL_TEACHER_PASSWORD'] = '1234567890'
os.environ['CAIFA_INITIAL_TEACHER_NAME'] = '教师管理员'
# Owner-confirmed one-shot FULL reset: also drop classes, student accounts,
# assignment definitions and the books themselves. Keep only the teacher.
# Set to '0' for a business-data-only wipe, or bump CAIFA_DATA_RESET_REVISION
# to run the reset again later.
os.environ['CAIFA_RESET_FULL'] = '1'
os.environ.setdefault('CAIFA_DATA_RESET_REVISION', '1')
# NOTE: this file holds the bootstrap credential. Do not push it to GitHub.

import uvicorn  # noqa: E402  (import after env setup)
from app.main import app as fastapi_app  # noqa: E402
from app.database import Database  # noqa: E402

# Make sure every table exists before the one-shot reset touches them.
Database(Path(os.environ['CAIFA_DB']))

TRUSTED_HOSTS = {h.strip().lower() for h in os.environ['CAIFA_ALLOWED_HOSTS'].split(',') if h.strip()}


class ProxyHeaderMiddleware:
    """Adapt reverse-proxy headers without weakening the app's own checks.

    1) The publish proxy injects its own Authorization header, which replaces
       the browser's app token. Front-end scripts additionally send the same
       token as X-Caifa-Token; restore it as Authorization here so every
       authenticated API works.
    2) app.main's CSRF guard compares urlsplit(Origin).netloc with the Host
       header. The proxy forwards an internal Host, so browser POSTs were
       rejected. Normalize Host only for Origins on the explicit allowlist.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            headers = list(scope.get('headers', []))
            patched = list(headers)

            app_token = next((v for k, v in headers if k.lower() == b'x-caifa-token'), None)
            if app_token:
                patched = [(k, v) for k, v in patched
                           if k.lower() not in (b'authorization', b'x-caifa-token')]
                patched.append((b'authorization', app_token))

            origin = next((v.decode('latin-1') for k, v in headers if k.lower() == b'origin'), None)
            if origin:
                parts = urlsplit(origin)
                if parts.scheme in ('http', 'https') and (parts.hostname or '').lower() in TRUSTED_HOSTS:
                    patched = [(k, v) for k, v in patched if k.lower() != b'host']
                    patched.append((b'host', parts.netloc.encode('latin-1')))

            if patched != headers:
                scope = dict(scope)
                scope['headers'] = patched
        await self.app(scope, receive, send)


def migrate_opening_deposits():
    """Give pre-existing class account books the new entity opening balances.

    Only the opening position is adjusted (cash / equity / budget reserve /
    opening_cash). Posted vouchers, business events and student answers are
    never touched, so the books stay reconcilable with their vouchers.
    A revision marker makes this idempotent across restarts and redeploys.
    """
    import json
    import sqlite3
    import traceback

    from app.database import Database
    from app.engine import fen
    from app.textbook import MONEY, OPENING_BANK_DEPOSITS

    # Effective opening balances before this policy change (yuan).
    legacy = {
        'textbook': {'fiscal': 100000000, 'hospital': 3000000, 'school': 600000, 'police': 100000},
        'jingzhou2025': {'fiscal': 48582500, 'hospital': 5000000, 'school': 1000000, 'police': 1000000},
    }
    revision = 2
    path = Path(os.environ['CAIFA_DB'])
    try:
        Database(path)  # ensure the schema exists on a fresh sandbox
        connection = sqlite3.connect(path, timeout=15)
        try:
            rows = connection.execute('SELECT id, state FROM simulations').fetchall()
            changed = 0
            for sid, raw in rows:
                state = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
                if not state or state.get('opening_deposit_revision') == revision:
                    continue
                profile = state.get('profile_id', 'textbook')
                if profile not in legacy or profile not in OPENING_BANK_DEPOSITS:
                    continue
                ledger = state.get('ledger') or {}
                budget = state.get('budget') or {}
                total_delta = 0
                for entity, amount in OPENING_BANK_DEPOSITS[profile].items():
                    delta = fen(amount) - fen(legacy[profile][entity])
                    if not delta or entity not in ledger or entity not in budget:
                        continue
                    cash = '国库存款' if entity == 'fiscal' else '银行存款'
                    equity = '实收资本' if entity == 'soe' else '累计盈余'
                    money = '资金结存' if entity == 'fiscal' else MONEY
                    reserve = '一般公共预算结转结余' if entity == 'fiscal' else '非财政拨款结余'
                    ledger[entity][cash] = ledger[entity].get(cash, 0) + delta
                    ledger[entity][equity] = ledger[entity].get(equity, 0) - delta
                    budget[entity][money] = budget[entity].get(money, 0) + delta
                    budget[entity][reserve] = budget[entity].get(reserve, 0) - delta
                    total_delta += delta
                state['opening_cash'] = state.get('opening_cash', 0) + total_delta
                state['opening_deposit_revision'] = revision
                connection.execute('UPDATE simulations SET state=? WHERE id=?',
                                   (json.dumps(state, ensure_ascii=False), sid))
                changed += 1
            connection.commit()
            print(f'Opening deposits initialized for {changed} existing account books '
                  f'({len(rows)} total)', flush=True)
        finally:
            connection.close()
    except Exception:
        print('Opening deposit migration failed; existing books keep their old balances.', flush=True)
        traceback.print_exc()


# One-shot wipe (owner-confirmed FULL mode): clear all posted vouchers / events /
# answers, classes, student accounts and books; keep only the teacher. Bump
# CAIFA_DATA_RESET_REVISION to run it again.
from deploy_reset import reset_deployment_data  # noqa: E402
reset_deployment_data()
migrate_opening_deposits()

port = int(os.environ.get('PORT') or os.environ.get('CAIFA_PORT') or '8765')
print(f'Caifa city simulator listening on 0.0.0.0:{port}', flush=True)
uvicorn.run(ProxyHeaderMiddleware(fastapi_app), host='0.0.0.0', port=port,
            workers=1, log_level='info')
