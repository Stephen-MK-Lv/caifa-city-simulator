"""Recoverable training passwords, separate from authentication hashes."""
import os
import time
from cryptography.fernet import Fernet, InvalidToken
from .database import StudentCredential


def vault(db, create=False):
    path = db.path.parent / 'student-credentials.key'
    if create and not path.exists():
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'wb') as f:
                f.write(Fernet.generate_key())
    return Fernet(path.read_bytes())


def save_password(db, session, user, password):
    encrypted = vault(db, True).encrypt(password.encode()).decode()
    row = session.get(StudentCredential, user.id)
    if row:
        row.encrypted_password = encrypted; row.updated_at = time.time()
    else:
        session.add(StudentCredential(user_id=user.id, encrypted_password=encrypted))


def reveal_password(db, session, user):
    row = session.get(StudentCredential, user.id)
    if row is None:
        return None
    try:
        return vault(db).decrypt(row.encrypted_password.encode()).decode()
    except (OSError, ValueError, InvalidToken):
        return None
