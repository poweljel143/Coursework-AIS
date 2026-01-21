from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SAEnum, Boolean
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from shared.database import Base

class InsuranceType(str, PyEnum):
    OSAGO = "osago"  # Обязательное страхование автогражданской ответственности
    KASKO = "kasko"  # Добровольное страхование автомобиля
    LIFE = "life"    # Страхование жизни
    HEALTH = "health"  # Страхование здоровья

class InsuranceStatus(str, PyEnum):
    DRAFT = "draft"
    QUOTED = "quoted"
    PURCHASED = "purchased"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    CLAIMED = "claimed"

class InsurancePolicy(Base):
    __tablename__ = "insurance_policies"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    order_id = Column(Integer, nullable=False, index=True)  # Reference to sales order
    vehicle_id = Column(Integer, nullable=True)  # Reference to vehicle (if applicable)

    # Policy details
    policy_number = Column(String, unique=True, nullable=False)
    insurance_type = Column(SAEnum(InsuranceType), nullable=False)
    provider_name = Column(String, nullable=False)  # Insurance company name

    # Coverage details
    coverage_amount = Column(Float, nullable=False)  # Maximum coverage
    premium_amount = Column(Float, nullable=False)  # Monthly/annual premium
    deductible = Column(Float, default=0.0)  # Франшиза

    # Dates
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    purchased_at = Column(DateTime(timezone=True), nullable=True)

    # Status and payment
    status = Column(SAEnum(InsuranceStatus), default=InsuranceStatus.DRAFT)
    is_paid = Column(Boolean, default=False)
    payment_date = Column(DateTime(timezone=True), nullable=True)

    # Vehicle details (for context)
    vehicle_make = Column(String, nullable=True)
    vehicle_model = Column(String, nullable=True)
    vehicle_year = Column(Integer, nullable=True)
    vehicle_vin = Column(String, nullable=True)

    # Additional options
    additional_coverages = Column(String, nullable=True)  # JSON string of additional options

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class InsuranceClaim(Base):
    __tablename__ = "insurance_claims"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)

    # Claim details
    claim_number = Column(String, unique=True, nullable=False)
    incident_date = Column(DateTime(timezone=True), nullable=False)
    incident_type = Column(String, nullable=False)  # Accident, theft, damage, etc.
    incident_description = Column(String, nullable=False)

    # Claim amounts
    claimed_amount = Column(Float, nullable=False)
    approved_amount = Column(Float, default=0.0)
    paid_amount = Column(Float, default=0.0)

    # Status and processing
    status = Column(String, default="submitted")  # submitted, under_review, approved, rejected, paid
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)

    # Processing details
    assessor_notes = Column(String, nullable=True)
    rejection_reason = Column(String, nullable=True)

    # Documents (simplified - would be file paths in real system)
    documents = Column(String, nullable=True)  # JSON array of document references