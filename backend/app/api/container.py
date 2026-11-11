"""Process-wide providers, built once from configuration and injected via app.state.

Selection happens here and nowhere else. Missing configuration yields an "unconfigured"
provider that fails loudly; live SMS never silently becomes simulation.
"""

from dataclasses import dataclass, field

from app.core.config import Settings
from app.integrations.auth_provider import (
    AuthProvider,
    SupabaseAuthProvider,
    UnconfiguredAuthProvider,
)
from app.integrations.otp_delivery import (
    OtpDelivery,
    SimulatedInbox,
    SimulatedOtpDelivery,
    UnavailableLiveOtpDelivery,
)
from app.integrations.storage_provider import (
    StorageProvider,
    SupabaseStorageProvider,
    UnconfiguredStorageProvider,
)
from app.modules.profiles.presence import PresenceRegistry


@dataclass
class Providers:
    auth: AuthProvider
    storage: StorageProvider
    otp: OtpDelivery
    inbox: SimulatedInbox = field(default_factory=SimulatedInbox)
    presence: PresenceRegistry = field(default_factory=PresenceRegistry)

    async def aclose(self) -> None:
        for provider in (self.auth, self.storage):
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
    if settings.supabase_url and service_key:
        storage = SupabaseStorageProvider(
            base_url=settings.supabase_url,
            service_role_key=service_key,
            bucket=settings.avatar_bucket,
        )
    else:
        storage = UnconfiguredStorageProvider()

    inbox = SimulatedInbox()
    otp: OtpDelivery = (
        SimulatedOtpDelivery(inbox)
        if settings.sms_provider_mode == "mock"
        else UnavailableLiveOtpDelivery()
    )
    return Providers(auth=auth, storage=storage, otp=otp, inbox=inbox)
