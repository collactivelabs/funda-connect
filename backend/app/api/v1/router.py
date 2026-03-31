from fastapi import APIRouter

from app.api.v1.endpoints import (
    account,
    admin,
    auth,
    bookings,
    notifications,
    parents,
    reference_data,
    reviews,
    subjects,
    teachers,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(account.router, prefix="/account", tags=["account"])
api_router.include_router(teachers.router, prefix="/teachers", tags=["teachers"])
api_router.include_router(parents.router, prefix="/parents", tags=["parents"])
api_router.include_router(bookings.router, prefix="/bookings", tags=["bookings"])
api_router.include_router(subjects.router, prefix="/subjects", tags=["subjects"])
api_router.include_router(reference_data.router, tags=["reference-data"])
api_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
