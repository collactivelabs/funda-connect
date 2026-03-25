# Import all models so SQLAlchemy/Alembic can discover them
from app.models.booking import AvailabilitySlot, Booking
from app.models.curriculum import Subject
from app.models.parent import Learner, ParentProfile
from app.models.payment import Payout, Payment, VerificationDocument
from app.models.review import Review
from app.models.teacher import TeacherProfile, TeacherSubject
from app.models.user import User

__all__ = [
    "User",
    "TeacherProfile",
    "TeacherSubject",
    "ParentProfile",
    "Learner",
    "Subject",
    "AvailabilitySlot",
    "Booking",
    "Payment",
    "Payout",
    "VerificationDocument",
    "Review",
]
