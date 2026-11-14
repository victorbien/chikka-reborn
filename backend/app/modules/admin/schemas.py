"""Response and request models for the administration dashboard (Module J).

Nothing here carries message bodies, AI prompts or outputs, secrets, full phone numbers or full
email addresses.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AccountStatusFilter = Literal["pending_verification", "active", "suspended", "deleted"]
RoleFilter = Literal["user", "admin"]
RestrictionReason = Literal["abuse", "spam", "fraud", "security", "other"]
Health = Literal["healthy", "degraded", "paused", "unavailable"]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


# -- dashboard -----------------------------------------------------------------------------


class UserStats(BaseModel):
    total_registered: int
    active_accounts: int
    pending_verification: int
    suspended: int
    administrators: int
    active_last_24h: int
    active_last_7d: int
    active_last_30d: int


class ConversationStats(BaseModel):
    total: int
    chikka: int
    sms: int


class SmsModeStats(BaseModel):
    """Live and simulated traffic are never added together."""

    sent: int
    received: int
    delivered: int
    failed: int
    undelivered: int
    in_progress: int
    delivery_success_rate: float | None


class SmsStats(BaseModel):
    live: SmsModeStats
    simulated: SmsModeStats


class MessageStats(BaseModel):
    chikka_messages_sent: int


class AiStats(BaseModel):
    total_requests: int
    last_24h: int
    failed_requests: int
    input_tokens: int
    output_tokens: int


class CreditLedgerStats(BaseModel):
    ledger_type: Literal["live", "demo"]
    transactions: int
    units_granted: int
    units_deducted: int
    units_refunded: int
    units_adjusted: int


class DashboardOut(BaseModel):
    generated_at: datetime
    users: UserStats
    conversations: ConversationStats
    messages: MessageStats
    sms: SmsStats
    ai: AiStats
    credits: list[CreditLedgerStats]


# -- users ---------------------------------------------------------------------------------


class AdminUserRow(BaseModel):
    id: UUID
    username: str | None
    display_name: str | None
    masked_email: str | None
    role: str
    status: str
    country_code: str | None
    created_at: datetime
    last_seen_at: datetime | None
    suspended_at: datetime | None


class CreditBalanceOut(BaseModel):
    ledger_type: str
    balance_units: int
    reserved_units: int


class UserActivityOut(BaseModel):
    chikka_messages_sent: int
    sms_sent: int
    sms_received: int
    conversations: int
    ai_requests: int
    open_reports_against: int
    active_sessions: int


class AdminUserDetail(AdminUserRow):
    masked_verified_phone: str | None
    ai_enabled: bool
    deletion_requested_at: datetime | None
    activity: UserActivityOut
    credits: list[CreditBalanceOut]


class RestrictRequest(StrictRequest):
    reason_code: RestrictionReason


# -- SMS monitoring ------------------------------------------------------------------------


class SmsMessageRow(BaseModel):
    id: UUID
    direction: Literal["outbound", "inbound"]
    status: str
    is_simulated: bool
    created_at: datetime
    masked_phone: str | None
    user_id: UUID | None
    segment_count: int | None
    attempts: int
    provider_message_id: str | None
    failure_class: str | None
    failure_code: str | None
    failure_reason: str | None


class DeliveryEventOut(BaseModel):
    source: str
    provider_status: str | None
    normalised_status: str
    applied: bool
    ignore_reason: str | None
    received_at: datetime


class DeliveryAttemptOut(BaseModel):
    attempt_number: int
    status: str
    provider_message_id: str | None
    is_simulated: bool
    failure_class: str | None
    failure_code: str | None
    failure_reason: str | None
    is_permanent: bool | None
    started_at: datetime | None
    next_attempt_at: datetime | None
    terminal_at: datetime | None
    events: list[DeliveryEventOut]


class SmsMessageDetail(SmsMessageRow):
    attempts_history: list[DeliveryAttemptOut]


# -- providers -----------------------------------------------------------------------------


class ProviderHealthOut(BaseModel):
    health: Health
    reasons: list[str]
    mode: Literal["simulation", "live"] | None
    running_provider: str | None
    active_provider: str | None
    credentials_configured: bool
    outbound_paused: bool
    dispatch_paused_by_configuration_error: bool
    queue_depth: int
    delivery_success_rate_24h: float | None
    webhook_failures_24h: int
    webhook_signature_rejections_24h: int


class CountryCapabilityOut(BaseModel):
    country_code: str
    country_name: str
    outbound_support: str
    inbound_support: str
    registered_sender_required: bool
    registered_sender_status: str
    verified: bool


class ConfigurationStatusOut(BaseModel):
    app_env: str
    sms_provider_mode: str
    sms_live_confirmed: bool
    sms_worker_enabled: bool
    ai_provider_mode: str
    ai_provider_configured: bool
    email_provider_mode: str


class ProviderOverviewOut(BaseModel):
    health: ProviderHealthOut
    configuration: ConfigurationStatusOut
    capabilities: list[CountryCapabilityOut]


# -- AI monitoring -------------------------------------------------------------------------


class AiFeatureUsage(BaseModel):
    feature: str
    requests: int
    failures: int
    accepted: int
    average_latency_ms: int | None
    input_tokens: int
    output_tokens: int


class AiErrorCount(BaseModel):
    outcome: str
    error_code: str | None
    count: int


class AiDayUsage(BaseModel):
    day: str
    requests: int


class AiMetricsOut(BaseModel):
    window_days: int
    total_requests: int
    failed_requests: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float | None = Field(
        description="Only when AI_COST_PER_1K_INPUT_USD and AI_COST_PER_1K_OUTPUT_USD are set."
    )
    features: list[AiFeatureUsage]
    errors: list[AiErrorCount]
    daily: list[AiDayUsage]


# -- audit ---------------------------------------------------------------------------------


class AuditLogRow(BaseModel):
    id: UUID
    created_at: datetime
    category: str
    action: str
    outcome: str
    actor_id: UUID | None
    actor_role: str | None
    target_type: str | None
    target_id: str | None
    request_id: str | None
