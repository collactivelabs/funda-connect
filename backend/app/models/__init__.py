# Import all models so SQLAlchemy/Alembic can discover them
from app.models.audit import AuditLog
from app.models.booking import AvailabilitySlot, BlockedDate, Booking
from app.models.consent import ConsentRecord
from app.models.curriculum import Subject
from app.models.notification import (
    Notification,
    NotificationDelivery,
    NotificationPreference,
    PushSubscription,
)
from app.models.parent import Learner, ParentProfile
from app.models.payment import Payment, Payout, VerificationDocument
from app.models.review import Review
from app.models.teacher import TeacherProfile, TeacherSubject
from app.models.user import User

__all__ = [
    "AuditLog",
    "ConsentRecord",
    "User",
    "TeacherProfile",
    "TeacherSubject",
    "ParentProfile",
    "Learner",
    "Subject",
    "AvailabilitySlot",
    "BlockedDate",
    "Booking",
    "Notification",
    "NotificationDelivery",
    "NotificationPreference",
    "PushSubscription",
    "Payment",
    "Payout",
    "VerificationDocument",
    "Review",
]
