from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SAEnum, Boolean
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from shared.database import Base

class FinancingStatus(str, PyEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    COMPLETED = "completed"
    DEFAULTED = "defaulted"

class FinancingType(str, PyEnum):
    CAR_LOAN = "car_loan"
    LEASING = "leasing"
    INSTALLMENT = "installment"

class FinancingApplication(Base):
    __tablename__ = "financing_applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    order_id = Column(Integer, nullable=False, index=True)
    vehicle_price = Column(Float, nullable=False)
    down_payment = Column(Float, default=0.0)
    loan_amount = Column(Float, nullable=False)
    financing_type = Column(SAEnum(FinancingType), default=FinancingType.CAR_LOAN)
    term_months = Column(Integer, nullable=False)  # 12, 24, 36, etc.
    interest_rate = Column(Float, nullable=False)  # Annual percentage
    monthly_payment = Column(Float, nullable=False)
    total_payment = Column(Float, nullable=False)  # Total amount to be paid

    # Application status
    status = Column(SAEnum(FinancingStatus), default=FinancingStatus.DRAFT)

    # Additional info
    employment_status = Column(String, nullable=True)
    monthly_income = Column(Float, nullable=True)
    credit_score = Column(Integer, nullable=True)  # 300-850 scale
    notes = Column(String, nullable=True)

    # Approval details
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by = Column(Integer, nullable=True)  # Manager/Admin ID

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class FinancingSchedule(Base):
    __tablename__ = "financing_schedules"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, nullable=False, index=True)
    payment_number = Column(Integer, nullable=False)  # 1, 2, 3, ...
    due_date = Column(DateTime(timezone=True), nullable=False)
    principal_amount = Column(Float, nullable=False)
    interest_amount = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    remaining_balance = Column(Float, nullable=False)
    is_paid = Column(Boolean, default=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())