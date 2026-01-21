from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional
from models import FinancingApplication, FinancingSchedule, FinancingStatus, FinancingType
from shared.models import FinancingEvent
from shared.messaging import message_broker

class FinancingCRUD:
    @staticmethod
    def calculate_loan_payment(principal: float, annual_rate: float, term_months: int) -> dict:
        """Calculate monthly payment and total cost for a loan"""
        monthly_rate = annual_rate / 100 / 12
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate) ** term_months) / ((1 + monthly_rate) ** term_months - 1)
        total_payment = monthly_payment * term_months

        return {
            "monthly_payment": round(monthly_payment, 2),
            "total_payment": round(total_payment, 2),
            "total_interest": round(total_payment - principal, 2)
        }

    @staticmethod
    def create_application(
        db: Session,
        user_id: int,
        order_id: int,
        vehicle_price: float,
        down_payment: float,
        term_months: int,
        financing_type: FinancingType = FinancingType.CAR_LOAN,
        employment_status: str = None,
        monthly_income: float = None
    ) -> FinancingApplication:
        """Create a new financing application"""

        loan_amount = vehicle_price - down_payment
        interest_rate = FinancingCRUD._get_interest_rate(loan_amount, term_months, employment_status)

        payment_details = FinancingCRUD.calculate_loan_payment(loan_amount, interest_rate, term_months)

        application = FinancingApplication(
            user_id=user_id,
            order_id=order_id,
            vehicle_price=vehicle_price,
            down_payment=down_payment,
            loan_amount=loan_amount,
            financing_type=financing_type,
            term_months=term_months,
            interest_rate=interest_rate,
            monthly_payment=payment_details["monthly_payment"],
            total_payment=payment_details["total_payment"],
            employment_status=employment_status,
            monthly_income=monthly_income,
            status=FinancingStatus.DRAFT
        )

        db.add(application)
        db.commit()
        db.refresh(application)

        # Publish event
        event = FinancingEvent(
            event_id=f"financing_{application.id}",
            event_type="financing.created",
            timestamp=application.created_at,
            payload={
                "application_id": application.id,
                "user_id": user_id,
                "order_id": order_id,
                "loan_amount": loan_amount,
                "status": FinancingStatus.DRAFT.value
            }
        )
        message_broker.publish_event("autosalon", "financing.created", event.dict())

        return application

    @staticmethod
    def submit_application(db: Session, application_id: int) -> Optional[FinancingApplication]:
        """Submit application for review"""
        application = db.query(FinancingApplication).filter(FinancingApplication.id == application_id).first()
        if not application or application.status != FinancingStatus.DRAFT:
            return None

        application.status = FinancingStatus.SUBMITTED
        db.commit()
        db.refresh(application)

        # Publish event
        event = FinancingEvent(
            event_id=f"financing_{application.id}_submitted",
            event_type="financing.submitted",
            timestamp=application.updated_at,
            payload={
                "application_id": application.id,
                "user_id": application.user_id,
                "order_id": application.order_id,
                "loan_amount": application.loan_amount,
                "status": FinancingStatus.SUBMITTED.value
            }
        )
        message_broker.publish_event("autosalon", "financing.submitted", event.dict())

        return application

    @staticmethod
    def review_application(db: Session, application_id: int, approved: bool, reviewer_id: int,
                          notes: str = None) -> Optional[FinancingApplication]:
        """Review and approve/reject application"""
        application = db.query(FinancingApplication).filter(FinancingApplication.id == application_id).first()
        if not application or application.status != FinancingStatus.SUBMITTED:
            return None

        if approved:
            application.status = FinancingStatus.APPROVED
            application.approved_at = datetime.utcnow()
            application.approved_by = reviewer_id

            # Create payment schedule
            FinancingCRUD._create_payment_schedule(db, application)
        else:
            application.status = FinancingStatus.REJECTED

        if notes:
            application.notes = notes

        db.commit()
        db.refresh(application)

        # Publish event
        event_type = "financing.approved" if approved else "financing.rejected"
        event = FinancingEvent(
            event_id=f"financing_{application.id}_{event_type}",
            event_type=event_type,
            timestamp=application.updated_at,
            payload={
                "application_id": application.id,
                "user_id": application.user_id,
                "order_id": application.order_id,
                "approved": approved,
                "status": application.status.value
            }
        )
        message_broker.publish_event("autosalon", event_type, event.dict())

        return application

    @staticmethod
    def get_application_by_id(db: Session, application_id: int) -> Optional[FinancingApplication]:
        """Get application by ID"""
        return db.query(FinancingApplication).filter(FinancingApplication.id == application_id).first()

    @staticmethod
    def get_applications_by_user(db: Session, user_id: int) -> List[FinancingApplication]:
        """Get all applications for a user"""
        return db.query(FinancingApplication).filter(FinancingApplication.user_id == user_id).all()

    @staticmethod
    def get_applications_by_order(db: Session, order_id: int) -> List[FinancingApplication]:
        """Get applications for an order"""
        return db.query(FinancingApplication).filter(FinancingApplication.order_id == order_id).all()

    @staticmethod
    def get_payment_schedule(db: Session, application_id: int) -> List[FinancingSchedule]:
        """Get payment schedule for an application"""
        return db.query(FinancingSchedule).filter(FinancingSchedule.application_id == application_id)\
               .order_by(FinancingSchedule.payment_number).all()

    @staticmethod
    def _get_interest_rate(loan_amount: float, term_months: int, employment_status: str = None) -> float:
        """Calculate interest rate based on loan parameters"""
        base_rate = 12.0  # Base annual rate

        # Adjust based on loan amount
        if loan_amount > 3000000:
            base_rate += 1.0
        elif loan_amount < 500000:
            base_rate -= 0.5

        # Adjust based on term
        if term_months > 60:
            base_rate += 1.5
        elif term_months < 24:
            base_rate -= 0.5

        # Adjust based on employment
        if employment_status == "employed":
            base_rate -= 0.5
        elif employment_status == "self_employed":
            base_rate += 0.5

        return max(5.0, min(25.0, base_rate))  # Clamp between 5% and 25%

    @staticmethod
    def _create_payment_schedule(db: Session, application: FinancingApplication):
        """Create payment schedule for approved application"""
        monthly_rate = application.interest_rate / 100 / 12
        remaining_balance = application.loan_amount
        monthly_payment = application.monthly_payment

        current_date = datetime.utcnow()

        for month in range(1, application.term_months + 1):
            interest_payment = remaining_balance * monthly_rate
            principal_payment = monthly_payment - interest_payment

            schedule_entry = FinancingSchedule(
                application_id=application.id,
                payment_number=month,
                due_date=current_date + timedelta(days=30 * month),
                principal_amount=round(principal_payment, 2),
                interest_amount=round(interest_payment, 2),
                total_amount=round(monthly_payment, 2),
                remaining_balance=round(remaining_balance - principal_payment, 2)
            )

            db.add(schedule_entry)
            remaining_balance -= principal_payment

        db.commit()

    @staticmethod
    def get_financing_stats(db: Session) -> dict:
        """Get financing statistics"""
        from sqlalchemy import func

        # Total applications count
        total_applications = db.query(FinancingApplication).count()

        # Status distribution
        status_counts = db.query(FinancingApplication.status, func.count(FinancingApplication.id))\
                         .group_by(FinancingApplication.status).all()
        status_distribution = {status.value: count for status, count in status_counts}

        # Type distribution
        type_counts = db.query(FinancingApplication.financing_type, func.count(FinancingApplication.id))\
                       .group_by(FinancingApplication.financing_type).all()
        type_distribution = {ftype.value: count for ftype, count in type_counts}

        # Total loan amounts
        total_loan_amount = db.query(func.sum(FinancingApplication.loan_amount)).scalar() or 0
        total_vehicle_price = db.query(func.sum(FinancingApplication.vehicle_price)).scalar() or 0

        # Average loan amount and term
        avg_loan_amount = db.query(func.avg(FinancingApplication.loan_amount)).scalar() or 0
        avg_term = db.query(func.avg(FinancingApplication.term_months)).scalar() or 0

        # Recent applications (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_applications = db.query(FinancingApplication)\
                               .filter(FinancingApplication.created_at >= thirty_days_ago).count()

        return {
            "total_applications": total_applications,
            "status_distribution": status_distribution,
            "type_distribution": type_distribution,
            "total_loan_amount": float(total_loan_amount),
            "total_vehicle_price": float(total_vehicle_price),
            "average_loan_amount": float(avg_loan_amount),
            "average_term_months": float(avg_term),
            "recent_applications_30_days": recent_applications
        }