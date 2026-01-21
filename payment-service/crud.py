from sqlalchemy.orm import Session
from models import Payment, PaymentLog, PaymentStatus, PaymentMethod
from shared.models import PaymentEvent
from shared.messaging import message_broker
from typing import List, Optional
import uuid

class PaymentCRUD:
    @staticmethod
    def create_payment(db: Session, order_id: int, user_id: int, amount: float,
                      method: PaymentMethod = PaymentMethod.CARD, description: str = None) -> Payment:
        """Create a new payment"""
        transaction_id = str(uuid.uuid4())
        payment = Payment(
            order_id=order_id,
            user_id=user_id,
            amount=amount,
            method=method,
            transaction_id=transaction_id,
            description=description
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        # Log creation
        PaymentCRUD._log_payment_action(db, payment.id, "created", None, PaymentStatus.PENDING)

        # Publish event
        event = PaymentEvent(
            event_id=f"payment_{payment.id}",
            event_type="payment.created",
            timestamp=payment.created_at,
            payload={
                "payment_id": payment.id,
                "order_id": order_id,
                "user_id": user_id,
                "amount": amount,
                "status": PaymentStatus.PENDING.value
            }
        )
        message_broker.publish_event("autosalon", "payment.created", event.dict())

        return payment

    @staticmethod
    def get_payment_by_id(db: Session, payment_id: int) -> Optional[Payment]:
        """Get payment by ID"""
        return db.query(Payment).filter(Payment.id == payment_id).first()

    @staticmethod
    def get_payments_by_user(db: Session, user_id: int) -> List[Payment]:
        """Get all payments for a user"""
        return db.query(Payment).filter(Payment.user_id == user_id).all()

    @staticmethod
    def get_payments_by_order(db: Session, order_id: int) -> List[Payment]:
        """Get all payments for an order"""
        return db.query(Payment).filter(Payment.order_id == order_id).all()

    @staticmethod
    def process_payment(db: Session, payment_id: int, success: bool = True) -> Optional[Payment]:
        """Process a payment (simulate payment gateway)"""
        payment = PaymentCRUD.get_payment_by_id(db, payment_id)
        if not payment:
            return None

        old_status = payment.status
        new_status = PaymentStatus.COMPLETED if success else PaymentStatus.FAILED

        payment.status = new_status
        db.commit()
        db.refresh(payment)

        # Log status change
        PaymentCRUD._log_payment_action(db, payment.id, "processed", old_status, new_status)

        # Publish event
        event_type = "payment.succeeded" if success else "payment.failed"
        event = PaymentEvent(
            event_id=f"payment_{payment.id}_{event_type}",
            event_type=event_type,
            timestamp=payment.updated_at,
            payload={
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "user_id": payment.user_id,
                "amount": payment.amount,
                "status": new_status.value
            }
        )
        message_broker.publish_event("autosalon", event_type, event.dict())

        return payment

    @staticmethod
    def cancel_payment(db: Session, payment_id: int) -> Optional[Payment]:
        """Cancel a payment"""
        payment = PaymentCRUD.get_payment_by_id(db, payment_id)
        if not payment or payment.status in [PaymentStatus.COMPLETED, PaymentStatus.FAILED]:
            return None

        old_status = payment.status
        payment.status = PaymentStatus.CANCELLED
        db.commit()
        db.refresh(payment)

        # Log status change
        PaymentCRUD._log_payment_action(db, payment.id, "cancelled", old_status, PaymentStatus.CANCELLED)

        # Publish event
        event = PaymentEvent(
            event_id=f"payment_{payment.id}_cancelled",
            event_type="payment.cancelled",
            timestamp=payment.updated_at,
            payload={
                "payment_id": payment.id,
                "order_id": payment.order_id,
                "user_id": payment.user_id,
                "amount": payment.amount,
                "status": PaymentStatus.CANCELLED.value
            }
        )
        message_broker.publish_event("autosalon", "payment.cancelled", event.dict())

        return payment

    @staticmethod
    def _log_payment_action(db: Session, payment_id: int, action: str,
                           old_status: PaymentStatus, new_status: PaymentStatus):
        """Log payment action"""
        log_entry = PaymentLog(
            payment_id=payment_id,
            action=action,
            old_status=old_status,
            new_status=new_status
        )
        db.add(log_entry)
        db.commit()

    @staticmethod
    def get_payment_stats(db: Session) -> dict:
        """Get payment statistics"""
        from sqlalchemy import func

        # Total payments count
        total_payments = db.query(Payment).count()

        # Status distribution
        status_counts = db.query(Payment.status, func.count(Payment.id)).group_by(Payment.status).all()
        status_distribution = {status.value: count for status, count in status_counts}

        # Method distribution
        method_counts = db.query(Payment.method, func.count(Payment.id)).group_by(Payment.method).all()
        method_distribution = {method.value: count for method, count in method_counts}

        # Total amount by currency
        total_amounts = db.query(Payment.currency, func.sum(Payment.amount)).group_by(Payment.currency).all()
        total_amount_by_currency = {currency: float(amount) for currency, amount in total_amounts}

        # Recent payments (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_payments = db.query(Payment).filter(Payment.created_at >= thirty_days_ago).count()

        return {
            "total_payments": total_payments,
            "status_distribution": status_distribution,
            "method_distribution": method_distribution,
            "total_amount_by_currency": total_amount_by_currency,
            "recent_payments_30_days": recent_payments
        }