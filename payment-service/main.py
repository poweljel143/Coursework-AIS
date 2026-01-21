from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Header
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio
import time

from shared.database import get_db, Base, engine
from shared.auth import AuthUtils
from shared.models import TokenData
from models import Payment, PaymentStatus, PaymentMethod
from crud import PaymentCRUD

# Wait for database to be ready
print("Waiting for database connection for Payment Service...")
for i in range(30):  # Try for 30 seconds
    try:
        with engine.connect() as conn:
            print("Payment Service Database connection established!")
            break
    except Exception as e:
        print(f"Payment Service Database not ready, attempt {i+1}/30: {e}")
        time.sleep(1)
else:
    print("Payment Service: Could not connect to database after 30 attempts")
    raise Exception("Payment Service: Database connection failed")

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Payment Service", description="Payment processing service for Autosalon")

@app.get("/")
def read_root(db: Session = Depends(get_db)):
    """Get Payment Service status with payment statistics"""
    stats = PaymentCRUD.get_payment_stats(db)
    return {
        "service": "Payment Service",
        "status": "running",
        "version": "1.0.0",
        "description": "Payment processing service for Autosalon",
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

@app.post("/payments")
def create_payment(
    order_id: int,
    amount: float,
    method: PaymentMethod = PaymentMethod.CARD,
    description: str = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new payment"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    payment = PaymentCRUD.create_payment(
        db=db,
        order_id=order_id,
        user_id=current_user.user_id,
        amount=amount,
        method=method,
        description=description
    )

    # Simulate payment processing in background
    background_tasks.add_task(process_payment_background, payment.id, db)

    return {
        "payment_id": payment.id,
        "transaction_id": payment.transaction_id,
        "status": payment.status.value,
        "amount": payment.amount,
        "message": "Payment created and processing started"
    }

async def process_payment_background(payment_id: int, db: Session):
    """Background task to process payment"""
    await asyncio.sleep(2)  # Simulate processing time

    # Simulate 90% success rate
    success = True  # For demo, always succeed
    PaymentCRUD.process_payment(db, payment_id, success)

@app.get("/payments/{payment_id}")
def get_payment(
    payment_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get payment details"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    payment = PaymentCRUD.get_payment_by_id(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Users can only see their own payments (unless admin)
    if payment.user_id != current_user.user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "id": payment.id,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "method": payment.method.value,
        "status": payment.status.value,
        "transaction_id": payment.transaction_id,
        "description": payment.description,
        "created_at": payment.created_at,
        "updated_at": payment.updated_at
    }

@app.get("/payments")
def get_user_payments(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all payments for current user"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    payments = PaymentCRUD.get_payments_by_user(db, current_user.user_id)
    return [{
        "id": payment.id,
        "order_id": payment.order_id,
        "amount": payment.amount,
        "status": payment.status.value,
        "method": payment.method.value,
        "created_at": payment.created_at
    } for payment in payments]

@app.get("/orders/{order_id}/payments")
def get_order_payments(
    order_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all payments for an order"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    payments = PaymentCRUD.get_payments_by_order(db, order_id)

    # Check if user has access to this order's payments
    # In a real system, you'd verify order ownership
    if payments and payments[0].user_id != current_user.user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    return [{
        "id": payment.id,
        "amount": payment.amount,
        "status": payment.status.value,
        "method": payment.method.value,
        "created_at": payment.created_at
    } for payment in payments]

@app.put("/payments/{payment_id}/cancel")
def cancel_payment(
    payment_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a payment (if still pending)"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    payment = PaymentCRUD.get_payment_by_id(db, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.user_id != current_user.user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    cancelled_payment = PaymentCRUD.cancel_payment(db, payment_id)
    if not cancelled_payment:
        raise HTTPException(status_code=400, detail="Payment cannot be cancelled")

    return {"message": "Payment cancelled successfully", "status": cancelled_payment.status.value}

@app.get("/stats")
def get_payment_stats(db: Session = Depends(get_db)):
    """Get payment statistics"""
    return PaymentCRUD.get_payment_stats(db)

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "payment-service"}