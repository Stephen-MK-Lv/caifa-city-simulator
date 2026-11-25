"""Transactional class cleanup; preserve identities and unrelated cities."""
import sqlite3
import uuid
from datetime import datetime
from sqlalchemy import select, delete
from .database import (TeachingClass, TeachingAssignment, StudentWork, ClassMember,
                       Simulation, BusinessEvent, Voucher, JournalLine, YearReport,
                       MonthSnapshot, Command)


def backup_database(db):
    folder = db.path.parent / 'backups'
    folder.mkdir(exist_ok=True)
    path = folder / f'class-cleanup-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.sqlite3'
    with sqlite3.connect(db.path.as_uri() + '?mode=ro', uri=True) as source:
        with sqlite3.connect(path) as target:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RuntimeError('备份校验失败，未删除数据')
    return path.name


def class_scope(session, class_id):
    aids = list(session.scalars(select(TeachingAssignment.id).where(TeachingAssignment.class_id == class_id)))
    works = list(session.scalars(select(StudentWork).where(StudentWork.assignment_id.in_(aids))))
    sids = {w.simulation_id for w in works}
    # New class/student accounts exist even before an assignment is issued.
    from .database import ClassCity
    sids.update(session.scalars(select(ClassCity.simulation_id).where(ClassCity.class_id == class_id)))
    return aids, works, sids


def erase_class(session, class_id):
    aids, works, sids = class_scope(session, class_id)
    if session.scalar(select(StudentWork.id).where(StudentWork.simulation_id.in_(sids),
                                                 StudentWork.assignment_id.not_in(aids)).limit(1)):
        raise ValueError('账套被其他班级引用，停止删除')
    from .database import ClassCity
    if session.scalar(select(ClassCity.id).where(ClassCity.simulation_id.in_(sids),
                                                ClassCity.class_id != class_id).limit(1)):
        raise ValueError('账套被其他班级引用，停止删除')
    session.execute(delete(StudentWork).where(StudentWork.assignment_id.in_(aids)))
    session.execute(delete(ClassCity).where(ClassCity.class_id == class_id))
    vids = select(Voucher.id).where(Voucher.simulation_id.in_(sids))
    session.execute(delete(JournalLine).where(JournalLine.voucher_id.in_(vids)))
    for model in (Voucher, BusinessEvent, YearReport, MonthSnapshot, Command):
        session.execute(delete(model).where(model.simulation_id.in_(sids)))
    session.execute(delete(Simulation).where(Simulation.id.in_(sids)))
    session.execute(delete(TeachingAssignment).where(TeachingAssignment.id.in_(aids)))
    session.execute(delete(ClassMember).where(ClassMember.class_id == class_id))
    session.execute(delete(TeachingClass).where(TeachingClass.id == class_id))
    return {'assignments': len(aids), 'works': len(works), 'cities': len(sids)}
