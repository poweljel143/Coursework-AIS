from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import time

from shared.database import get_db, Base, engine
from shared.auth import AuthUtils
from shared.models import TokenData
from models import InsurancePolicy, InsuranceClaim, InsuranceStatus, InsuranceType
from crud import InsuranceCRUD

# Wait for database to be ready
print("Waiting for database connection for Insurance Service...")
for i in range(30):  # Try for 30 seconds
    try:
        with engine.connect() as conn:
            print("Insurance Service Database connection established!")
            break
    except Exception as e:
        print(f"Insurance Service Database not ready, attempt {i+1}/30: {e}")
        time.sleep(1)
else:
    print("Insurance Service: Could not connect to database after 30 attempts")
    raise Exception("Insurance Service: Database connection failed")

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Insurance Service", description="Insurance policy and claims management service for Autosalon")

@app.get("/")
def read_root(db: Session = Depends(get_db)):
    """Get Insurance Service status with insurance statistics"""
    stats = InsuranceCRUD.get_insurance_stats(db)
    return {
        "service": "Insurance Service",
        "status": "running",
        "version": "1.0.0",
        "description": "Vehicle insurance management service",
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

@app.post("/quotes")
def create_quote(
    order_id: int,
    insurance_type: InsuranceType,
    coverage_amount: float,
    vehicle_make: str = None,
    vehicle_model: str = None,
    vehicle_year: int = None,
    vehicle_vin: str = None,
    additional_coverages: dict = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create an insurance quote"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    if coverage_amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid coverage amount")

    policy = InsuranceCRUD.create_policy_quote(
        db=db,
        user_id=current_user.user_id,
        order_id=order_id,
        insurance_type=insurance_type,
        coverage_amount=coverage_amount,
        vehicle_make=vehicle_make,
        vehicle_model=vehicle_model,
        vehicle_year=vehicle_year,
        vehicle_vin=vehicle_vin,
        additional_coverages=additional_coverages
    )

    return {
        "policy_id": policy.id,
        "policy_number": policy.policy_number,
        "insurance_type": policy.insurance_type.value,
        "coverage_amount": policy.coverage_amount,
        "premium_amount": policy.premium_amount,
        "start_date": policy.start_date,
        "end_date": policy.end_date,
        "status": policy.status.value,
        "provider_name": policy.provider_name
    }

@app.put("/policies/{policy_id}/purchase")
def purchase_policy(
    policy_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Purchase an insurance policy"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    policy = InsuranceCRUD.get_policy_by_id(db, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if policy.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    purchased_policy = InsuranceCRUD.purchase_policy(db, policy_id)
    if not purchased_policy:
        raise HTTPException(status_code=400, detail="Cannot purchase policy")

    return {"message": "Policy purchased successfully", "status": purchased_policy.status.value}

@app.put("/policies/{policy_id}/activate")
def activate_policy(
    policy_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Activate a purchased policy (internal call after payment)"""
    # This would typically be called by payment service after payment confirmation
    activated_policy = InsuranceCRUD.activate_policy(db, policy_id)
    if not activated_policy:
        raise HTTPException(status_code=400, detail="Cannot activate policy")

    return {"message": "Policy activated successfully", "status": activated_policy.status.value}

@app.get("/policies/{policy_id}")
def get_policy(
    policy_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get policy details"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    policy = InsuranceCRUD.get_policy_by_id(db, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Users can see their own policies, managers/admins can see all
    if policy.user_id != current_user.user_id and current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "id": policy.id,
        "policy_number": policy.policy_number,
        "insurance_type": policy.insurance_type.value,
        "provider_name": policy.provider_name,
        "coverage_amount": policy.coverage_amount,
        "premium_amount": policy.premium_amount,
        "deductible": policy.deductible,
        "start_date": policy.start_date,
        "end_date": policy.end_date,
        "status": policy.status.value,
        "is_paid": policy.is_paid,
        "vehicle_make": policy.vehicle_make,
        "vehicle_model": policy.vehicle_model,
        "vehicle_year": policy.vehicle_year,
        "additional_coverages": policy.additional_coverages
    }

@app.get("/policies")
def get_user_policies(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all policies for current user"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    policies = InsuranceCRUD.get_policies_by_user(db, current_user.user_id)
    return [{
        "id": policy.id,
        "policy_number": policy.policy_number,
        "insurance_type": policy.insurance_type.value,
        "coverage_amount": policy.coverage_amount,
        "premium_amount": policy.premium_amount,
        "status": policy.status.value,
        "start_date": policy.start_date,
        "end_date": policy.end_date
    } for policy in policies]

@app.get("/orders/{order_id}/policies")
def get_order_policies(
    order_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get insurance policies for an order"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    policies = InsuranceCRUD.get_policies_by_order(db, order_id)

    # Check access (simplified - in real system verify order ownership)
    if policies and policies[0].user_id != current_user.user_id and current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return [{
        "id": policy.id,
        "policy_number": policy.policy_number,
        "insurance_type": policy.insurance_type.value,
        "coverage_amount": policy.coverage_amount,
        "premium_amount": policy.premium_amount,
        "status": policy.status.value
    } for policy in policies]

@app.post("/claims")
def create_claim(
    policy_id: int,
    incident_date: datetime,
    incident_type: str,
    incident_description: str,
    claimed_amount: float,
    documents: list = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create an insurance claim"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify policy ownership
    policy = InsuranceCRUD.get_policy_by_id(db, policy_id)
    if not policy or policy.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    if policy.status != InsuranceStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Policy is not active")

    if claimed_amount <= 0 or claimed_amount > policy.coverage_amount:
        raise HTTPException(status_code=400, detail="Invalid claim amount")

    claim = InsuranceCRUD.create_claim(
        db=db,
        policy_id=policy_id,
        user_id=current_user.user_id,
        incident_date=incident_date,
        incident_type=incident_type,
        incident_description=incident_description,
        claimed_amount=claimed_amount,
        documents=documents
    )

    return {
        "claim_id": claim.id,
        "claim_number": claim.claim_number,
        "status": claim.status,
        "message": "Claim submitted successfully"
    }

@app.get("/claims/{claim_id}")
def get_claim(
    claim_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get claim details"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    claim = InsuranceCRUD.get_claim_by_id(db, claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim.user_id != current_user.user_id and current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "policy_id": claim.policy_id,
        "incident_date": claim.incident_date,
        "incident_type": claim.incident_type,
        "incident_description": claim.incident_description,
        "claimed_amount": claim.claimed_amount,
        "approved_amount": claim.approved_amount,
        "paid_amount": claim.paid_amount,
        "status": claim.status,
        "submitted_at": claim.submitted_at,
        "processed_at": claim.processed_at,
        "paid_at": claim.paid_at,
        "assessor_notes": claim.assessor_notes,
        "rejection_reason": claim.rejection_reason
    }

@app.get("/claims")
def get_user_claims(
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all claims for current user"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    claims = InsuranceCRUD.get_claims_by_user(db, current_user.user_id)
    return [{
        "id": claim.id,
        "claim_number": claim.claim_number,
        "policy_id": claim.policy_id,
        "incident_type": claim.incident_type,
        "claimed_amount": claim.claimed_amount,
        "approved_amount": claim.approved_amount,
        "status": claim.status,
        "submitted_at": claim.submitted_at
    } for claim in claims]

@app.get("/policies/{policy_id}/claims")
def get_policy_claims(
    policy_id: int,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all claims for a policy"""
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Verify policy ownership
    policy = InsuranceCRUD.get_policy_by_id(db, policy_id)
    if not policy or policy.user_id != current_user.user_id and current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")

    claims = InsuranceCRUD.get_claims_by_policy(db, policy_id)
    return [{
        "id": claim.id,
        "claim_number": claim.claim_number,
        "incident_type": claim.incident_type,
        "claimed_amount": claim.claimed_amount,
        "approved_amount": claim.approved_amount,
        "status": claim.status,
        "submitted_at": claim.submitted_at
    } for claim in claims]

# Admin endpoints for processing claims
@app.get("/admin/claims")
def get_all_claims(
    status: str = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[dict]:
    """Get all claims (admin/manager only)"""
    if not current_user or current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(InsuranceClaim)
    if status:
        query = query.filter(InsuranceClaim.status == status)

    claims = query.all()
    return [{
        "id": claim.id,
        "claim_number": claim.claim_number,
        "policy_id": claim.policy_id,
        "user_id": claim.user_id,
        "incident_type": claim.incident_type,
        "claimed_amount": claim.claimed_amount,
        "status": claim.status,
        "submitted_at": claim.submitted_at
    } for claim in claims]

@app.put("/admin/claims/{claim_id}/process")
def process_claim(
    claim_id: int,
    approved_amount: float = 0.0,
    assessor_notes: str = None,
    rejection_reason: str = None,
    current_user: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process an insurance claim (admin/manager only)"""
    if not current_user or current_user.role not in ["manager", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")

    if approved_amount < 0:
        raise HTTPException(status_code=400, detail="Invalid approved amount")

    processed_claim = InsuranceCRUD.process_claim(
        db=db,
        claim_id=claim_id,
        approved_amount=approved_amount,
        assessor_notes=assessor_notes,
        rejection_reason=rejection_reason
    )

    if not processed_claim:
        raise HTTPException(status_code=400, detail="Cannot process claim")

    action = "approved" if approved_amount > 0 else "rejected"
    return {"message": f"Claim {action}", "status": processed_claim.status}

@app.get("/calculator")
def calculate_premium(
    insurance_type: InsuranceType,
    coverage_amount: float,
    vehicle_year: int = None,
    driver_age: int = None,
    accident_history: bool = False
):
    """Calculate insurance premium without creating a policy"""
    if coverage_amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid coverage amount")

    premium = InsuranceCRUD.calculate_premium(
        insurance_type=insurance_type,
        coverage_amount=coverage_amount,
        vehicle_year=vehicle_year,
        driver_age=driver_age,
        accident_history=accident_history
    )

    return {
        "insurance_type": insurance_type.value,
        "coverage_amount": coverage_amount,
        "premium_amount": premium,
        "calculation_factors": {
            "vehicle_year": vehicle_year,
            "driver_age": driver_age,
            "accident_history": accident_history
        }
    }

@app.get("/stats")
def get_insurance_stats(db: Session = Depends(get_db)):
    """Get insurance statistics"""
    return InsuranceCRUD.get_insurance_stats(db)

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "insurance-service"}