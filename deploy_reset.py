"""One-shot deployment data wipe with verified opening books.

Only depends on sqlite3 and the project's pure-Python accounting engine, so the
reset can be exercised locally without the web stack. Executed once per
CAIFA_DATA_RESET_REVISION by deploy_run.py at startup.

Two modes (CAIFA_RESET_FULL):
  * partial (default): erase all posted vouchers / journal lines / events /
    reports / snapshots / commands / sessions / audit, plus every student's
    answer, score, confirmation and review. Rebuild every existing simulation
    from new_city(profile, seed). Keep identities, classes, memberships and
    assignment definitions.
  * full: additionally erase class structures, assignment definitions,
    student works, simulations and all non-teacher accounts. Only the teacher
    administrator survives -- a clean installation. Opening balances are still
    verified for both profiles so every book created afterwards starts funded
    and balanced.

Both modes take a verified full SQLite backup before deleting anything, and
validate accounting invariants BEFORE the wipe. A deployment_meta marker makes
the operation idempotent: later restarts / redeploys never wipe live data again.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.engine import fen
from app.engine.state import dump_city
from app.textbook import OPENING_BANK_DEPOSITS, display_report, new_city

# Child tables first, so foreign keys never block the deletes.
ERASE_TABLES = (
    'journal_lines', 'vouchers', 'business_events', 'year_reports',
    'month_snapshots', 'commands', 'login_sessions', 'teaching_audit',
)
# Full mode only: class/identity structures. Order respects every FK.
FULL_ERASE_TABLES = (
    'student_works', 'class_cities', 'class_members', 'teaching_assignments',
    'teaching_classes', 'simulations', 'student_credentials',
)


def _snapshot_payload(report):
    """Local copy of app.monthly.snapshot_payload (avoids a SQLAlchemy import)."""
    entities = {}
    for key, entity in report['entities'].items():
        ledger = entity['financial_balance_fen']
        entities[key] = {
            'cash_yuan': entity['cash_yuan'],
            'jobs': report.get('jobs', {}).get(key),
            'receivables_yuan': round(ledger.get('应收账款', 0) / 100, 2),
            'fixed_assets_net_yuan': round(
                (ledger.get('固定资产', 0) + ledger.get('固定资产累计折旧', 0)) / 100, 2),
            'construction_yuan': round(ledger.get('在建工程', 0) / 100, 2),
        }
    return {
        'schema_version': 2,
        'month': report['month'],
        'population': sum(report['population'].values()),
        'population_groups': report['population'],
        'students': report['students'],
        'jobs': sum(report.get('jobs', {}).values()),
        'fiscal_cash_yuan': report['entities']['fiscal']['cash_yuan'],
        'entities': entities,
    }


def _backup(path: Path):
    """Never wipe without a verified full SQLite backup inside the sandbox."""
    folder = path.parent / 'backups'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'pre-reset-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.sqlite3'
    with sqlite3.connect(path) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
        if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('清除前备份校验失败')
    return target.name


def _clean_book(profile, seed):
    """Build a brand-new opening book and prove no entity starts in a loss."""
    city = new_city(profile, int(seed))
    city.check()  # financial balance, budget balance, cash >= 0, cash conservation
    report = city.report()
    checks = []
    for entity, amount in OPENING_BANK_DEPOSITS[profile].items():
        cash_fen = city.ledger[entity][city.cash_account(entity)]
        surplus = report['entities'][entity]['surplus_yuan']
        if cash_fen != fen(amount) or cash_fen <= 0:
            raise RuntimeError(f'期初资金校验失败: {entity} 实际 {cash_fen} 分, 应为 {fen(amount)} 分')
        if surplus < 0:
            raise RuntimeError(f'期初结余为负: {entity} = {surplus}')
        checks.append({'entity': entity, 'cash_yuan': cash_fen / 100, 'surplus_yuan': surplus})
    if report['cash_conservation_difference_fen'] != 0:
        raise RuntimeError('现金守恒差额不为零')
    if any(sum(accounts.values()) != 0 for accounts in city.ledger.values()):
        raise RuntimeError('财务试算不平')
    if any(sum(accounts.values()) != 0 for accounts in city.budget.values()):
        raise RuntimeError('预算试算不平')

    state = dump_city(city)
    # migrate_opening_deposits() must not re-apply the legacy delta to a fresh book.
    state['opening_deposit_revision'] = 2
    shown = display_report(report)
    return state, shown, _snapshot_payload(shown), checks


def _validate_future_books():
    """Full mode has no books left, so prove the policy both profiles will use."""
    results = {}
    for profile in ('textbook', 'jingzhou2025'):
        _, _, _, checks = _clean_book(profile, 20260906)
        results[profile] = checks
    return results


def reset_deployment_data(db_path=None, revision=None, full=None):
    """Wipe posted teaching data once, then rebuild or remove every book."""
    path = Path(db_path or os.environ['CAIFA_DB'])
    revision = str(revision or os.environ.get('CAIFA_DATA_RESET_REVISION', '1'))
    if full is None:
        full = os.environ.get('CAIFA_RESET_FULL', '0') == '1'
    connection = sqlite3.connect(path, timeout=30)
    connection.isolation_level = None  # explicit transaction control
    try:
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=30000')
        connection.execute('CREATE TABLE IF NOT EXISTS deployment_meta '
                           '(key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        applied = connection.execute(
            "SELECT value FROM deployment_meta WHERE key='data_reset_revision'").fetchone()
        if applied and applied[0] == revision:
            print(f'[reset] revision {revision} already applied; leaving live data untouched',
                  flush=True)
            return {'skipped': True, 'reason': 'already applied', 'revision': revision}

        try:
            rows = connection.execute('SELECT id, seed, state FROM simulations').fetchall()
        except sqlite3.OperationalError:
            print('[reset] simulations table missing; nothing to wipe', flush=True)
            return {'skipped': True, 'reason': 'no schema', 'revision': revision}

        # Validate ALL accounting invariants before erasing anything.
        books = []
        first_checks = None
        if full:
            future = _validate_future_books()
        else:
            future = None
            for sid, seed, raw in rows:
                old = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
                profile = old.get('profile_id', 'textbook')
                if profile not in OPENING_BANK_DEPOSITS:
                    raise RuntimeError(f'未知账套方案 {profile} (simulation {sid})')
                state, before, snapshot, checks = _clean_book(profile, seed)
                if first_checks is None:
                    first_checks = checks
                books.append((sid,
                              json.dumps(state, ensure_ascii=False),
                              json.dumps(before, ensure_ascii=False),
                              json.dumps(snapshot, ensure_ascii=False)))

        backup = _backup(path)
        connection.execute('BEGIN IMMEDIATE')
        try:
            for table in ERASE_TABLES:
                connection.execute(f'DELETE FROM {table}')
            now = time.time()
            for sid, state, before, snapshot in books:
                connection.execute(
                    'UPDATE simulations SET state=?, month=0, version=0, running=0, '
                    'last_error=NULL, next_tick=NULL, updated_at=? WHERE id=?',
                    (state, now, sid))
                connection.execute('DELETE FROM month_snapshots WHERE simulation_id=?', (sid,))
                connection.execute(
                    'INSERT INTO month_snapshots (simulation_id, month, payload) VALUES (?, 0, ?)',
                    (sid, snapshot))
                connection.execute(
                    "UPDATE student_works SET latest_attempt=NULL, teacher_review=NULL, "
                    "confirmed_at=NULL, status='assigned', before_report=?, updated_at=? "
                    "WHERE simulation_id=?", (before, now, sid))
            if full:
                for table in FULL_ERASE_TABLES:
                    connection.execute(f'DELETE FROM {table}')
                # Never leave the deployment without a usable administrator.
                teachers = connection.execute(
                    "SELECT count(*) FROM users WHERE role='teacher'").fetchone()[0]
                if teachers:
                    connection.execute("DELETE FROM users WHERE COALESCE(role,'') <> 'teacher'")
                else:
                    print('[reset] no teacher row found; leaving user rows untouched', flush=True)
            connection.execute(
                "INSERT INTO deployment_meta(key,value) VALUES('data_reset_revision',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (revision,))
            connection.execute('COMMIT')
        except Exception:
            connection.execute('ROLLBACK')
            raise
        mode = 'FULL' if full else 'PARTIAL'
        print(f'[reset] {mode}: wiped {len(ERASE_TABLES) + (len(FULL_ERASE_TABLES) if full else 0)} '
              f'tables, {len(rows)} books previously existed, backup={backup}', flush=True)
        return {'skipped': False, 'mode': mode, 'books_seen': len(rows),
                'books_rebuilt': len(books), 'backup': backup, 'revision': revision,
                'opening_checks': first_checks, 'future_book_checks': future}
    finally:
        connection.close()
