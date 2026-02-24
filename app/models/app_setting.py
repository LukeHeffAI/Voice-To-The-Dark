from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class AppSetting(Base):
    __tablename__ = 'app_settings'

    key = Column(String, primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


def get_setting(db, key: str, default: str = "") -> str:
    """Return the value for a setting key, or default if not set."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    return row.value if row else default


def set_setting(db, key: str, value: str) -> None:
    """Upsert a setting value."""
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
    else:
        row = AppSetting(key=key, value=value)
        db.add(row)
    db.commit()
