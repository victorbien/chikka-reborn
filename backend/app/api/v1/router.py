from fastapi import APIRouter

from app.api.v1 import health
from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.chat.router import router as chat_router
from app.modules.contacts.router import router as contacts_router
from app.modules.credits.router import admin_router as credits_admin_router
from app.modules.credits.router import router as credits_router
from app.modules.notifications.router import admin_router as notifications_admin_router
from app.modules.notifications.router import router as notifications_router
from app.modules.profiles.router import router as profile_router
from app.modules.sms.admin_router import router as sms_admin_router
from app.modules.sms.router import router as sms_router
from app.modules.sms.webhook_router import router as sms_webhook_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(contacts_router)
api_router.include_router(chat_router)
api_router.include_router(ai_router)
api_router.include_router(notifications_router)
api_router.include_router(notifications_admin_router)
api_router.include_router(credits_router)
api_router.include_router(credits_admin_router)
api_router.include_router(sms_router)
api_router.include_router(sms_webhook_router)
api_router.include_router(sms_admin_router)
