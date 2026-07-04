"""
One-off script: creates all tables defined in app.models against DATABASE_URL.
Run with: python backend/create_tables.py
"""
from app.database import Base, engine
from app.models import article  # noqa: F401 ensures the model is registered
from app.models import newsletter  # noqa: F401 ensures newsletter_subscribers is registered


def main():
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")


if __name__ == "__main__":
    main()
