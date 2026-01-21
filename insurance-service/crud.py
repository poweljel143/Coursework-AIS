from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
import uuid
import json
from models import InsurancePolicy, InsuranceClaim, InsuranceStatus, InsuranceType
from shared.models import InsuranceEvent
from shared.messaging import message_broker

class InsuranceCRUD:
    @staticmethod
    def calculate_premium(
        insurance_type: InsuranceType,
        coverage_amount: float,
        vehicle_year: int = None,
        driver_age: int = None,
        accident_history: bool = False
    ) -> float:
        """Calculate insurance premium based on risk factors"""
        base_rates = {
            InsuranceType.OSAGO: 0.02,  # 2% of coverage
            InsuranceType.KASKO: 0.05,  # 5% of coverage
            InsuranceType.LIFE: 0.001,  # 0.1% of coverage
            InsuranceType.HEALTH: 0.003  # 0.3% of coverage
        }

        premium = coverage_amount * base_rates.get(insurance_type, 0.03)

        # Risk adjustments
        if vehicle_year and vehicle_year < 2010:
            premium *= 1.2  # Older vehicles are riskier

        if driver_age and driver_age < 25:
            premium *= 1.3  # Younger drivers pay more

        if accident_history:
            premium *= 1.5  # Drivers with accidents pay more

        return round(premium, 2)

    @staticmethod
    def create_policy_quote(
        db: Session,
        user_id: int,
        order_id: int,
        insurance_type: InsuranceType,
        coverage_amount: float,
        vehicle_make: str = None,
        vehicle_model: str = None,
        vehicle_year: int = None,
        vehicle_vin: str = None,
        additional_coverages: dict = None
    ) -> InsurancePolicy:
        """Create an insurance policy quote"""

        premium = InsuranceCRUD.calculate_premium(
            insurance_type=insurance_type,
            coverage_amount=coverage_amount,
            vehicle_year=vehicle_year
        )

        policy = InsurancePolicy(
            user_id=user_id,
            order_id=order_id,
            policy_number=f"POL-{uuid.uuid4().hex[:8].upper()}",
            insurance_type=insurance_type,
            provider_name="AutoInsurance Plus",  # Default provider
            coverage_amount=coverage_amount,
            premium_amount=premium,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=365),
            status=InsuranceStatus.QUOTED,
            vehicle_make=vehicle_make,
            vehicle_model=vehicle_model,
            vehicle_year=vehicle_year,
            vehicle_vin=vehicle_vin,
            additional_coverages=json.dumps(additional_coverages) if additional_coverages else None
        )

        db.add(policy)
        db.commit()
        db.refresh(policy)

        return policy

    @staticmethod
    def purchase_policy(db: Session, policy_id: int) -> Optional[InsurancePolicy]:
        """Purchase an insurance policy"""
        policy = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
        if not policy or policy.status != InsuranceStatus.QUOTED:
            return None

        policy.status = InsuranceStatus.PURCHASED
        policy.purchased_at = datetime.utcnow()
        db.commit()
        db.refresh(policy)

        # Publish event
        event = InsuranceEvent(
            event_id=f"insurance_{policy.id}",
            event_type="insurance.purchased",
            timestamp=policy.purchased_at,
            payload={
                "policy_id": policy.id,
                "user_id": policy.user_id,
                "order_id": policy.order_id,
                "insurance_type": policy.insurance_type.value,
                "premium_amount": policy.premium_amount,
                "status": InsuranceStatus.PURCHASED.value
            }
        )
        message_broker.publish_event("autosalon", "insurance.purchased", event.dict())

        return policy

    @staticmethod
    def activate_policy(db: Session, policy_id: int) -> Optional[InsurancePolicy]:
        """Activate a purchased policy (after payment)"""
        policy = db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()
        if not policy or policy.status != InsuranceStatus.PURCHASED:
            return None

        policy.status = InsuranceStatus.ACTIVE
        policy.is_paid = True
        policy.payment_date = datetime.utcnow()
        db.commit()
        db.refresh(policy)

        # Publish event
        event = InsuranceEvent(
            event_id=f"insurance_{policy.id}_activated",
            event_type="insurance.activated",
            timestamp=policy.payment_date,
            payload={
                "policy_id": policy.id,
                "user_id": policy.user_id,
                "order_id": policy.order_id,
                "insurance_type": policy.insurance_type.value,
                "status": InsuranceStatus.ACTIVE.value
            }
        )
        message_broker.publish_event("autosalon", "insurance.activated", event.dict())

        return policy

    @staticmethod
    def get_policy_by_id(db: Session, policy_id: int) -> Optional[InsurancePolicy]:
        """Get policy by ID"""
        return db.query(InsurancePolicy).filter(InsurancePolicy.id == policy_id).first()

    @staticmethod
    def get_policies_by_user(db: Session, user_id: int) -> List[InsurancePolicy]:
        """Get all policies for a user"""
        return db.query(InsurancePolicy).filter(InsurancePolicy.user_id == user_id).all()

    @staticmethod
    def get_policies_by_order(db: Session, order_id: int) -> List[InsurancePolicy]:
        """Get policies for an order"""
        return db.query(InsurancePolicy).filter(InsurancePolicy.order_id == order_id).all()

    @staticmethod
    def create_claim(
        db: Session,
        policy_id: int,
        user_id: int,
        incident_date: datetime,
        incident_type: str,
        incident_description: str,
        claimed_amount: float,
        documents: list = None
    ) -> InsuranceClaim:
        """Create an insurance claim"""

        claim = InsuranceClaim(
            policy_id=policy_id,
            user_id=user_id,
            claim_number=f"CLM-{uuid.uuid4().hex[:8].upper()}",
            incident_date=incident_date,
            incident_type=incident_type,
            incident_description=incident_description,
            claimed_amount=claimed_amount,
            documents=json.dumps(documents) if documents else None
        )

        db.add(claim)
        db.commit()
        db.refresh(claim)

        # Publish event
        event = InsuranceEvent(
            event_id=f"claim_{claim.id}",
            event_type="insurance.claim.submitted",
            timestamp=claim.submitted_at,
            payload={
                "claim_id": claim.id,
                "policy_id": policy_id,
                "user_id": user_id,
                "claimed_amount": claimed_amount,
                "status": "submitted"
            }
        )
        message_broker.publish_event("autosalon", "insurance.claim.submitted", event.dict())

        return claim

    @staticmethod
    def process_claim(
        db: Session,
        claim_id: int,
        approved_amount: float = 0.0,
        assessor_notes: str = None,
        rejection_reason: str = None
    ) -> Optional[InsuranceClaim]:
        """Process an insurance claim"""
        claim = db.query(InsuranceClaim).filter(InsuranceClaim.id == claim_id).first()
        if not claim or claim.status != "submitted":
            return None

        claim.processed_at = datetime.utcnow()
        claim.approved_amount = approved_amount
        claim.assessor_notes = assessor_notes

        if approved_amount > 0:
            claim.status = "approved"
            claim.paid_amount = approved_amount
            claim.paid_at = datetime.utcnow()
        else:
            claim.status = "rejected"
            claim.rejection_reason = rejection_reason

        db.commit()
        db.refresh(claim)

        # Publish event
        event_type = "insurance.claim.approved" if approved_amount > 0 else "insurance.claim.rejected"
        event = InsuranceEvent(
            event_id=f"claim_{claim.id}_processed",
            event_type=event_type,
            timestamp=claim.processed_at,
            payload={
                "claim_id": claim.id,
                "policy_id": claim.policy_id,
                "user_id": claim.user_id,
                "approved_amount": approved_amount,
                "status": claim.status
            }
        )
        message_broker.publish_event("autosalon", event_type, event.dict())

        return claim

    @staticmethod
    def get_claim_by_id(db: Session, claim_id: int) -> Optional[InsuranceClaim]:
        """Get claim by ID"""
        return db.query(InsuranceClaim).filter(InsuranceClaim.id == claim_id).first()

    @staticmethod
    def get_claims_by_user(db: Session, user_id: int) -> List[InsuranceClaim]:
        """Get all claims for a user"""
        return db.query(InsuranceClaim).filter(InsuranceClaim.user_id == user_id).all()

    @staticmethod
    def get_claims_by_policy(db: Session, policy_id: int) -> List[InsuranceClaim]:
        """Get all claims for a policy"""
        return db.query(InsuranceClaim).filter(InsuranceClaim.policy_id == policy_id).all()

    @staticmethod
    def get_insurance_stats(db: Session) -> dict:
        """Get insurance statistics"""
        from sqlalchemy import func

        # Policies statistics
        total_policies = db.query(InsurancePolicy).count()
        active_policies = db.query(InsurancePolicy).filter(InsurancePolicy.status == InsuranceStatus.ACTIVE).count()

        # Policy status distribution
        policy_status_counts = db.query(InsurancePolicy.status, func.count(InsurancePolicy.id))\
                               .group_by(InsurancePolicy.status).all()
        policy_status_distribution = {status.value: count for status, count in policy_status_counts}

        # Insurance type distribution
        type_counts = db.query(InsurancePolicy.insurance_type, func.count(InsurancePolicy.id))\
                       .group_by(InsurancePolicy.insurance_type).all()
        type_distribution = {itype.value: count for itype, count in type_counts}

        # Premium statistics
        total_premium = db.query(func.sum(InsurancePolicy.premium_amount)).scalar() or 0
        avg_premium = db.query(func.avg(InsurancePolicy.premium_amount)).scalar() or 0

        # Claims statistics
        total_claims = db.query(InsuranceClaim).count()
        approved_claims = db.query(InsuranceClaim).filter(InsuranceClaim.status == "approved").count()
        rejected_claims = db.query(InsuranceClaim).filter(InsuranceClaim.status == "rejected").count()

        # Total claimed and paid amounts
        total_claimed = db.query(func.sum(InsuranceClaim.claimed_amount)).scalar() or 0
        total_paid = db.query(func.sum(InsuranceClaim.paid_amount)).scalar() or 0

        # Recent policies (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_policies = db.query(InsurancePolicy)\
                           .filter(InsurancePolicy.created_at >= thirty_days_ago).count()

        return {
            "total_policies": total_policies,
            "active_policies": active_policies,
            "policy_status_distribution": policy_status_distribution,
            "type_distribution": type_distribution,
            "total_premium_collected": float(total_premium),
            "average_premium": float(avg_premium),
            "total_claims": total_claims,
            "approved_claims": approved_claims,
            "rejected_claims": rejected_claims,
            "total_claimed_amount": float(total_claimed),
            "total_paid_amount": float(total_paid),
            "recent_policies_30_days": recent_policies
        }