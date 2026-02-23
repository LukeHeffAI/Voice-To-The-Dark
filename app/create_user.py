"""Create a user account from the command line.

Usage:
    python -m app.create_user <username> <password> [--admin]

The first user you create should use --admin so they can create
additional accounts via the API.
"""

import sys
from app.database import SessionLocal, engine
from app.models.story import Base, User
from app.auth import hash_password

Base.metadata.create_all(bind=engine)


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m app.create_user <username> <password> [--admin]")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    is_admin = "--admin" in sys.argv

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"Error: username '{username}' already exists.")
            sys.exit(1)

        user = User(
            username=username,
            password_hash=hash_password(password),
            is_admin=is_admin,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        role = "admin" if is_admin else "user"
        print(f"Created {role} account: {username} (id={user.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
