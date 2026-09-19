"""Persistence and wire shapes.

`tables` holds SQLAlchemy models mirroring supabase/migrations/.
`schemas` holds the Pydantic models used at the API boundary.

Neither is imported by `app.engine`, which takes plain dataclasses instead.
"""

from . import schemas, tables
from .tables import Base

__all__ = ["Base", "schemas", "tables"]
