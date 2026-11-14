"""Process-wide providers, built once from configuration and injected via app.state.

Selection happens here and nowhere else. Missing configuration yields an "unconfigured"
provider that fails loudly; live SMS never silently becomes simulation.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.config import Settings
from app.integrations.ai.base import AiProvider
from app.integrations.auth_provider import (
    AuthProvider,
    SupabaseAuthProvider,
    UnconfiguredAuthProvider,
)
from app.integrations.email.base import EmailProvider
from app.integrations.otp_delivery import (
    OtpDelivery,
    SimulatedInbox,
    SimulatedOtpDelivery,
    UnavailableLiveOtpDelivery,
)
from app.integrations.sms.base import SmsProvider
from app.integrations.sms.factory import build_sms_provider
from app.integrations.storage_provider import (
    StorageProvider,
    SupabaseStorageProvider,
    UnconfiguredStorageProvider,
)
from app.modules.profiles.presence import PresenceRegistry
from app.realtime.hub import RealtimeHub


@dataclass
class Providers:
    auth: AuthProvider
    storage: StorageProvider
    otp: OtpDelivery
    inbox: SimulatedInbox = field(default_factory=SimulatedInbox)
    presence: PresenceRegistry = field(default_factory=PresenceRegistry)
    # Message attachments live in their own private bucket.
    attachment_storage: StorageProvider = field(default_factory=UnconfiguredStorageProvider)
    realtime: RealtimeHub = field(default_factory=RealtimeHub)
    # Chosen once from configuration (integrations/sms/factory.py). None means "build from
    # settings"; create_app fills it in, so a live failure surfaces at startup.
    sms: SmsProvider | None = None
    # Same rule for AI: filled in by create_app so a Bedrock misconfiguration fails at startup.
    ai: AiProvider | None = None
    # Notification email. Filled in by create_app, same rule as sms and ai.
    email: EmailProvider | None = None
    # Time source for the SMS subsystem. Tests replace it so retries and timelines are exact.
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    # Seeded in tests so retry jitter is deterministic.
    rng: random.Random | None = None

    async def aclose(self) -> None:
        for provider in (
            self.auth,
            self.storage,
            self.attachment_storage,
            self.sms,
            self.ai,
            self.email,
        ):
            close = getattr(provider, "aclose", None)
            if close is not None:
                await close()


def build_providers(settings: Settings) -> Providers:
    service_key = (
        settings.supabase_service_role_key.get_secret_value()
        if settings.supabase_service_role_key
        else None
    )

    auth: AuthProvider
    if settings.supabase_url and settings.supabase_anon_key:
        auth = SupabaseAuthProvider(
            base_url=settings.supabase_url,
            anon_key=settings.supabase_anon_key.get_secret_value(),
            service_role_key=service_key,
        )
    else:
        auth = UnconfiguredAuthProvider()

    storage: StorageProvider
    attachment_storage: StorageProvider
    if settings.supabase_url and service_key:
        storage = SupabaseStorageProvider(
            base_url=settings.supabase_url,
            service_role_key=service_key,
            bucket=settings.avatar_bucket,
        )
        attachment_storage = SupabaseStorageProvider(
            base_url=settings.supabase_url,
            service_role_key=service_key,
            bucket=settings.attachment_bucket,
        )
    else:
        storage = UnconfiguredStorageProvider()
        attachment_storage = UnconfiguredStorageProvider()

    inbox = SimulatedInbox()
    otp: OtpDelivery = (
        SimulatedOtpDelivery(inbox)
        if settings.sms_provider_mode == "mock"
        else UnavailableLiveOtpDelivery()
    )
    return Providers(
        auth=auth,
        storage=storage,
        otp=otp,
        inbox=inbox,
        attachment_storage=attachment_storage,
        sms=build_sms_provider(settings),
    )
