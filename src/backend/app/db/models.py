"""Database model notes.

The project currently uses explicit PostgreSQL DDL in `src/database/init.sql`
and runtime SQL helpers in `session.py`. This module is intentionally kept as
the stable place for future ORM models.
"""

TABLES = ("users", "logs", "alerts", "model_predictions")
