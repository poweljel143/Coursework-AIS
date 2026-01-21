from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SAEnum, ForeignKey
from enum import Enum as PyEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from shared.database import Base

class PaymentStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PaymentMethod(str, PyEnum):
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"
    CREDIT = "credit"

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, nullable=False, index=True)  # Reference to sales order
    user_id = Column(Integer, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="RUB", nullable=False)
    method = Column(SAEnum(PaymentMethod), default=PaymentMethod.CARD)
    status = Column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING)
    transaction_id = Column(String, unique=True, nullable=True)
    description = Column(String, nullable=True)

    # Payment details
    card_last_four = Column(String(4), nullable=True)
    bank_reference = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class PaymentLog(Base):
    __tablename__ = "payment_logs"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    action = Column(String, nullable=False)  # created, processed, completed, failed
    old_status = Column(SAEnum(PaymentStatus), nullable=True)
    new_status = Column(SAEnum(PaymentStatus), nullable=False)
    message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payment = relationship("Payment")