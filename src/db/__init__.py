"""Database package: async engine, session factory, and session dependency.

There is no ORM in this project. SQLAlchemy is used only as the async
connection pool and transaction manager; every query is hand-written SQL
executed through :func:`sqlalchemy.text`.
"""

from db.session import SessionDep, SessionFactory, dispose_engine, engine, get_session

__all__ = ["SessionDep", "SessionFactory", "dispose_engine", "engine", "get_session"]
