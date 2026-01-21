from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
import os
import time

from shared.database import get_db, Base, engine
from shared.auth import AuthUtils
from shared.models import UserCreate, UserResponse, Token, TokenData, UserRole
from models import User
from crud import UserCRUD

# Wait for database to be ready
print("Waiting for database connection...")
for i in range(30):  # Try for 30 seconds
    try:
        with engine.connect() as conn:
            print("Database connection established!")
            break
    except Exception as e:
        print(f"Database not ready, attempt {i+1}/30: {e}")
        time.sleep(1)
else:
    print("Could not connect to database after 30 attempts")
    raise Exception("Database connection failed")

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Auth Service", description="User authentication and authorization service")

@app.get("/")
def read_root(db: Session = Depends(get_db)):
    """Get Auth Service status with user statistics"""
    stats = UserCRUD.get_users_stats(db)
    return {
        "service": "Auth Service",
        "status": "running",
        "version": "1.0.0",
        "description": "User authentication and authorization service",
        "statistics": stats
    }

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    db_user = UserCRUD.get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    created_user = UserCRUD.create_user(db, user)
    if not created_user:
        raise HTTPException(status_code=400, detail="User creation failed")

    return UserResponse.from_orm(created_user)

@app.post("/token", response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return access/refresh tokens"""
    user = UserCRUD.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = AuthUtils.create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )
    refresh_token = AuthUtils.create_refresh_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )

    return Token(access_token=access_token, refresh_token=refresh_token)

@app.post("/refresh", response_model=Token)
def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    payload = AuthUtils.verify_token(refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    user = UserCRUD.get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = AuthUtils.create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role.value}
    )

    return Token(access_token=access_token, refresh_token=refresh_token)

@app.get("/me", response_model=UserResponse)
def read_users_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get current user information"""
    payload = AuthUtils.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    user = UserCRUD.get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return UserResponse.from_orm(user)

@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Get user by ID (admin/manager only)"""
    payload = AuthUtils.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    current_user_role = payload.get("role")
    if current_user_role not in [UserRole.ADMIN.value, UserRole.MANAGER.value]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    user = UserCRUD.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.from_orm(user)

@app.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: int, user_data: dict, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Update user information (admin/manager only or self)"""
    payload = AuthUtils.verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    current_user_id = int(payload.get("sub"))
    current_user_role = payload.get("role")

    # Allow users to update themselves, or admins/managers to update anyone
    if current_user_id != user_id and current_user_role not in [UserRole.ADMIN.value, UserRole.MANAGER.value]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    updated_user = UserCRUD.update_user(db, user_id, user_data)
    if not updated_user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse.from_orm(updated_user)

@app.get("/stats")
def get_user_stats(db: Session = Depends(get_db)):
    """Get user statistics"""
    return UserCRUD.get_users_stats(db)

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "auth-service"}