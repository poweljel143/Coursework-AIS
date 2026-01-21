from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import time

from shared.database import get_db, Base, engine
from shared.auth import AuthUtils
from shared.models import TokenData
from models import FinancingApplication, FinancingSchedule, FinancingStatus, FinancingType
from crud import FinancingCRUD

# Wait for database to be ready
print("Waiting for database connection for Financing Service...")
for i in range(30):  # Try for 30 seconds
    try:
        with engine.connect() as conn:
            print("Financing Service Database connection established!")
            break
    except Exception as e:
        print(f"Financing Service Database not ready, attempt {i+1}/30: {e}")
        time.sleep(1)
else:
    print("Financing Service: Could not connect to database after 30 attempts")
    raise Exception("Financing Service: Database connection failed")

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Financing Service", description="Loan and financing management service for Autosalon")

@app.get("/")
def read_root(db: Session = Depends(get_db)):
    """Get Financing Service status with financing statistics"""
    stats = FinancingCRUD.get_financing_stats(db)
    return {
        "service": "Financing Service",
        "status": "running",
        "version": "1.0.0",
        "description": "Car financing and loan management service",
        "statistics": stats
    }

def get_current_user(authorization: Optional[str] = Header(default=None)) -> Optional[TokenData]:
    """Get current user from Authorization header (Bearer token)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    payload = AuthUtils.verify_token(token)
    if payload:
        return TokenData(
            user_id=int(payload.get("sub")),
            email=payload.get("email"),
            role=payload.get("role")
        )
    return None

@app.post("/applications")
def create_application(
    order_id: int,
    vehicle_price: float,
    down_payment: float = 0.0,
    term_months: int = 36,
    financing_type: FinancingType = FinancingType.CAR_LOAN,
    employment_status: str = None,
    monthly_income: float = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new financing application"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if vehicle_price <= 0 or term_months < 12 or term_months > 84:
        raise HTTPException(status_code=400, detail="Invalid financing parameters")

    if down_payment < 0 or down_payment >= vehicle_price:
        raise HTTPException(status_code=400, detail="Invalid down payment amount")

    application = FinancingCRUD.create_application(
        db=db,
        user_id=current_user.user_id,
        order_id=order_id,
        vehicle_price=vehicle_price,
        down_payment=down_payment,
        term_months=term_months,
        financing_type=financing_type,
        employment_status=employment_status,
        monthly_income=monthly_income
    )

    return {
        "application_id": application.id,
        "loan_amount": application.loan_amount,
        "monthly_payment": application.monthly_payment,
        "total_payment": application.total_payment,
        "interest_rate": application.interest_rate,
        "status": application.status.value,
        "term_months": application.term_months
    }

@app.put("/applications/{application_id}/submit")
def submit_application(
    application_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit application for review"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    application = FinancingCRUD.get_application_by_id(db, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    submitted_app = FinancingCRUD.submit_application(db, application_id)
    if not submitted_app:
        raise HTTPException(status_code=400, detail="Cannot submit application")

    return {"message": "Application submitted for review", "status": submitted_app.status.value}

@app.get("/applications/{application_id}")
def get_application(
    application_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get application details"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    application = FinancingCRUD.get_application_by_id(db, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Users can see their own applications, managers/admins can see all
    if application.user_id != current_user.user_id and current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "id": application.id,
        "user_id": application.user_id,
        "order_id": application.order_id,
        "vehicle_price": application.vehicle_price,
        "down_payment": application.down_payment,
        "loan_amount": application.loan_amount,
        "financing_type": application.financing_type.value,
        "term_months": application.term_months,
        "interest_rate": application.interest_rate,
        "monthly_payment": application.monthly_payment,
        "total_payment": application.total_payment,
        "status": application.status.value,
        "employment_status": application.employment_status,
        "monthly_income": application.monthly_income,
        "created_at": application.created_at,
        "updated_at": application.updated_at
    }

@app.get("/applications")
def get_user_applications(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all applications for current user"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    applications = FinancingCRUD.get_applications_by_user(db, current_user.user_id)
    return [{
        "id": app.id,
        "order_id": app.order_id,
        "loan_amount": app.loan_amount,
        "monthly_payment": app.monthly_payment,
        "status": app.status.value,
        "term_months": app.term_months,
        "created_at": app.created_at
    } for app in applications]

@app.get("/orders/{order_id}/applications")
def get_order_applications(
    order_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get financing applications for an order"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    applications = FinancingCRUD.get_applications_by_order(db, order_id)

    # Check access (simplified - in real system verify order ownership)
    if applications and applications[0].user_id != current_user.user_id and current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return [{
        "id": app.id,
        "loan_amount": app.loan_amount,
        "monthly_payment": app.monthly_payment,
        "status": app.status.value,
        "created_at": app.created_at
    } for app in applications]

@app.get("/applications/{application_id}/schedule")
def get_payment_schedule(
    application_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get payment schedule for an application"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    application = FinancingCRUD.get_application_by_id(db, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.user_id != current_user.user_id and current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")

    if application.status != FinancingStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Application not approved yet")

    schedule = FinancingCRUD.get_payment_schedule(db, application_id)
    return [{
        "payment_number": payment.payment_number,
        "due_date": payment.due_date,
        "principal_amount": payment.principal_amount,
        "interest_amount": payment.interest_amount,
        "total_amount": payment.total_amount,
        "remaining_balance": payment.remaining_balance,
        "is_paid": payment.is_paid,
        "paid_at": payment.paid_at
    } for payment in schedule]

# Manager/Admin endpoints
@app.get("/admin/applications")
def get_all_applications(
    status: Optional[FinancingStatus] = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all applications (admin/manager only)"""
    if not current_user or current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(FinancingApplication)
    if status:
        query = query.filter(FinancingApplication.status == status)

    applications = query.all()
    return [{
        "id": app.id,
        "user_id": app.user_id,
        "order_id": app.order_id,
        "loan_amount": app.loan_amount,
        "monthly_payment": app.monthly_payment,
        "status": app.status.value,
        "created_at": app.created_at
    } for app in applications]

@app.put("/admin/applications/{application_id}/review")
def review_application(
    application_id: int,
    approved: bool,
    notes: str = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Review application (admin/manager only)"""
    if not current_user or current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    reviewed_app = FinancingCRUD.review_application(
        db=db,
        application_id=application_id,
        approved=approved,
        reviewer_id=current_user.user_id,
        notes=notes
    )

    if not reviewed_app:
        raise HTTPException(status_code=400, detail="Cannot review application")

    action = "approved" if approved else "rejected"
    return {"message": f"Application {action}", "status": reviewed_app.status.value}

@app.get("/calculator")
def calculate_financing(
    vehicle_price: float,
    down_payment: float = 0.0,
    term_months: int = 36,
    employment_status: str = None
):
    """Calculate financing options without creating application"""
    if vehicle_price <= 0 or term_months < 12 or term_months > 84:
        raise HTTPException(status_code=400, detail="Invalid parameters")

    loan_amount = vehicle_price - down_payment
    interest_rate = FinancingCRUD._get_interest_rate(loan_amount, term_months, employment_status)
    payment_details = FinancingCRUD.calculate_loan_payment(loan_amount, interest_rate, term_months)

    return {
        "loan_amount": loan_amount,
        "interest_rate": interest_rate,
        "monthly_payment": payment_details["monthly_payment"],
        "total_payment": payment_details["total_payment"],
        "total_interest": payment_details["total_interest"],
        "term_months": term_months
    }

@app.get("/stats")
def get_financing_stats(db: Session = Depends(get_db)):
    """Get financing statistics"""
    return FinancingCRUD.get_financing_stats(db)

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "financing-service"}