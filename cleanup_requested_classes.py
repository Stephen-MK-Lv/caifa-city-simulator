"""One-off explicitly requested cleanup, restricted to verified class IDs."""
from pathlib import Path
from types import SimpleNamespace
from app.class_cleanup import backup_database, erase_class
from app.database import Database, TeachingClass, TeachingAudit

if __name__ == '__main__':
    path = Path(__file__).resolve().parent / 'data' / 'mingchuan.sqlite3'
    backup = backup_database(SimpleNamespace(path=path))
    print('Backup:', backup)
    db = Database(path)
    with db.transaction(write=True) as session:
        for cid in ('8991b5c8-ed0f-52b6-b347-ef87958a1e07','278a429a-1556-5db8-9572-b9ccabdebef9'):
            cls = session.get(TeachingClass, cid)
            if cls is None:
                print(cid, 'already removed'); continue
            assert cls.name == '政府会计学实训班', '名称不匹配，停止清理'
            actor = cls.teacher_id
            result = erase_class(session, cid)
            session.add(TeachingAudit(actor_id=actor, action='delete_class', target_id=cid,
                                      detail={**result, 'backup':backup, 'name':'政府会计学实训班'}))
            print(cid, result)
    with db.engine.connect() as connection:
        print('Foreign keys:', list(connection.exec_driver_sql('PRAGMA foreign_key_check')))
        print('Integrity:', list(connection.exec_driver_sql('PRAGMA integrity_check')))
