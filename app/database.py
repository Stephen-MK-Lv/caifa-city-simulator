from contextlib import contextmanager
from pathlib import Path
import time
from sqlalchemy import (create_engine, event, String, Integer, BigInteger, Float, Boolean,
                        JSON, ForeignKey, UniqueConstraint, CheckConstraint, Index, Computed)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session


class Base(DeclarativeBase):
    pass


class Simulation(Base):
    __tablename__ = 'simulations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(60))
    seed: Mapped[int] = mapped_column(BigInteger)
    month: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[dict] = mapped_column(JSON)
    running: Mapped[bool] = mapped_column(Boolean, default=False)
    interval: Mapped[int] = mapped_column(Integer, default=8)
    pause_at_year: Mapped[bool] = mapped_column(Boolean, default=True)
    next_tick: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(12))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class LoginSession(Base):
    __tablename__ = 'login_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    expires_at: Mapped[float] = mapped_column(Float, index=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class StudentCredential(Base):
    __tablename__ = 'student_credentials'
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    encrypted_password: Mapped[str] = mapped_column(String(1000))
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)


class TeachingClass(Base):
    __tablename__ = 'teaching_classes'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    term: Mapped[str] = mapped_column(String(80), default='')
    profile_id: Mapped[str] = mapped_column(String(30), default='textbook')
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class ClassMember(Base):
    __tablename__ = 'class_members'
    __table_args__ = (UniqueConstraint('class_id', 'user_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_id: Mapped[str] = mapped_column(ForeignKey('teaching_classes.id'), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class TeachingAssignment(Base):
    __tablename__ = 'teaching_assignments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    class_id: Mapped[str] = mapped_column(ForeignKey('teaching_classes.id'), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    chapter: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(160))
    instruction: Mapped[str] = mapped_column(String(3000))
    scenario: Mapped[dict] = mapped_column(JSON)
    rubric: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class StudentWork(Base):
    __tablename__ = 'student_works'
    __table_args__ = (UniqueConstraint('assignment_id', 'student_id'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(ForeignKey('teaching_assignments.id'), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey('simulations.id'), index=True)
    case_data: Mapped[dict] = mapped_column(JSON)
    reference_entries: Mapped[list] = mapped_column(JSON)
    rubric: Mapped[dict] = mapped_column(JSON)
    before_report: Mapped[dict] = mapped_column(JSON)
    latest_attempt: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default='assigned')
    confirmed_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    teacher_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
    updated_at: Mapped[float] = mapped_column(Float, default=time.time)


class ClassCity(Base):
    __tablename__ = 'class_cities'
    __table_args__ = (UniqueConstraint('class_id', 'student_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    class_id: Mapped[str] = mapped_column(ForeignKey('teaching_classes.id'), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey('simulations.id'), unique=True)


class TeachingAudit(Base):
    __tablename__ = 'teaching_audit'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    action: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class BusinessEvent(Base):
    __tablename__ = 'business_events'
    __table_args__ = (UniqueConstraint('simulation_id', 'event_key'),
                     UniqueConstraint('simulation_id', 'sequence'),
                     Index('ix_events_lookup', 'simulation_id', 'month', 'entity', 'kind'))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey('simulations.id'))
    event_key: Mapped[str] = mapped_column(String(120))
    sequence: Mapped[int] = mapped_column(Integer)
    business_code: Mapped[str] = mapped_column(String(24), Computed("'业-' || sequence", persisted=False))
    month: Mapped[int] = mapped_column(Integer)
    entity: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON)


class Voucher(Base):
    __tablename__ = 'vouchers'
    __table_args__ = (UniqueConstraint('simulation_id', 'number'),
                     CheckConstraint("book in ('financial','budget')"),
                     Index('ix_vouchers_lookup', 'simulation_id', 'entity', 'book', 'month'))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey('simulations.id'))
    event_id: Mapped[int] = mapped_column(ForeignKey('business_events.id'))
    number: Mapped[int] = mapped_column(Integer)
    month: Mapped[int] = mapped_column(Integer)
    entity: Mapped[str] = mapped_column(String(20))
    book: Mapped[str] = mapped_column(String(15))
    payload: Mapped[dict] = mapped_column(JSON)


class JournalLine(Base):
    __tablename__ = 'journal_lines'
    __table_args__ = (CheckConstraint('amount_fen >= 0'), CheckConstraint("side in ('debit','credit')"))
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    voucher_id: Mapped[int] = mapped_column(ForeignKey('vouchers.id'), index=True)
    entity: Mapped[str | None] = mapped_column(String(20))
    book: Mapped[str | None] = mapped_column(String(15))
    side: Mapped[str] = mapped_column(String(8))
    account: Mapped[str] = mapped_column(String(160))
    amount_fen: Mapped[int] = mapped_column(BigInteger)


class YearReport(Base):
    __tablename__ = 'year_reports'
    __table_args__ = (UniqueConstraint('simulation_id', 'year'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey('simulations.id'))
    year: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)


class MonthSnapshot(Base):
    __tablename__ = 'month_snapshots'
    __table_args__ = (UniqueConstraint('simulation_id', 'month'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey('simulations.id'))
    month: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)


class Command(Base):
    __tablename__ = 'commands'
    __table_args__ = (UniqueConstraint('simulation_id', 'request_id'),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey('simulations.id'))
    request_id: Mapped[str] = mapped_column(String(80))
    fingerprint: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class Database:
    def __init__(self, path: str | Path):
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.engine = create_engine('sqlite:///' + path.as_posix(),
                                    connect_args={'check_same_thread': False, 'timeout': 15})

        @event.listens_for(self.engine, 'connect')
        def configure(connection, _):
            cursor = connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.execute('PRAGMA busy_timeout=15000')
            cursor.close()

        with self.engine.connect() as connection:
            connection.exec_driver_sql('PRAGMA journal_mode=WAL')
        Base.metadata.create_all(self.engine)
        # Remove the legacy one-task/one-city unique constraint without losing rows.
        with self.engine.begin() as connection:
            indexes = list(connection.exec_driver_sql('PRAGMA index_list(student_works)'))
            legacy = any(row[2] and [c[2] for c in connection.exec_driver_sql(
                'PRAGMA index_info("' + row[1] + '")')] == ['simulation_id'] for row in indexes)
            if legacy:
                from sqlalchemy import MetaData
                from sqlalchemy.schema import CreateTable, CreateIndex
                table = StudentWork.__table__.to_metadata(MetaData(), name='student_works_new')
                # Foreign keys resolve against the original metadata during compilation.
                for ref in ('users', 'teaching_assignments', 'simulations'):
                    Base.metadata.tables[ref].to_metadata(table.metadata)
                connection.execute(CreateTable(table))
                columns = ','.join(c.name for c in StudentWork.__table__.columns)
                connection.exec_driver_sql(f'INSERT INTO student_works_new ({columns}) SELECT {columns} FROM student_works')
                connection.exec_driver_sql('DROP TABLE student_works')
                connection.exec_driver_sql('ALTER TABLE student_works_new RENAME TO student_works')
                for index in StudentWork.__table__.indexes:
                    connection.execute(CreateIndex(index))
        with self.engine.begin() as connection:
            class_columns = {row[1] for row in connection.exec_driver_sql('PRAGMA table_info(teaching_classes)')}
            if 'profile_id' not in class_columns:
                connection.exec_driver_sql("ALTER TABLE teaching_classes ADD COLUMN profile_id VARCHAR(30) NOT NULL DEFAULT 'textbook'")
            columns = {row[1] for row in connection.exec_driver_sql('PRAGMA table_info(simulations)')}
            if 'owner_user_id' not in columns:
                connection.exec_driver_sql('ALTER TABLE simulations ADD COLUMN owner_user_id INTEGER REFERENCES users(id)')
            journal_columns = {row[1] for row in connection.exec_driver_sql('PRAGMA table_info(journal_lines)')}
            if 'entity' not in journal_columns:
                connection.exec_driver_sql('ALTER TABLE journal_lines ADD COLUMN entity VARCHAR(20)')
            if 'book' not in journal_columns:
                connection.exec_driver_sql('ALTER TABLE journal_lines ADD COLUMN book VARCHAR(15)')
            event_columns = {row[1] for row in connection.exec_driver_sql('PRAGMA table_xinfo(business_events)')}
            if 'business_code' not in event_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE business_events ADD COLUMN business_code VARCHAR(24) "
                    "GENERATED ALWAYS AS ('业-' || sequence) VIRTUAL"
                )

    @contextmanager
    def transaction(self, write=False):
        # Serialize writers BEFORE loading a checkpoint, including across processes.
        # Explicit BEGIN also gives read requests a consistent snapshot across tables.
        with Session(self.engine, expire_on_commit=False) as session:
            session.connection().exec_driver_sql('BEGIN IMMEDIATE' if write else 'BEGIN')
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
