"""
Quick admin user creator

Creates an admin-capable application user with a known password so you can log in
to the SQLAdmin panel. It tries to assign role_id 1 first, then 2, then the first
available role. Idempotent by email.

Run inside the container:
    python -m app.utils.create_admin_quick
"""

from app.database import SessionLocal, engine, Base
from app.models import User, Role, Company
from app.services.organization_service import UserService
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    # Ensure metadata exists (no-op if already created)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        name = "관리자"
        email = "admin@babba-api.local"
        password = "admin123"

        # Idempotent check by email
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            logger.info("Admin user already exists: %s (id=%s)", existing.email, getattr(existing, "user_id", None))
            return

        # Pick a role: prefer id 1, then 2, else first active role
        role = db.query(Role).filter(Role.role_id.in_([1, 2])).order_by(Role.role_id.asc()).first()
        if not role:
            role = db.query(Role).order_by(Role.role_id.asc()).first()
        if not role:
            # create a default role when table empty
            role = Role(role_name="본사 관리자", description="관리자")
            db.add(role)
            db.flush()

        # Pick or create a company
        company = db.query(Company).first()
        if not company:
            company = Company(company_group="HQ", name="본사")
            db.add(company)
            db.flush()

        password_hash = UserService.hash_password(password)

        user = User(
            name=name,
            email=email,
            password_hash=password_hash,
            company_id=getattr(company, "company_id", None),
            role_id=getattr(role, "role_id", None),
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info("✅ Admin user created")
        logger.info("   name=%s email=%s role_id=%s company_id=%s", user.name, user.email, user.role_id, user.company_id)
        logger.info("   login at /admin with username='%s' and password='%s'", name, password)
    except Exception as e:
        db.rollback()
        logger.error("Failed to create admin: %s", e)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
