from fastapi import APIRouter

from app.api import activity, admin, auth, health, lessons, profiles, progress, progressive_learning, recordings, recitation_audio, scriptures

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(activity.router)
api_router.include_router(profiles.router)
api_router.include_router(scriptures.router)
api_router.include_router(lessons.router)
api_router.include_router(recordings.router)
api_router.include_router(recitation_audio.router)
api_router.include_router(progressive_learning.router)
api_router.include_router(progress.router)
api_router.include_router(admin.router)
