from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import User
from shared.auth import AuthUtils
from shared.models import UserCreate, UserResponse, UserRole

class UserCRUD:
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def create_user(db: Session, user: UserCreate) -> User:
        hashed_password = AuthUtils.get_password_hash(user.password)
        db_user = User(
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            hashed_password=hashed_password,
            role=user.role
        )
        try:
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError:
            db.rollback()
            return None

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        user = UserCRUD.get_user_by_email(db, email)
        if not user:
            return False
        if not AuthUtils.verify_password(password, user.hashed_password):
            return False
        return user

    @staticmethod
    def update_user(db: Session, user_id: int, user_data: dict) -> User:
        user = UserCRUD.get_user_by_id(db, user_id)
        if not user:
            return None

        for key, value in user_data.items():
            if hasattr(user, key):
                setattr(user, key, value)

        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_users_count(db: Session) -> int:
        """Get total number of registered users"""
        return db.query(User).count()

    @staticmethod
    def get_users_stats(db: Session) -> dict:
        """Get detailed user statistics"""
        total_users = db.query(User).count()

        # Count users by role
        from shared.models import UserRole
        role_counts = {}
        for role in UserRole:
            count = db.query(User).filter(User.role == role).count()
            role_counts[role.value] = count

        return {
            "total_users": total_users,
            "role_distribution": role_counts
        }