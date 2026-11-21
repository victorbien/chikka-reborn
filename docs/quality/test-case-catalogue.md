# Test case catalogue

Generated 2026-11-18 21:37 by `scripts/test_catalogue.py` from the result files of the last full run. Do not edit by hand: regenerate it. Totals and coverage are in [test-report.md](test-report.md).

| Suite | Cases | Passed | Failed | Skipped |
|---|---:|---:|---:|---:|
| Backend (pytest) | 681 | 679 | 0 | 2 |
| Frontend (Vitest) | 329 | 314 | 0 | 15 |
| Browser (Playwright) | 48 | 48 | 0 | 0 |

Database SQL suites (run by `npm test` in `supabase/tools`, which reports ok/fail per file):

- `01_constraints_and_triggers.test.sql`
- `02_messaging_and_deliveries.test.sql`
- `03_credits_ledger.test.sql`
- `04_rls_isolation.test.sql`
- `05_attachments_and_group_members_rls.test.sql`

## Backend (pytest), by requirement area

681 cases: 679 passed, 0 failed, 2 skipped.

### AI (114)

| Status | File | Test case |
|---|---|---|
| PASS | `flows/test_ai` | test_ai_is_off_by_default_and_consent_is_audited |
| PASS | `flows/test_ai` | test_translate_stores_metadata_but_never_the_text |
| PASS | `flows/test_ai` | test_suggest_replies_reads_chat_text_without_side_effects_and_masks_it |
| PASS | `flows/test_ai` | test_decision_is_recorded_for_the_owner_only |
| PASS | `flows/test_ai` | test_a_non_member_cannot_use_someone_elses_conversation |
| PASS | `flows/test_ai` | test_a_conversation_with_ai_switched_off_is_not_sent_to_the_model |
| PASS | `flows/test_ai` | test_cleared_history_is_not_summarised |
| PASS | `flows/test_ai` | test_admin_kill_switch_and_hourly_limit_come_from_system_settings |
| PASS | `flows/test_ai` | test_provider_outage_leaves_chat_and_the_rest_of_the_app_working |
| PASS | `unit/test_ai_api` | test_every_endpoint_requires_a_signed_in_user |
| PASS | `unit/test_ai_api` | test_translate_returns_the_enveloped_draft |
| PASS | `unit/test_ai_api` | test_the_full_draft_then_decision_round_trip |
| PASS | `unit/test_ai_api` | test_an_unknown_assistance_id_is_not_found |
| PASS | `unit/test_ai_api` | test_provider_failure_is_a_502_envelope_without_provider_details |
| PASS | `unit/test_ai_api` | test_not_opted_in_is_a_403_and_the_model_is_never_called |
| PASS | `unit/test_ai_api` | test_status_and_settings_toggle |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[translate-payload0] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[translate-payload1] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[translate-payload2] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[translate-payload3] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[rewrite-payload4] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[rewrite-payload5] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[optimise-sms-payload6] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[optimise-sms-payload7] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[suggest-replies-payload8] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[suggest-replies-payload9] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[summarise-payload10] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[compose-payload11] |
| PASS | `unit/test_ai_api` | test_invalid_input_is_rejected_before_any_model_call[compose-payload12] |
| PASS | `unit/test_ai_api` | test_the_ai_module_has_no_way_to_send_a_message |
| PASS | `unit/test_ai_providers` | test_bedrock_sends_a_converse_request_and_returns_text_and_usage |
| PASS | `unit/test_ai_providers` | test_bedrock_http_errors_are_classified[429-throttled] |
| PASS | `unit/test_ai_providers` | test_bedrock_http_errors_are_classified[408-timeout] |
| PASS | `unit/test_ai_providers` | test_bedrock_http_errors_are_classified[504-timeout] |
| PASS | `unit/test_ai_providers` | test_bedrock_http_errors_are_classified[500-unavailable] |
| PASS | `unit/test_ai_providers` | test_bedrock_http_errors_are_classified[503-unavailable] |
| PASS | `unit/test_ai_providers` | test_bedrock_http_errors_are_classified[400-unavailable] |
| PASS | `unit/test_ai_providers` | test_bedrock_http_errors_are_classified[403-configuration] |
| PASS | `unit/test_ai_providers` | test_bedrock_http_errors_are_classified[401-configuration] |
| PASS | `unit/test_ai_providers` | test_bedrock_network_errors_are_classified |
| PASS | `unit/test_ai_providers` | test_bedrock_guardrail_stop_is_a_blocked_failure |
| PASS | `unit/test_ai_providers` | test_bedrock_malformed_responses_are_unavailable[body0] |
| PASS | `unit/test_ai_providers` | test_bedrock_malformed_responses_are_unavailable[body1] |
| PASS | `unit/test_ai_providers` | test_bedrock_malformed_responses_are_unavailable[body2] |
| PASS | `unit/test_ai_providers` | test_bedrock_never_logs_prompts_completions_or_the_key |
| PASS | `unit/test_ai_providers` | test_bedrock_needs_every_setting |
| PASS | `unit/test_ai_providers` | test_default_mode_is_the_mock_and_calls_nothing_external |
| PASS | `unit/test_ai_providers` | test_bedrock_mode_without_configuration_fails_at_startup_not_to_the_mock |
| PASS | `unit/test_ai_providers` | test_bedrock_mode_builds_the_bedrock_provider |
| PASS | `unit/test_ai_providers` | test_factory_refuses_to_fall_back_when_settings_were_bypassed |
| PASS | `unit/test_ai_providers` | test_blank_bedrock_values_count_as_unset |
| PASS | `unit/test_ai_providers` | test_mock_replays_the_script_then_falls_back_to_deterministic_defaults |
| PASS | `unit/test_ai_service` | test_translate_returns_a_draft_and_logs_metadata_only |
| PASS | `unit/test_ai_service` | test_translate_auto_detect_tells_the_model_to_detect |
| PASS | `unit/test_ai_service` | test_translate_rejects_unsupported_languages[xx] |
| PASS | `unit/test_ai_service` | test_translate_rejects_unsupported_languages[] |
| PASS | `unit/test_ai_service` | test_translate_rejects_unsupported_languages[EN] |
| PASS | `unit/test_ai_service` | test_translate_rejects_same_source_and_target |
| PASS | `unit/test_ai_service` | test_suggest_replies_returns_distinct_drafts_up_to_the_requested_count |
| PASS | `unit/test_ai_service` | test_suggest_replies_needs_messages_to_work_with |
| PASS | `unit/test_ai_service` | test_suggest_replies_for_a_conversation_you_are_not_in_is_not_found |
| PASS | `unit/test_ai_service` | test_a_conversation_with_ai_switched_off_is_never_sent_to_the_provider |
| PASS | `unit/test_ai_service` | test_rewrite_instructions[make_professional] |
| PASS | `unit/test_ai_service` | test_rewrite_instructions[make_friendly] |
| PASS | `unit/test_ai_service` | test_rewrite_instructions[shorten] |
| PASS | `unit/test_ai_service` | test_rewrite_instructions[improve_clarity] |
| PASS | `unit/test_ai_service` | test_rewrite_instructions[make_formal] |
| PASS | `unit/test_ai_service` | test_rewrite_instructions[fix_grammar] |
| PASS | `unit/test_ai_service` | test_adjust_tone_uses_the_tone_feature_and_requires_a_tone |
| PASS | `unit/test_ai_service` | test_summarise_uses_the_chosen_length_and_counts_messages |
| PASS | `unit/test_ai_service` | test_compose_drafts_a_message_with_its_sms_size |
| PASS | `unit/test_ai_service` | test_compose_over_the_requested_length_is_rejected_not_truncated |
| PASS | `unit/test_ai_service` | test_optimise_sms_shows_original_and_optimised_segment_counts |
| PASS | `unit/test_ai_service` | test_optimise_sms_normalises_typographic_characters_to_stay_in_gsm7 |
| PASS | `unit/test_ai_service` | test_optimise_sms_detects_unicode_encoding_and_its_smaller_segments |
| PASS | `unit/test_ai_service` | test_optimise_sms_says_so_when_meaning_cannot_be_kept |
| PASS | `unit/test_ai_service` | test_optimise_sms_discards_a_rewrite_that_saves_no_segment |
| PASS | `unit/test_ai_service` | test_optimise_sms_reports_when_the_target_is_not_reached |
| PASS | `unit/test_ai_service` | test_optimise_sms_does_not_call_the_model_when_the_message_already_fits |
| PASS | `unit/test_ai_service` | test_a_transient_failure_is_retried_once |
| PASS | `unit/test_ai_service` | test_provider_failures_become_a_generic_502_and_are_logged[timeout-timeout-2] |
| PASS | `unit/test_ai_service` | test_provider_failures_become_a_generic_502_and_are_logged[unavailable-unavailable-2] |
| PASS | `unit/test_ai_service` | test_provider_failures_become_a_generic_502_and_are_logged[throttled-throttled-1] |
| PASS | `unit/test_ai_service` | test_a_blocked_request_returns_no_draft_instead_of_an_error |
| PASS | `unit/test_ai_service` | test_empty_or_invalid_model_output_gives_no_draft[] |
| PASS | `unit/test_ai_service` | test_empty_or_invalid_model_output_gives_no_draft[   ] |
| PASS | `unit/test_ai_service` | test_empty_or_invalid_model_output_gives_no_draft[not json] |
| PASS | `unit/test_ai_service` | test_empty_or_invalid_model_output_gives_no_draft[[]] |
| PASS | `unit/test_ai_service` | test_empty_or_invalid_model_output_gives_no_draft[{}] |
| PASS | `unit/test_ai_service` | test_empty_or_invalid_model_output_gives_no_draft[{"text": ""}] |
| PASS | `unit/test_ai_service` | test_empty_or_invalid_model_output_gives_no_draft[{"text": 12}] |
| PASS | `unit/test_ai_service` | test_empty_or_invalid_model_output_gives_no_draft[{"text": null}] |
| PASS | `unit/test_ai_service` | test_invalid_suggestions_give_no_drafts[{"suggestions": []}] |
| PASS | `unit/test_ai_service` | test_invalid_suggestions_give_no_drafts[{"suggestions": ["", "   "]}] |
| PASS | `unit/test_ai_service` | test_invalid_suggestions_give_no_drafts[{"suggestions": "Sure"}] |
| PASS | `unit/test_ai_service` | test_invalid_suggestions_give_no_drafts[{"suggestions": [1, 2]}] |
| PASS | `unit/test_ai_service` | test_invalid_suggestions_give_no_drafts[{"text": "Sure"}] |
| PASS | `unit/test_ai_service` | test_model_output_in_a_code_fence_is_accepted_and_markup_is_stripped |
| PASS | `unit/test_ai_service` | test_optimise_sms_without_a_meaning_flag_is_invalid |
| PASS | `unit/test_ai_service` | test_a_failed_log_write_does_not_lose_the_draft |
| PASS | `unit/test_ai_service` | test_ai_is_off_until_the_user_turns_it_on |
| PASS | `unit/test_ai_service` | test_the_admin_kill_switch_stops_every_request |
| PASS | `unit/test_ai_service` | test_the_hourly_limit_comes_from_platform_settings |
| PASS | `unit/test_ai_service` | test_exceeding_the_limit_is_rate_limited_before_the_model_is_called |
| PASS | `unit/test_ai_service` | test_status_reports_consent_availability_and_simulation |
| PASS | `unit/test_ai_service` | test_turning_ai_on_and_off_is_recorded_as_consent |
| PASS | `unit/test_ai_service` | test_a_draft_is_pending_until_the_user_decides |
| PASS | `unit/test_ai_service` | test_nobody_can_record_a_decision_on_someone_elses_draft |
| PASS | `unit/test_ai_service` | test_no_ai_response_model_can_carry_a_send_instruction |
| PASS | `unit/test_ai_service` | test_context_is_minimised_masked_and_never_includes_identities |
| PASS | `unit/test_ai_service` | test_context_respects_the_total_character_budget |
| PASS | `unit/test_ai_service` | test_instructions_hidden_in_messages_stay_data |
| PASS | `unit/test_ai_service` | test_conversation_text_and_drafts_are_never_logged_or_stored |
| PASS | `unit/test_ai_service` | test_provider_receives_no_credentials_or_identifiers |

### Administration (47)

| Status | File | Test case |
|---|---|---|
| PASS | `flows/test_admin` | test_ordinary_users_are_refused_and_the_attempt_is_audited |
| PASS | `flows/test_admin` | test_a_user_promoted_in_the_database_gains_access_and_a_demoted_one_loses_it |
| PASS | `flows/test_admin` | test_a_suspended_administrator_loses_access |
| PASS | `flows/test_admin` | test_dashboard_counts_come_from_real_rows_and_keep_simulation_apart |
| PASS | `flows/test_admin` | test_dashboard_counts_ai_requests_without_exposing_content |
| PASS | `flows/test_admin` | test_user_search_details_and_masking |
| PASS | `flows/test_admin` | test_restricting_an_account_ends_its_sessions_and_is_audited |
| PASS | `flows/test_admin` | test_restriction_rules_protect_administrators_and_enforce_state |
| PASS | `flows/test_admin` | test_sms_lists_show_attempts_and_provider_ids_without_bodies_or_full_numbers |
| PASS | `flows/test_admin` | test_failed_messages_show_the_failure_reason_and_retry_history |
| PASS | `flows/test_admin` | test_provider_overview_reports_mode_health_and_never_secrets |
| PASS | `flows/test_admin` | test_pausing_outbound_sms_is_reflected_in_provider_health |
| PASS | `flows/test_admin` | test_audit_log_is_readable_filterable_and_free_of_sensitive_data |
| PASS | `flows/test_admin` | test_audit_log_cannot_be_read_or_changed_by_other_users |
| PASS | `unit/test_admin_access` | test_anonymous_requests_are_rejected[GET-/api/v1/admin/dashboard] |
| PASS | `unit/test_admin_access` | test_anonymous_requests_are_rejected[GET-/api/v1/admin/users] |
| PASS | `unit/test_admin_access` | test_anonymous_requests_are_rejected[GET-/api/v1/admin/users/00000000-0000-0000-0000-000000000002] |
| PASS | `unit/test_admin_access` | test_anonymous_requests_are_rejected[POST-/api/v1/admin/users/00000000-0000-0000-0000-000000000002/restrict] |
| PASS | `unit/test_admin_access` | test_anonymous_requests_are_rejected[POST-/api/v1/admin/users/00000000-0000-0000-0000-000000000002/reinstate] |
| PASS | `unit/test_admin_access` | test_anonymous_requests_are_rejected[GET-/api/v1/admin/sms/messages] |
| PASS | `unit/test_admin_access` | test_anonymous_requests_are_rejected[GET-/api/v1/admin/sms/messages/00000000-0000-0000-0000-000000000002] |
| PASS | `unit/test_admin_access` | test_anonymous_requests_are_rejected[GET-/api/v1/admin/providers/overview] |
| PASS | `unit/test_admin_access` | test_anonymous_requests_are_rejected[GET-/api/v1/admin/ai/metrics] |
| PASS | `unit/test_admin_access` | test_anonymous_requests_are_rejected[GET-/api/v1/admin/audit-logs] |
| PASS | `unit/test_admin_access` | test_ordinary_users_are_refused[GET-/api/v1/admin/dashboard] |
| PASS | `unit/test_admin_access` | test_ordinary_users_are_refused[GET-/api/v1/admin/users] |
| PASS | `unit/test_admin_access` | test_ordinary_users_are_refused[GET-/api/v1/admin/users/00000000-0000-0000-0000-000000000002] |
| PASS | `unit/test_admin_access` | test_ordinary_users_are_refused[POST-/api/v1/admin/users/00000000-0000-0000-0000-000000000002/restrict] |
| PASS | `unit/test_admin_access` | test_ordinary_users_are_refused[POST-/api/v1/admin/users/00000000-0000-0000-0000-000000000002/reinstate] |
| PASS | `unit/test_admin_access` | test_ordinary_users_are_refused[GET-/api/v1/admin/sms/messages] |
| PASS | `unit/test_admin_access` | test_ordinary_users_are_refused[GET-/api/v1/admin/sms/messages/00000000-0000-0000-0000-000000000002] |
| PASS | `unit/test_admin_access` | test_ordinary_users_are_refused[GET-/api/v1/admin/providers/overview] |
| PASS | `unit/test_admin_access` | test_ordinary_users_are_refused[GET-/api/v1/admin/ai/metrics] |
| PASS | `unit/test_admin_access` | test_ordinary_users_are_refused[GET-/api/v1/admin/audit-logs] |
| PASS | `unit/test_admin_access` | test_a_role_claimed_by_the_browser_is_ignored[GET-/api/v1/admin/dashboard] |
| PASS | `unit/test_admin_access` | test_a_role_claimed_by_the_browser_is_ignored[GET-/api/v1/admin/users] |
| PASS | `unit/test_admin_access` | test_a_role_claimed_by_the_browser_is_ignored[GET-/api/v1/admin/users/00000000-0000-0000-0000-000000000002] |
| PASS | `unit/test_admin_access` | test_a_role_claimed_by_the_browser_is_ignored[POST-/api/v1/admin/users/00000000-0000-0000-0000-000000000002/restrict] |
| PASS | `unit/test_admin_access` | test_a_role_claimed_by_the_browser_is_ignored[POST-/api/v1/admin/users/00000000-0000-0000-0000-000000000002/reinstate] |
| PASS | `unit/test_admin_access` | test_a_role_claimed_by_the_browser_is_ignored[GET-/api/v1/admin/sms/messages] |
| PASS | `unit/test_admin_access` | test_a_role_claimed_by_the_browser_is_ignored[GET-/api/v1/admin/sms/messages/00000000-0000-0000-0000-000000000002] |
| PASS | `unit/test_admin_access` | test_a_role_claimed_by_the_browser_is_ignored[GET-/api/v1/admin/providers/overview] |
| PASS | `unit/test_admin_access` | test_a_role_claimed_by_the_browser_is_ignored[GET-/api/v1/admin/ai/metrics] |
| PASS | `unit/test_admin_access` | test_a_role_claimed_by_the_browser_is_ignored[GET-/api/v1/admin/audit-logs] |
| PASS | `unit/test_admin_access` | test_a_database_administrator_passes_the_role_check |
| PASS | `unit/test_admin_access` | test_unverified_administrators_are_refused |
| PASS | `unit/test_admin_access` | test_suspended_administrators_are_refused |

### Authentication (46)

| Status | File | Test case |
|---|---|---|
| PASS | `flows/test_registration_and_verification` | test_successful_registration_creates_pending_profile_and_consents |
| PASS | `flows/test_registration_and_verification` | test_registration_rejects_invalid_input_with_field_errors |
| PASS | `flows/test_registration_and_verification` | test_registration_rejects_unknown_fields |
| PASS | `flows/test_registration_and_verification` | test_duplicate_registration_is_indistinguishable |
| PASS | `flows/test_registration_and_verification` | test_unverified_account_cannot_sign_in |
| PASS | `flows/test_registration_and_verification` | test_email_verification_activates_and_signs_in |
| PASS | `flows/test_registration_and_verification` | test_verification_link_is_single_use |
| PASS | `flows/test_registration_and_verification` | test_expired_verification_link_is_rejected |
| PASS | `flows/test_registration_and_verification` | test_resend_invalidates_the_previous_link_and_is_neutral |
| PASS | `flows/test_registration_and_verification` | test_resend_is_rate_limited |
| PASS | `flows/test_sessions_and_passwords` | test_successful_login_issues_memory_token_and_httponly_refresh_cookie |
| PASS | `flows/test_sessions_and_passwords` | test_login_email_is_case_insensitive |
| PASS | `flows/test_sessions_and_passwords` | test_wrong_password_and_unknown_email_get_identical_answers |
| PASS | `flows/test_sessions_and_passwords` | test_five_failures_lock_the_account_without_revealing_it_exists |
| PASS | `flows/test_sessions_and_passwords` | test_successful_login_resets_the_failure_counter |
| PASS | `flows/test_sessions_and_passwords` | test_refresh_requires_the_csrf_header_and_rotates |
| PASS | `flows/test_sessions_and_passwords` | test_refresh_without_cookie_is_401 |
| PASS | `flows/test_sessions_and_passwords` | test_logout_revokes_the_token_immediately |
| PASS | `flows/test_sessions_and_passwords` | test_global_logout_ends_every_device |
| PASS | `flows/test_sessions_and_passwords` | test_list_and_revoke_sessions |
| PASS | `flows/test_sessions_and_passwords` | test_revoke_other_sessions_keeps_the_current_one |
| PASS | `flows/test_sessions_and_passwords` | test_cannot_revoke_another_users_session |
| PASS | `flows/test_sessions_and_passwords` | test_reset_request_is_neutral_for_known_and_unknown_addresses |
| PASS | `flows/test_sessions_and_passwords` | test_password_reset_changes_password_and_revokes_sessions |
| PASS | `flows/test_sessions_and_passwords` | test_password_reset_validates_before_using_the_link |
| PASS | `flows/test_sessions_and_passwords` | test_reset_requests_are_rate_limited |
| PASS | `flows/test_sessions_and_passwords` | test_auth_provider_outage_is_a_readable_503 |
| PASS | `unit/test_security` | test_valid_token_yields_claims |
| PASS | `unit/test_security` | test_role_claims_in_token_are_not_part_of_identity |
| PASS | `unit/test_security` | test_token_without_session_id_is_rejected |
| PASS | `unit/test_security` | test_non_uuid_subject_is_rejected |
| PASS | `unit/test_security` | test_expired_token_is_rejected |
| PASS | `unit/test_security` | test_wrong_signature_is_rejected |
| PASS | `unit/test_security` | test_wrong_audience_is_rejected |
| PASS | `unit/test_security` | test_garbage_token_is_rejected |
| PASS | `unit/test_security` | test_missing_secret_fails_closed |
| PASS | `unit/test_security_asymmetric` | test_es256_token_from_project_keys_is_accepted |
| PASS | `unit/test_security_asymmetric` | test_explicit_jwks_url_overrides_the_default |
| PASS | `unit/test_security_asymmetric` | test_token_signed_by_another_key_is_rejected |
| PASS | `unit/test_security_asymmetric` | test_unknown_key_id_is_rejected |
| PASS | `unit/test_security_asymmetric` | test_token_from_another_project_is_rejected |
| PASS | `unit/test_security_asymmetric` | test_wrong_audience_and_expiry_are_enforced |
| PASS | `unit/test_security_asymmetric` | test_unsigned_token_is_rejected |
| PASS | `unit/test_security_asymmetric` | test_hs256_token_is_rejected_when_no_shared_secret_is_configured |
| PASS | `unit/test_security_asymmetric` | test_unreachable_key_endpoint_is_a_503_not_a_401 |
| PASS | `unit/test_security_asymmetric` | test_legacy_hs256_still_works_alongside_project_keys |

### Contacts (72)

| Status | File | Test case |
|---|---|---|
| PASS | `flows/test_contacts` | test_every_contacts_endpoint_requires_authentication[get-/contacts] |
| PASS | `flows/test_contacts` | test_every_contacts_endpoint_requires_authentication[get-/contacts/search?q=abc] |
| PASS | `flows/test_contacts` | test_every_contacts_endpoint_requires_authentication[get-/contacts/requests] |
| PASS | `flows/test_contacts` | test_every_contacts_endpoint_requires_authentication[post-/contacts/requests] |
| PASS | `flows/test_contacts` | test_every_contacts_endpoint_requires_authentication[get-/contacts/groups] |
| PASS | `flows/test_contacts` | test_every_contacts_endpoint_requires_authentication[get-/contacts/blocks] |
| PASS | `flows/test_contacts` | test_every_contacts_endpoint_requires_authentication[get-/contacts/recent] |
| PASS | `flows/test_contacts` | test_every_contacts_endpoint_requires_authentication[get-/contacts/recent-conversations] |
| PASS | `flows/test_contacts` | test_every_contacts_endpoint_requires_authentication[get-/contacts/13d1e39f-2afc-4135-9ecb-53f56820cb29] |
| PASS | `flows/test_contacts` | test_unverified_account_cannot_use_contacts |
| PASS | `flows/test_contacts` | test_exact_username_finds_a_person_with_a_minimal_card |
| PASS | `flows/test_contacts` | test_username_search_is_exact_not_a_directory |
| PASS | `flows/test_contacts` | test_search_never_returns_yourself |
| PASS | `flows/test_contacts` | test_private_profiles_are_never_discoverable |
| PASS | `flows/test_contacts` | test_email_search_requires_opt_in_and_does_not_reveal_registration |
| PASS | `flows/test_contacts` | test_phone_search_requires_opt_in_and_does_not_reveal_registration |
| PASS | `flows/test_contacts` | test_search_requires_two_characters |
| PASS | `flows/test_contacts` | test_search_is_rate_limited |
| PASS | `flows/test_contacts` | test_search_looks_through_own_contacts_by_name |
| PASS | `flows/test_contacts` | test_blocked_people_are_excluded_from_search_in_both_directions |
| PASS | `flows/test_contacts` | test_request_accept_creates_two_linked_contacts |
| PASS | `flows/test_contacts` | test_duplicate_requests_create_one_row |
| PASS | `flows/test_contacts` | test_request_note_is_sanitised_and_limited |
| PASS | `flows/test_contacts` | test_cannot_request_yourself |
| PASS | `flows/test_contacts` | test_request_to_unknown_user_looks_like_success |
| PASS | `flows/test_contacts` | test_request_to_private_profile_is_silently_dropped |
| PASS | `flows/test_contacts` | test_reverse_request_connects_both_immediately |
| PASS | `flows/test_contacts` | test_requesting_an_existing_contact_is_a_no_op |
| PASS | `flows/test_contacts` | test_only_the_recipient_can_accept_or_reject |
| PASS | `flows/test_contacts` | test_only_the_sender_can_cancel |
| PASS | `flows/test_contacts` | test_reject_is_silent_and_resend_waits_seven_days |
| PASS | `flows/test_contacts` | test_reject_and_block_removes_the_sender_from_view |
| PASS | `flows/test_contacts` | test_expired_requests_disappear_and_cannot_be_accepted |
| PASS | `flows/test_contacts` | test_request_daily_limit |
| PASS | `flows/test_contacts` | test_accept_into_a_group |
| PASS | `flows/test_contacts` | test_accept_with_someone_elses_group_fails |
| PASS | `flows/test_contacts` | test_blocked_sender_gets_no_signal_and_nothing_is_created |
| PASS | `flows/test_contacts` | test_blocker_must_unblock_before_requesting |
| PASS | `flows/test_contacts` | test_blocking_hides_the_contact_and_unblocking_restores_it |
| PASS | `flows/test_contacts` | test_blocking_withdraws_pending_requests |
| PASS | `flows/test_contacts` | test_unblocking_does_not_re_add_a_removed_contact |
| PASS | `flows/test_contacts` | test_block_validation |
| PASS | `flows/test_contacts` | test_blocking_twice_is_harmless_and_block_list_is_private |
| PASS | `flows/test_contacts` | test_buddy_list_orders_favourites_first_then_alphabetical |
| PASS | `flows/test_contacts` | test_favourite_flag_is_private_to_the_owner |
| PASS | `flows/test_contacts` | test_nickname_overrides_display_name_and_can_be_cleared |
| PASS | `flows/test_contacts` | test_online_and_offline_filters_follow_presence |
| PASS | `flows/test_contacts` | test_invisible_contacts_appear_offline |
| PASS | `flows/test_contacts` | test_presence_can_be_hidden_and_is_then_unknown_not_offline |
| PASS | `flows/test_contacts` | test_last_seen_is_shown_only_when_the_contact_allows_it |
| PASS | `flows/test_contacts` | test_status_message_is_shown_to_contacts_but_hidden_for_private_profiles |
| PASS | `flows/test_contacts` | test_status_message_length_limit |
| PASS | `flows/test_contacts` | test_contact_profile_includes_details |
| PASS | `flows/test_contacts` | test_list_is_paginated |
| PASS | `flows/test_contacts` | test_remove_contact_ends_the_relationship_for_both |
| PASS | `flows/test_contacts` | test_users_cannot_touch_each_others_contact_records |
| PASS | `flows/test_contacts` | test_rls_blocks_forged_contacts_and_cross_user_reads |
| PASS | `flows/test_contacts` | test_group_lifecycle |
| PASS | `flows/test_contacts` | test_group_names_are_unique_per_owner_and_sanitised |
| PASS | `flows/test_contacts` | test_group_validation |
| PASS | `flows/test_contacts` | test_group_limit_is_twenty |
| PASS | `flows/test_contacts` | test_groups_are_private_to_their_owner |
| PASS | `flows/test_contacts` | test_cannot_put_someone_elses_contact_in_your_group |
| PASS | `flows/test_contacts` | test_group_filter_requires_a_group |
| PASS | `flows/test_contacts` | test_removing_a_contact_drops_its_group_memberships |
| PASS | `flows/test_contacts` | test_recent_contacts_are_ordered_by_latest_activity |
| PASS | `flows/test_contacts` | test_recent_excludes_blocked_contacts_and_clearing_keeps_conversations |
| PASS | `flows/test_contacts` | test_recent_conversations_cover_contacts_strangers_and_sms |
| PASS | `flows/test_contacts` | test_recent_conversations_hide_blocked_people |
| PASS | `flows/test_contacts` | test_privacy_defaults_are_conservative |
| PASS | `flows/test_contacts` | test_privacy_update_validation |
| PASS | `flows/test_contacts` | test_contact_decisions_are_audited_without_personal_data |

### Conversations and messaging (38)

| Status | File | Test case |
|---|---|---|
| PASS | `flows/test_chat` | test_two_signed_in_users_exchange_messages_in_real_time |
| PASS | `flows/test_chat` | test_sender_info_timestamps_and_delivery_state_in_history |
| PASS | `flows/test_chat` | test_retrying_with_the_same_client_id_stores_and_pushes_once |
| PASS | `flows/test_chat` | test_reusing_a_client_id_for_different_content_is_rejected |
| PASS | `flows/test_chat` | test_a_retry_does_not_count_against_the_rate_limit |
| PASS | `flows/test_chat` | test_sending_is_rate_limited |
| PASS | `flows/test_chat` | test_offline_recipient_gets_messages_later_and_sender_learns_of_delivery |
| PASS | `flows/test_chat` | test_reconnecting_client_catches_up_without_gaps_or_duplicates |
| PASS | `flows/test_chat` | test_history_pages_backwards_in_order |
| PASS | `flows/test_chat` | test_outsiders_cannot_read_write_or_touch_a_conversation |
| PASS | `flows/test_chat` | test_every_endpoint_requires_a_signed_in_user |
| PASS | `flows/test_chat` | test_only_contacts_can_start_a_conversation |
| PASS | `flows/test_chat` | test_opening_twice_returns_the_same_single_conversation |
| PASS | `flows/test_chat` | test_messages_are_not_readable_through_the_database_by_outsiders |
| PASS | `flows/test_chat` | test_a_blocked_sender_sees_sent_but_the_recipient_never_receives |
| PASS | `flows/test_chat` | test_former_contacts_cannot_keep_messaging |
| PASS | `flows/test_chat` | test_read_receipts_need_both_people_to_opt_in |
| PASS | `flows/test_chat` | test_read_position_never_moves_backwards_or_past_the_end |
| PASS | `flows/test_chat` | test_own_messages_never_count_as_unread |
| PASS | `flows/test_chat` | test_read_state_is_pushed_to_the_readers_other_devices |
| PASS | `flows/test_chat` | test_archive_hides_until_a_new_message_arrives |
| PASS | `flows/test_chat` | test_muted_conversations_stay_archived |
| PASS | `flows/test_chat` | test_conversation_search_by_name_and_message_text |
| PASS | `flows/test_chat` | test_conversation_list_shows_contact_last_message_and_order |
| PASS | `flows/test_chat` | test_emoji_round_trip_and_length_counts_code_points |
| PASS | `flows/test_chat` | test_blank_messages_are_rejected_and_markup_is_kept_as_text |
| PASS | `flows/test_chat` | test_attachments_are_validated_shared_and_private |
| PASS | `flows/test_chat` | test_attachment_type_is_checked_from_the_content |
| PASS | `flows/test_chat` | test_image_metadata_is_removed |
| PASS | `flows/test_chat` | test_socket_requires_a_valid_token_in_the_first_frame |
| PASS | `flows/test_chat` | test_socket_closes_when_no_auth_frame_arrives |
| PASS | `flows/test_chat` | test_socket_refuses_foreign_origins |
| PASS | `flows/test_chat` | test_accounts_that_are_not_set_up_cannot_connect |
| PASS | `flows/test_chat` | test_signing_out_closes_the_live_socket |
| PASS | `flows/test_chat` | test_token_refresh_keeps_the_socket_open_for_the_same_user_only |
| PASS | `flows/test_chat` | test_malformed_and_oversized_frames |
| PASS | `flows/test_chat` | test_typing_reaches_the_other_person_only_if_they_share_it |
| PASS | `flows/test_chat` | test_too_many_connections_replace_the_oldest |

### Credits (30)

| Status | File | Test case |
|---|---|---|
| PASS | `flows/test_credits` | test_new_users_start_with_demo_credits_and_a_clear_notice |
| PASS | `flows/test_credits` | test_the_quote_shows_the_cost_and_whether_you_can_afford_it |
| PASS | `flows/test_credits` | test_a_delivered_sms_holds_then_spends_exactly_its_cost |
| PASS | `flows/test_credits` | test_live_credits_are_never_touched_by_a_simulated_send |
| PASS | `flows/test_credits` | test_a_repeated_send_with_the_same_key_is_charged_once |
| PASS | `flows/test_credits` | test_a_message_accepted_then_failed_is_refunded_once |
| PASS | `flows/test_credits` | test_a_message_that_was_never_accepted_only_releases_its_hold |
| PASS | `flows/test_credits` | test_retrying_a_failed_message_charges_the_new_message_once |
| PASS | `flows/test_credits` | test_insufficient_credits_block_the_quote_and_the_send |
| PASS | `flows/test_credits` | test_two_sends_cannot_both_spend_the_last_credits |
| PASS | `flows/test_credits` | test_low_balance_is_announced_once_per_crossing |
| PASS | `flows/test_credits` | test_history_is_paginated_newest_first_and_private |
| PASS | `flows/test_credits` | test_credits_endpoints_need_a_signed_in_user |
| PASS | `flows/test_credits` | test_only_administrators_can_adjust_credits |
| PASS | `flows/test_credits` | test_an_adjustment_is_a_ledger_entry_with_actor_reason_audit_and_notice |
| PASS | `flows/test_credits` | test_an_adjustment_is_idempotent |
| PASS | `flows/test_credits` | test_adjustments_are_validated_and_cannot_touch_live_credit_or_overdraw |
| PASS | `flows/test_credits` | test_a_removal_cannot_dip_into_credits_held_for_queued_messages |
| PASS | `flows/test_credits` | test_the_ledger_is_append_only_and_balances_always_match_it |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_an_overdraw_becomes_a_402_with_the_amounts |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_an_overdraw_without_amounts_still_becomes_a_402 |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_other_database_errors_are_not_disguised_as_a_shortfall |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_balance_hint[5000-100-True-True-False] |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_balance_hint[50-100-True-False-True] |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_balance_hint[100-100-True-True-True] |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_balance_hint[5000-None-True-None-False] |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_balance_hint[0-100-False-True-False] |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_the_loop_runs_until_stopped_and_stops_cleanly |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_the_loop_survives_a_failing_pass |
| PASS | `unit/test_credit_ledger_and_dispatcher` | test_an_empty_pass_does_nothing |

### Failure handling (20)

| Status | File | Test case |
|---|---|---|
| PASS | `flows/test_failure_paths` | test_outages_are_503_with_a_readable_message[signup-<lambda>] |
| PASS | `flows/test_failure_paths` | test_outages_are_503_with_a_readable_message[resend-<lambda>] |
| PASS | `flows/test_failure_paths` | test_outages_are_503_with_a_readable_message[recover-<lambda>] |
| PASS | `flows/test_failure_paths` | test_outages_are_503_with_a_readable_message[verify-<lambda>] |
| PASS | `flows/test_failure_paths` | test_refresh_outage_is_503 |
| PASS | `flows/test_failure_paths` | test_logout_still_revokes_when_the_provider_is_down |
| PASS | `flows/test_failure_paths` | test_reset_confirm_outage_while_setting_password |
| PASS | `flows/test_failure_paths` | test_reusing_the_current_password_on_reset_is_rejected |
| PASS | `flows/test_failure_paths` | test_reauthentication_outage_changes_nothing |
| PASS | `flows/test_failure_paths` | test_reauthentication_locks_after_repeated_wrong_passwords |
| PASS | `flows/test_failure_paths` | test_suspended_accounts_cannot_sign_in_or_use_tokens |
| PASS | `flows/test_failure_paths` | test_resend_cooldown_and_expired_codes |
| PASS | `flows/test_failure_paths` | test_confirming_without_requesting_a_code |
| PASS | `flows/test_failure_paths` | test_reverifying_the_same_number_is_a_conflict |
| PASS | `flows/test_failure_paths` | test_removing_when_no_number_is_verified |
| PASS | `flows/test_failure_paths` | test_live_mode_without_sms_provider_fails_loudly_and_stores_no_code |
| PASS | `flows/test_failure_paths` | test_simulated_inbox_is_never_served_in_production |
| PASS | `flows/test_failure_paths` | test_storage_outage_keeps_the_old_photo |
| PASS | `flows/test_failure_paths` | test_database_unavailable_fails_closed |
| PASS | `flows/test_failure_paths` | test_profile_update_is_rate_limited |

### Notifications (49)

| Status | File | Test case |
|---|---|---|
| PASS | `flows/test_notifications` | test_a_new_message_creates_one_unread_notification_without_the_text |
| PASS | `flows/test_notifications` | test_messages_in_one_chat_fold_into_one_notification_until_it_is_read |
| PASS | `flows/test_notifications` | test_mark_one_as_read_then_all_as_read |
| PASS | `flows/test_notifications` | test_read_all_can_be_limited_to_one_type |
| PASS | `flows/test_notifications` | test_dismissed_notifications_leave_the_feed_and_the_count |
| PASS | `flows/test_notifications` | test_the_feed_is_paginated_and_private |
| PASS | `flows/test_notifications` | test_notification_endpoints_need_a_signed_in_user |
| PASS | `flows/test_notifications` | test_contact_requests_and_acceptances_notify_once |
| PASS | `flows/test_notifications` | test_a_muted_conversation_does_not_notify |
| PASS | `flows/test_notifications` | test_a_delivered_sms_notifies_once_even_when_the_callback_repeats |
| PASS | `flows/test_notifications` | test_signing_out_other_devices_creates_a_security_notice |
| PASS | `flows/test_notifications` | test_preferences_start_at_the_defaults |
| PASS | `flows/test_notifications` | test_preferences_store_only_deviations_and_validate |
| PASS | `flows/test_notifications` | test_mandatory_notices_cannot_be_switched_off_in_the_app |
| PASS | `flows/test_notifications` | test_a_type_switched_off_everywhere_creates_nothing |
| PASS | `flows/test_notifications` | test_in_app_off_hides_the_notice_but_keeps_the_other_channels |
| PASS | `flows/test_notifications` | test_previews_show_message_text_only_when_enabled |
| PASS | `flows/test_notifications` | test_a_new_notification_is_pushed_to_open_sessions_with_the_browser_flag |
| PASS | `flows/test_notifications` | test_browser_notifications_follow_the_push_preference |
| PASS | `flows/test_notifications` | test_quiet_hours_silence_browser_and_email_but_not_the_feed |
| PASS | `flows/test_notifications` | test_system_notices_are_emailed_once_through_the_configured_provider |
| PASS | `flows/test_notifications` | test_email_is_off_by_default_for_chat_messages |
| PASS | `flows/test_notifications` | test_a_failed_email_is_retried_later_and_gives_up_after_three_attempts |
| PASS | `flows/test_notifications` | test_a_rejected_address_is_not_retried_and_eventually_disables_email |
| PASS | `flows/test_notifications` | test_only_administrators_can_send_notices |
| PASS | `flows/test_notifications` | test_an_admin_notice_is_idempotent_and_audited |
| PASS | `flows/test_notifications` | test_a_notice_can_go_to_everyone_and_to_nobody_unknown |
| PASS | `unit/test_notification_rules` | test_every_type_has_a_default_for_every_channel |
| PASS | `unit/test_notification_rules` | test_overrides_win_over_defaults_but_mandatory_in_app_never_turns_off |
| PASS | `unit/test_notification_rules` | test_only_message_notifications_depend_on_previews |
| PASS | `unit/test_notification_rules` | test_overrides_for_keeps_only_deviations |
| PASS | `unit/test_notification_rules` | test_quiet_hours_may_wrap_midnight[now0-False] |
| PASS | `unit/test_notification_rules` | test_quiet_hours_may_wrap_midnight[now1-True] |
| PASS | `unit/test_notification_rules` | test_quiet_hours_may_wrap_midnight[now2-True] |
| PASS | `unit/test_notification_rules` | test_quiet_hours_may_wrap_midnight[now3-True] |
| PASS | `unit/test_notification_rules` | test_quiet_hours_may_wrap_midnight[now4-False] |
| PASS | `unit/test_notification_rules` | test_quiet_hours_may_wrap_midnight[now5-False] |
| PASS | `unit/test_notification_rules` | test_quiet_hours_use_the_users_time_zone |
| PASS | `unit/test_notification_rules` | test_no_quiet_hours_when_unset_or_empty[None-None] |
| PASS | `unit/test_notification_rules` | test_no_quiet_hours_when_unset_or_empty[start1-end1] |
| PASS | `unit/test_notification_rules` | test_no_quiet_hours_when_unset_or_empty[start2-None] |
| PASS | `unit/test_notification_rules` | test_the_mock_email_provider_records_and_can_fail_on_demand |
| PASS | `unit/test_notification_rules` | test_default_email_mode_is_the_mock |
| PASS | `unit/test_notification_rules` | test_smtp_mode_without_configuration_fails_at_startup |
| PASS | `unit/test_notification_rules` | test_smtp_mode_builds_the_smtp_provider_and_never_falls_back |
| PASS | `unit/test_notification_rules` | test_smtp_sends_a_plain_text_message_with_starttls_and_login |
| PASS | `unit/test_notification_rules` | test_smtp_failures_are_classified_without_leaking_details[error0-True] |
| PASS | `unit/test_notification_rules` | test_smtp_failures_are_classified_without_leaking_details[error1-False] |
| PASS | `unit/test_notification_rules` | test_smtp_failures_are_classified_without_leaking_details[error2-False] |

### Platform and infrastructure (70)

| Status | File | Test case |
|---|---|---|
| PASS | `integration/test_api_platform` | test_unknown_route_uses_error_envelope |
| PASS | `integration/test_api_platform` | test_domain_error_is_mapped_to_envelope |
| PASS | `integration/test_api_platform` | test_unhandled_error_does_not_leak_internals |
| PASS | `integration/test_api_platform` | test_validation_error_does_not_echo_submitted_values |
| PASS | `integration/test_api_platform` | test_protected_route_without_token_is_401 |
| PASS | `integration/test_api_platform` | test_protected_route_with_bad_token_is_401 |
| PASS | `integration/test_api_platform` | test_protected_route_with_valid_token |
| PASS | `integration/test_api_platform` | test_admin_route_denies_regular_user |
| PASS | `integration/test_api_platform` | test_admin_role_in_token_metadata_is_ignored |
| PASS | `integration/test_api_platform` | test_admin_route_allows_admin |
| PASS | `integration/test_api_platform` | test_auth_fails_closed_when_secret_is_not_configured |
| PASS | `integration/test_api_platform` | test_revoked_session_is_rejected |
| PASS | `integration/test_api_platform` | test_cors_allows_configured_origin |
| PASS | `integration/test_api_platform` | test_cors_blocks_unknown_origin |
| PASS | `integration/test_api_platform` | test_cors_preflight_allows_idempotency_key |
| PASS | `integration/test_api_platform` | test_api_documentation_is_available |
| PASS | `integration/test_api_platform` | test_api_documentation_is_off_in_production |
| PASS | `integration/test_health` | test_health_responds_without_database |
| PASS | `integration/test_health` | test_health_reports_database_ok |
| PASS | `integration/test_health` | test_health_degrades_but_stays_live_when_database_is_down |
| PASS | `integration/test_health` | test_readiness_is_503_when_database_is_down |
| PASS | `integration/test_health` | test_readiness_is_200_when_nothing_is_down |
| PASS | `integration/test_health` | test_platform_aliases_match_versioned_routes |
| PASS | `integration/test_health` | test_caller_request_id_is_echoed |
| PASS | `integration/test_health` | test_security_headers_are_present |
| SKIP | `integration/test_twilio_test_credentials` | test_test_credentials_accept_a_valid_message |
| SKIP | `integration/test_twilio_test_credentials` | test_test_credentials_reject_an_invalid_number_as_permanent |
| PASS | `unit/test_config` | test_defaults_are_safe |
| PASS | `unit/test_config` | test_cors_origins_accept_comma_separated_string |
| PASS | `unit/test_config` | test_cors_wildcard_is_rejected |
| PASS | `unit/test_config` | test_blank_values_from_env_example_mean_unset |
| PASS | `unit/test_config` | test_database_url_is_upgraded_to_async_driver |
| PASS | `unit/test_config` | test_non_postgres_database_url_is_rejected |
| PASS | `unit/test_config` | test_live_sms_requires_explicit_confirmation |
| PASS | `unit/test_config` | test_docs_are_disabled_in_production |
| PASS | `unit/test_config` | test_secret_key_is_required_outside_development |
| PASS | `unit/test_config` | test_env_example_values_load |
| PASS | `unit/test_config` | test_env_example_contains_no_real_secrets |
| PASS | `unit/test_config` | test_secure_cookies_default_by_environment |
| PASS | `unit/test_config` | test_secret_is_not_leaked_in_repr |
| PASS | `unit/test_database_session` | test_build_database_returns_none_without_url |
| PASS | `unit/test_database_session` | test_session_scope_fails_explicitly_without_database |
| PASS | `unit/test_database_session` | test_session_scope_rolls_back_and_reraises_on_error |
| PASS | `unit/test_database_session` | test_declarative_base_uses_project_naming_convention |
| PASS | `unit/test_integrations` | test_sign_in_maps_provider_errors[400-invalid_credentials-InvalidCredentialsError] |
| PASS | `unit/test_integrations` | test_sign_in_maps_provider_errors[400-email_not_confirmed-EmailNotConfirmedError] |
| PASS | `unit/test_integrations` | test_sign_in_maps_provider_errors[400-user_banned-InvalidCredentialsError] |
| PASS | `unit/test_integrations` | test_sign_in_maps_provider_errors[500-boom-AuthUnavailableError] |
| PASS | `unit/test_integrations` | test_sign_in_maps_provider_errors[503--AuthUnavailableError] |
| PASS | `unit/test_integrations` | test_network_failure_is_unavailable_not_invalid |
| PASS | `unit/test_integrations` | test_sign_in_sends_the_anon_key_and_parses_the_session |
| PASS | `unit/test_integrations` | test_signup_weak_password_and_verify_failures |
| PASS | `unit/test_integrations` | test_admin_calls_need_the_service_role_key |
| PASS | `unit/test_integrations` | test_unconfigured_providers_fail_loudly |
| PASS | `unit/test_integrations` | test_live_otp_delivery_never_falls_back_to_simulation |
| PASS | `unit/test_integrations` | test_simulated_delivery_stores_masked_recipient_only |
| PASS | `unit/test_integrations` | test_provider_selection_follows_configuration |
| PASS | `unit/test_integrations` | test_phone_normalisation[+63 917 123 0001-+639171230001-PH] |
| PASS | `unit/test_integrations` | test_phone_normalisation[+1-415-555-2671-+14155552671-US] |
| PASS | `unit/test_integrations` | test_phone_normalisation_rejects_bad_numbers[09171230001] |
| PASS | `unit/test_integrations` | test_phone_normalisation_rejects_bad_numbers[+63] |
| PASS | `unit/test_integrations` | test_phone_normalisation_rejects_bad_numbers[+00000000] |
| PASS | `unit/test_integrations` | test_phone_normalisation_rejects_bad_numbers[+63 abc] |
| PASS | `unit/test_integrations` | test_log_handler_writes_to_the_current_stdout |
| PASS | `unit/test_logging_and_request_context` | test_request_id_accepts_safe_caller_value |
| PASS | `unit/test_logging_and_request_context` | test_request_id_replaces_unsafe_or_missing_value |
| PASS | `unit/test_logging_and_request_context` | test_json_formatter_includes_request_id_and_extras |
| PASS | `unit/test_logging_and_request_context` | test_json_formatter_logs_error_type_without_traceback |
| PASS | `unit/test_privacy_helpers` | test_mask_email_keeps_first_letter_and_domain |
| PASS | `unit/test_privacy_helpers` | test_mask_email_handles_missing_or_malformed_values |

### Profiles (66)

| Status | File | Test case |
|---|---|---|
| PASS | `flows/test_phone_and_deletion` | test_phone_verification_in_simulation_mode |
| PASS | `flows/test_phone_and_deletion` | test_email_and_mobile_verification_are_separate |
| PASS | `flows/test_phone_and_deletion` | test_wrong_codes_are_counted_and_invalidate_after_five |
| PASS | `flows/test_phone_and_deletion` | test_number_verified_elsewhere_gets_a_neutral_refusal |
| PASS | `flows/test_phone_and_deletion` | test_invalid_numbers_are_rejected |
| PASS | `flows/test_phone_and_deletion` | test_code_sends_are_limited_to_three_per_half_hour |
| PASS | `flows/test_phone_and_deletion` | test_changing_and_removing_a_number_needs_the_password |
| PASS | `flows/test_phone_and_deletion` | test_unverified_accounts_cannot_use_phone_verification |
| PASS | `flows/test_phone_and_deletion` | test_account_deletion_requires_password_and_confirmation |
| PASS | `flows/test_phone_and_deletion` | test_account_deletion_erases_profile_and_blocks_access |
| PASS | `flows/test_phone_and_deletion` | test_deletion_is_atomic_when_auth_provider_fails |
| PASS | `flows/test_phone_and_deletion` | test_logs_never_contain_passwords_codes_or_tokens |
| PASS | `flows/test_profiles` | test_profile_contains_expected_fields_without_credentials |
| PASS | `flows/test_profiles` | test_profile_update_sanitises_and_persists |
| PASS | `flows/test_profiles` | test_profile_update_rejects_invalid_values |
| PASS | `flows/test_profiles` | test_privileged_fields_cannot_be_set_by_the_user |
| PASS | `flows/test_profiles` | test_onboarding_sets_username_once |
| PASS | `flows/test_profiles` | test_taken_username_is_case_insensitive_and_offers_suggestions |
| PASS | `flows/test_profiles` | test_reserved_and_malformed_usernames_are_rejected |
| PASS | `flows/test_profiles` | test_profile_requires_a_valid_token |
| PASS | `flows/test_profiles` | test_one_user_cannot_change_another |
| PASS | `flows/test_profiles` | test_token_signed_with_another_key_is_rejected |
| PASS | `flows/test_profiles` | test_rls_denies_cross_user_reads_for_client_roles |
| PASS | `flows/test_profiles` | test_avatar_upload_reencodes_and_strips_metadata |
| PASS | `flows/test_profiles` | test_replacing_and_removing_avatar_cleans_up_storage |
| PASS | `flows/test_profiles` | test_avatar_rejects_non_images_and_oversized_files |
| PASS | `flows/test_profiles` | test_presence_preferences_and_heartbeat |
| PASS | `unit/test_profile_helpers` | test_clean_text[  hello  -hello] |
| PASS | `unit/test_profile_helpers` | test_clean_text[<b>bold</b> text-bold text] |
| PASS | `unit/test_profile_helpers` | test_clean_text[&lt;script&gt;alert(1)&lt;/script&gt;hi-alert(1)hi] |
| PASS | `unit/test_profile_helpers` | test_clean_text[tab\x00null\x07bell-tabnullbell] |
| PASS | `unit/test_profile_helpers` | test_clean_text[Salamat po \U0001f64f-Salamat po \U0001f64f] |
| PASS | `unit/test_profile_helpers` | test_mask_phone_matches_the_logging_policy |
| PASS | `unit/test_profile_helpers` | test_ip_prefix_is_coarse |
| PASS | `unit/test_profile_helpers` | test_weak_passwords_are_rejected[Short1A] |
| PASS | `unit/test_profile_helpers` | test_weak_passwords_are_rejected[alllowercase1] |
| PASS | `unit/test_profile_helpers` | test_weak_passwords_are_rejected[ALLUPPERCASE1] |
| PASS | `unit/test_profile_helpers` | test_weak_passwords_are_rejected[NoDigitsHere] |
| PASS | `unit/test_profile_helpers` | test_weak_passwords_are_rejected[\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4\xc4a1] |
| PASS | `unit/test_profile_helpers` | test_strong_password_is_accepted |
| PASS | `unit/test_profile_helpers` | test_valid_usernames[abc] |
| PASS | `unit/test_profile_helpers` | test_valid_usernames[Mari_2026] |
| PASS | `unit/test_profile_helpers` | test_valid_usernames[aaaaaaaaaaaaaaaaaaaa] |
| PASS | `unit/test_profile_helpers` | test_invalid_usernames[ab] |
| PASS | `unit/test_profile_helpers` | test_invalid_usernames[aaaaaaaaaaaaaaaaaaaaa] |
| PASS | `unit/test_profile_helpers` | test_invalid_usernames[has space] |
| PASS | `unit/test_profile_helpers` | test_invalid_usernames[dash-name] |
| PASS | `unit/test_profile_helpers` | test_invalid_usernames[ADMIN] |
| PASS | `unit/test_profile_helpers` | test_invalid_usernames[Chikka] |
| PASS | `unit/test_profile_helpers` | test_profile_update_only_reports_fields_that_were_sent |
| PASS | `unit/test_profile_helpers` | test_empty_bio_clears_it |
| PASS | `unit/test_profile_helpers` | test_supported_images_become_webp[JPEG] |
| PASS | `unit/test_profile_helpers` | test_supported_images_become_webp[PNG] |
| PASS | `unit/test_profile_helpers` | test_supported_images_become_webp[WEBP] |
| PASS | `unit/test_profile_helpers` | test_transparency_is_kept |
| PASS | `unit/test_profile_helpers` | test_exif_including_location_is_removed |
| PASS | `unit/test_profile_helpers` | test_unsupported_or_corrupt_files_are_rejected[] |
| PASS | `unit/test_profile_helpers` | test_unsupported_or_corrupt_files_are_rejected[GIF89a not really] |
| PASS | `unit/test_profile_helpers` | test_unsupported_or_corrupt_files_are_rejected[\x89PNG\r\n\x1a\n\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00] |
| PASS | `unit/test_profile_helpers` | test_unsupported_or_corrupt_files_are_rejected[data3] |
| PASS | `unit/test_profile_helpers` | test_unsupported_or_corrupt_files_are_rejected[data4] |
| PASS | `unit/test_profile_helpers` | test_oversized_upload_is_rejected_before_decoding |
| PASS | `unit/test_profile_helpers` | test_decompression_bomb_is_rejected |
| PASS | `unit/test_profile_helpers` | test_presence_transitions |
| PASS | `unit/test_profile_helpers` | test_invisible_looks_offline_to_others |
| PASS | `unit/test_profile_helpers` | test_user_agent_is_summarised |

### SMS (129)

| Status | File | Test case |
|---|---|---|
| PASS | `flows/test_sms` | test_send_in_simulation_walks_the_status_ladder_and_never_skips_to_delivered |
| PASS | `flows/test_sms` | test_simulated_reply_appears_in_the_same_conversation |
| PASS | `flows/test_sms` | test_unauthenticated_requests_are_rejected |
| PASS | `flows/test_sms` | test_sender_without_a_verified_number_cannot_send |
| PASS | `flows/test_sms` | test_other_users_cannot_read_or_retry_my_messages |
| PASS | `flows/test_sms` | test_sending_requires_explicit_confirmation_and_a_key |
| PASS | `flows/test_sms` | test_duplicate_idempotency_key_sends_once |
| PASS | `flows/test_sms` | test_consent_is_required_per_recipient_and_can_be_withdrawn |
| PASS | `flows/test_sms` | test_opt_out_keyword_blocks_everyone_until_the_recipient_opts_back_in |
| PASS | `flows/test_sms` | test_keyword_inside_a_sentence_is_a_normal_reply |
| PASS | `flows/test_sms` | test_unknown_country_and_unsupported_routes_are_refused |
| PASS | `flows/test_sms` | test_invalid_and_special_numbers_are_refused |
| PASS | `flows/test_sms` | test_local_format_needs_a_country_and_normalises |
| PASS | `flows/test_sms` | test_quote_reports_segments_cost_consent_and_warnings |
| PASS | `flows/test_sms` | test_overlong_message_is_refused_and_not_stored |
| PASS | `flows/test_sms` | test_capabilities_never_promise_universal_two_way_sms |
| PASS | `flows/test_sms` | test_status_endpoint_labels_the_mode |
| PASS | `flows/test_sms` | test_failed_delivery_shows_a_readable_reason_notifies_and_can_be_retried |
| PASS | `flows/test_sms` | test_undelivered_is_not_delivered |
| PASS | `flows/test_sms` | test_transient_failure_is_retried_with_the_same_key_and_then_accepted |
| PASS | `flows/test_sms` | test_transient_failures_stop_at_the_attempt_limit |
| PASS | `flows/test_sms` | test_permanent_provider_errors_are_not_retried |
| PASS | `flows/test_sms` | test_ambiguous_outcome_is_not_resent_and_resolves_to_failed_with_a_warning |
| PASS | `flows/test_sms` | test_late_callback_corrects_an_ambiguous_failure_forward |
| PASS | `flows/test_sms` | test_no_receipt_route_stays_sent_and_is_labelled_unconfirmed |
| PASS | `flows/test_sms` | test_out_of_order_callbacks_never_regress_status |
| PASS | `flows/test_sms` | test_duplicate_status_callbacks_are_recorded_once |
| PASS | `flows/test_sms` | test_delayed_delivery_waits_for_the_callback |
| PASS | `flows/test_sms` | test_lost_callbacks_are_recovered_by_polling |
| PASS | `flows/test_sms` | test_provider_response_is_stored_without_the_message_body |
| PASS | `flows/test_sms` | test_invalid_signatures_are_rejected_without_side_effects |
| PASS | `flows/test_sms` | test_webhook_for_a_provider_that_is_not_running_does_not_exist |
| PASS | `flows/test_sms` | test_malformed_signed_payload_is_a_400_and_stores_nothing |
| PASS | `flows/test_sms` | test_replayed_inbound_webhook_creates_one_message |
| PASS | `flows/test_sms` | test_concurrent_duplicate_webhooks_create_one_message |
| PASS | `flows/test_sms` | test_reply_from_an_unknown_route_is_kept_for_admins_and_shown_to_nobody |
| PASS | `flows/test_sms` | test_reply_from_a_blocked_number_is_stored_hidden_and_not_notified |
| PASS | `flows/test_sms` | test_replies_reach_only_the_user_who_owns_the_route |
| PASS | `flows/test_sms` | test_reply_marks_read_and_unarchives |
| PASS | `flows/test_sms` | test_reply_after_the_route_expired_is_unrouted |
| PASS | `flows/test_sms` | test_a_sender_number_is_never_shared_by_two_users_for_one_recipient |
| PASS | `flows/test_sms` | test_outbound_pause_switch_blocks_sending |
| PASS | `flows/test_sms` | test_mode_mismatch_fails_loudly_instead_of_switching_modes |
| PASS | `flows/test_sms` | test_queued_message_is_held_while_a_different_provider_is_active |
| PASS | `flows/test_sms` | test_audit_trail_has_no_numbers_or_message_text |
| PASS | `flows/test_sms` | test_simulation_spends_demo_credits_and_never_touches_live_credits |
| PASS | `flows/test_sms` | test_admin_endpoints_require_the_admin_role |
| PASS | `flows/test_sms` | test_admin_provider_view_never_exposes_secrets |
| PASS | `flows/test_sms` | test_admin_updates_retry_settings_and_cannot_activate_a_provider_that_is_not_running |
| PASS | `flows/test_sms` | test_admin_capability_changes_are_versioned_and_guarded |
| PASS | `flows/test_sms` | test_admin_monitoring_summarises_health_without_content |
| PASS | `flows/test_sms` | test_admin_can_simulate_a_reply_through_the_signed_path_and_replay_it |
| PASS | `flows/test_sms` | test_simulated_reply_can_omit_the_sender_number |
| PASS | `flows/test_sms` | test_reply_simulation_is_refused_in_production |
| PASS | `flows/test_sms_live` | test_live_mode_is_labelled_and_refuses_to_send_until_an_operator_confirms |
| PASS | `flows/test_sms_live` | test_unverified_routes_are_unavailable_in_live_mode |
| PASS | `flows/test_sms_live` | test_live_send_goes_to_twilio_and_only_a_signed_callback_marks_delivery |
| PASS | `flows/test_sms_live` | test_live_inbound_reply_is_verified_routed_and_not_labelled_simulated |
| PASS | `flows/test_sms_live` | test_the_simulation_webhook_does_not_exist_in_live_mode |
| PASS | `flows/test_sms_live` | test_twilio_rejection_of_the_number_is_permanent_and_not_retried |
| PASS | `flows/test_sms_live` | test_twilio_outage_is_retried_then_succeeds |
| PASS | `flows/test_sms_live` | test_twilio_credential_error_pauses_dispatch_and_keeps_the_message_queued |
| PASS | `flows/test_sms_live` | test_twilio_opt_out_error_records_a_persistent_opt_out |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[-gsm7-0-0] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[Hello-gsm7-5-1] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[body2-gsm7-160-1] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[body3-gsm7-161-2] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[body4-gsm7-306-2] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[body5-gsm7-307-3] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{-gsm7-160-1] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{-gsm7-162-2] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[Kumusta ka, Nanay?-gsm7-18-1] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9\xe9-gsm7-70-1] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[\u65e5\u672c\u8a9e-ucs2-3-1] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\xf1\U0001f600-ucs2-72-2] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57-ucs2-70-1] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57\u5b57-ucs2-71-2] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[body14-ucs2-134-2] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[body15-ucs2-135-3] |
| PASS | `unit/test_sms_helpers` | test_segment_vectors[Hi \U0001f600-ucs2-5-1] |
| PASS | `unit/test_sms_helpers` | test_unknown_country_is_unavailable_in_both_modes |
| PASS | `unit/test_sms_helpers` | test_unverified_route_is_unavailable_for_live_but_usable_in_simulation |
| PASS | `unit/test_sms_helpers` | test_philippines_style_registration_blocks_live_only |
| PASS | `unit/test_sms_helpers` | test_live_needs_registration_and_pricing |
| PASS | `unit/test_sms_helpers` | test_number_type_and_unsupported_outbound_are_blocked |
| PASS | `unit/test_sms_helpers` | test_replies_are_never_promised_when_unsupported |
| PASS | `unit/test_sms_helpers` | test_cost_estimate_sources |
| PASS | `unit/test_sms_helpers` | test_parse_destination[+63 917 123 4567-None-expected0] |
| PASS | `unit/test_sms_helpers` | test_parse_destination[0917 123 4567-PH-expected1] |
| PASS | `unit/test_sms_helpers` | test_parse_destination[+12025550142-None-expected2] |
| PASS | `unit/test_sms_helpers` | test_parse_destination_rejects[09171234567-None] |
| PASS | `unit/test_sms_helpers` | test_parse_destination_rejects[+63123-None] |
| PASS | `unit/test_sms_helpers` | test_parse_destination_rejects[not a number-PH] |
| PASS | `unit/test_sms_helpers` | test_parse_destination_rejects[+18005550199-None] |
| PASS | `unit/test_sms_helpers` | test_keywords_match_whole_message_only[STOP-expected0] |
| PASS | `unit/test_sms_helpers` | test_keywords_match_whole_message_only[  stopall \n-expected1] |
| PASS | `unit/test_sms_helpers` | test_keywords_match_whole_message_only[Unsubscribe-expected2] |
| PASS | `unit/test_sms_helpers` | test_keywords_match_whole_message_only[start-expected3] |
| PASS | `unit/test_sms_helpers` | test_keywords_match_whole_message_only[please stop by later-None] |
| PASS | `unit/test_sms_helpers` | test_keywords_match_whole_message_only[stopping-None] |
| PASS | `unit/test_sms_helpers` | test_keywords_match_whole_message_only[yes-None] |
| PASS | `unit/test_sms_helpers` | test_keywords_match_whole_message_only[-None] |
| PASS | `unit/test_sms_helpers` | test_retry_delay_is_exponential_capped_and_seeded |
| PASS | `unit/test_sms_helpers` | test_only_transient_failures_below_the_limit_retry |
| PASS | `unit/test_sms_providers` | test_mock_sends_nothing_real_and_ids_are_marked_simulated |
| PASS | `unit/test_sms_providers` | test_mock_callbacks_follow_the_timeline_and_are_signed |
| PASS | `unit/test_sms_providers` | test_mock_rejects_tampering_missing_and_stale_signatures |
| PASS | `unit/test_sms_providers` | test_mock_error_scenarios[+12025550105-permanent-SIM-INVALID] |
| PASS | `unit/test_sms_providers` | test_mock_error_scenarios[+12025550104-transient-SIM-TRANSIENT] |
| PASS | `unit/test_sms_providers` | test_mock_error_scenarios[+12025550110-ambiguous-SIM-TIMEOUT] |
| PASS | `unit/test_sms_providers` | test_mock_transient_then_success_counts_attempts_per_idempotency_key |
| PASS | `unit/test_sms_providers` | test_mock_no_receipt_stops_at_sent_and_status_lookup_agrees |
| PASS | `unit/test_sms_providers` | test_mock_out_of_order_and_duplicate_scenarios |
| PASS | `unit/test_sms_providers` | test_twilio_send_success_maps_queued_to_accepted_not_delivered |
| PASS | `unit/test_sms_providers` | test_twilio_http_errors_are_classified[400-payload0-permanent] |
| PASS | `unit/test_sms_providers` | test_twilio_http_errors_are_classified[400-payload1-permanent] |
| PASS | `unit/test_sms_providers` | test_twilio_http_errors_are_classified[400-payload2-permanent] |
| PASS | `unit/test_sms_providers` | test_twilio_http_errors_are_classified[401-payload3-configuration] |
| PASS | `unit/test_sms_providers` | test_twilio_http_errors_are_classified[429-payload4-transient] |
| PASS | `unit/test_sms_providers` | test_twilio_http_errors_are_classified[503-payload5-transient] |
| PASS | `unit/test_sms_providers` | test_twilio_retry_after_is_honoured |
| PASS | `unit/test_sms_providers` | test_twilio_network_failures_split_into_transient_and_ambiguous |
| PASS | `unit/test_sms_providers` | test_twilio_signature_matches_the_documented_algorithm |
| PASS | `unit/test_sms_providers` | test_twilio_webhook_validation_uses_raw_form_and_rejects_bad_signatures |
| PASS | `unit/test_sms_providers` | test_twilio_parses_inbound_and_status_callbacks |
| PASS | `unit/test_sms_providers` | test_twilio_country_info_reports_price_without_claiming_support |
| PASS | `unit/test_sms_providers` | test_factory_builds_mock_by_default |
| PASS | `unit/test_sms_providers` | test_live_mode_refuses_to_start_without_credentials_or_confirmation |
| PASS | `unit/test_sms_providers` | test_factory_builds_twilio_only_when_fully_configured |

## Frontend (Vitest), by feature

329 cases: 314 passed, 0 failed, 15 skipped.

### admin (13)

| Status | File | Test case |
|---|---|---|
| PASS | `features/admin/admin.test.tsx` | Administration dashboard shows real totals, keeps simulated and live SMS apart and shows no secrets |
| PASS | `features/admin/admin.test.tsx` | Administration dashboard is not available to non-administrators and requests nothing from the admin API |
| PASS | `features/admin/admin.test.tsx` | Administration dashboard shows a readable error with a retry when the backend refuses |
| PASS | `features/admin/admin.test.tsx` | Administration dashboard only offers the admin entry in the navigation to administrators |
| PASS | `features/admin/admin.test.tsx` | Administration users searches with the typed term and shows only masked details |
| PASS | `features/admin/admin.test.tsx` | Administration users restricts an account only after confirmation, with the chosen reason |
| PASS | `features/admin/admin.test.tsx` | Administration users offers no restriction for administrators and lifts a suspension |
| PASS | `features/admin/admin.test.tsx` | Administration users explains a refused restriction |
| PASS | `features/admin/admin.test.tsx` | Administration users explains when no account matches |
| PASS | `features/admin/admin.test.tsx` | Administration SMS, AI and audit views lists SMS with failure reasons and shows attempts and provider IDs |
| PASS | `features/admin/admin.test.tsx` | Administration SMS, AI and audit views switches to inbound messages |
| PASS | `features/admin/admin.test.tsx` | Administration SMS, AI and audit views shows AI usage and says cost is unavailable instead of inventing it |
| PASS | `features/admin/admin.test.tsx` | Administration SMS, AI and audit views shows the audit log with actor, action, resource and outcome |

### ai (20)

| Status | File | Test case |
|---|---|---|
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel explains what is sent and stays off until the user opts in |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel says so when administrators switched the assistant off |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel keeps working without the assistant when its status cannot be loaded |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel labels the demo provider honestly |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel translates between chosen languages and only fills the box after Use |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel lets the user edit a draft before using it |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel rejects a draft without using it |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel asks for text first when translate, rewrite or shorten have nothing to work on |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel rewrites with a chosen instruction and tone |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel offers replies and summaries only inside a Chikka conversation |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel shows several reply suggestions and sends the conversation id only |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel summarises with the chosen length and offers no Use button |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel composes a draft from a short instruction |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel SMS optimisation shows original and optimised versions with their counts, and no price claim |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel SMS optimisation explains when the meaning cannot be kept |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel failures shows the server's message when the model returned nothing usable |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel failures reports a provider error and lets the user try again |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant panel failures explains the hourly limit |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant in the composer is closed until opened, and drafting never sends |
| PASS | `features/ai/ai-assistant.test.tsx` | AI assistant in the composer leaves typing and sending fully usable when the assistant is down |

### auth (40)

| Status | File | Test case |
|---|---|---|
| PASS | `features/auth/auth-pages.test.tsx` | registration validates in the browser before sending anything |
| PASS | `features/auth/auth-pages.test.tsx` | registration registers and shows the check-your-inbox screen |
| PASS | `features/auth/auth-pages.test.tsx` | registration shows server field errors next to the field |
| PASS | `features/auth/auth-pages.test.tsx` | sign in signs in, keeps the token in memory only and returns to the requested page |
| PASS | `features/auth/auth-pages.test.tsx` | sign in ignores redirect targets outside the app |
| PASS | `features/auth/auth-pages.test.tsx` | sign in shows one generic message for wrong credentials and clears the password |
| PASS | `features/auth/auth-pages.test.tsx` | sign in explains unverified accounts and links to a new confirmation email |
| PASS | `features/auth/auth-pages.test.tsx` | sign in shows the lockout wait time |
| PASS | `features/auth/auth-pages.test.tsx` | email verification confirms the link once, signs in and continues to profile setup |
| PASS | `features/auth/auth-pages.test.tsx` | email verification does not spend a single-use link twice under StrictMode |
| PASS | `features/auth/auth-pages.test.tsx` | email verification resends with a neutral confirmation |
| PASS | `features/auth/auth-pages.test.tsx` | password reset answers the same way for any address |
| PASS | `features/auth/auth-pages.test.tsx` | password reset checks the passwords match before using the link |
| PASS | `features/auth/auth-pages.test.tsx` | password reset sets the new password and says every device was signed out |
| PASS | `features/auth/auth-pages.test.tsx` | password reset offers a new link when the reset link has expired |
| PASS | `features/auth/auth-pages.test.tsx` | password reset explains a missing token |
| PASS | `features/auth/auth-pages.test.tsx` | sign out clears the session even when the server cannot be reached |
| PASS | `features/auth/schemas.test.ts` | password policy (mirrors the server) rejects Short1A |
| PASS | `features/auth/schemas.test.ts` | password policy (mirrors the server) rejects alllowercase1 |
| PASS | `features/auth/schemas.test.ts` | password policy (mirrors the server) rejects ALLUPPERCASE1 |
| PASS | `features/auth/schemas.test.ts` | password policy (mirrors the server) rejects NoDigitsHere |
| PASS | `features/auth/schemas.test.ts` | password policy (mirrors the server) rejects ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄa1B |
| PASS | `features/auth/schemas.test.ts` | password policy (mirrors the server) accepts a strong password |
| PASS | `features/auth/schemas.test.ts` | auth schemas normalises email and requires terms |
| PASS | `features/auth/schemas.test.ts` | auth schemas login only requires something in each field |
| PASS | `features/auth/schemas.test.ts` | auth schemas deletion needs the exact phrase |
| PASS | `features/auth/schemas.test.ts` | profile schemas accepts username abc |
| PASS | `features/auth/schemas.test.ts` | profile schemas accepts username Mari_2026 |
| PASS | `features/auth/schemas.test.ts` | profile schemas accepts username aaaaaaaaaaaaaaaaaaaa |
| PASS | `features/auth/schemas.test.ts` | profile schemas rejects username ab |
| PASS | `features/auth/schemas.test.ts` | profile schemas rejects username aaaaaaaaaaaaaaaaaaaaa |
| PASS | `features/auth/schemas.test.ts` | profile schemas rejects username has space |
| PASS | `features/auth/schemas.test.ts` | profile schemas rejects username dash-name |
| PASS | `features/auth/schemas.test.ts` | profile schemas rejects username ADMIN |
| PASS | `features/auth/schemas.test.ts` | profile schemas rejects username Chikka |
| PASS | `features/auth/schemas.test.ts` | profile schemas strips markup and maps empty optional fields to null |
| PASS | `features/auth/schemas.test.ts` | profile schemas rejects unknown countries, languages and zones |
| PASS | `features/auth/schemas.test.ts` | profile schemas phone numbers need E.164 after removing spaces |
| PASS | `features/auth/schemas.test.ts` | form helpers maps server field problems onto known fields only |
| PASS | `features/auth/schemas.test.ts` | form helpers reads Retry-After details and formats waits |

### chat (27)

| Status | File | Test case |
|---|---|---|
| PASS | `features/chat/chat-pages.test.tsx` | conversation view shows the header, history with sender, time, date separators and status |
| PASS | `features/chat/chat-pages.test.tsx` | conversation view shows an empty state and focuses the composer |
| PASS | `features/chat/chat-pages.test.tsx` | conversation view explains why sending is off |
| PASS | `features/chat/chat-pages.test.tsx` | conversation view shows a readable error for a conversation you cannot open |
| PASS | `features/chat/chat-pages.test.tsx` | sending sends with Enter, shows Sending then Sent, and keeps Shift+Enter for new lines |
| PASS | `features/chat/chat-pages.test.tsx` | sending marks a failed send and retries with the same client id |
| PASS | `features/chat/chat-pages.test.tsx` | sending does not send blank messages and counts characters near the limit |
| PASS | `features/chat/chat-pages.test.tsx` | sending inserts emoji from a keyboard-accessible picker |
| PASS | `features/chat/chat-pages.test.tsx` | sending uploads an attachment and sends it with the message |
| PASS | `features/chat/chat-pages.test.tsx` | sending rejects disallowed files before uploading |
| PASS | `features/chat/chat-pages.test.tsx` | real time receives a pushed message once, announces it and acknowledges delivery |
| PASS | `features/chat/chat-pages.test.tsx` | real time updates delivery state from the server and ignores older versions |
| PASS | `features/chat/chat-pages.test.tsx` | real time shows the other person typing, then clears it |
| PASS | `features/chat/chat-pages.test.tsx` | real time sends a throttled typing signal while composing |
| PASS | `features/chat/chat-pages.test.tsx` | real time shows reconnecting, then catches up on missed messages without duplicates |
| PASS | `features/chat/chat-pages.test.tsx` | real time repairs a gap in sequence numbers from the server |
| PASS | `features/chat/chat-pages.test.tsx` | conversation list lists conversations with previews and unread badges, and searches |
| PASS | `features/chat/chat-pages.test.tsx` | conversation list shows archived conversations and an empty inbox |
| PASS | `features/chat/chat-pages.test.tsx` | conversation list archives the open conversation |
| PASS | `features/chat/chat-pages.test.tsx` | conversation list opens a conversation with a contact from /messages/new |
| PASS | `features/chat/chat-pages.test.tsx` | conversation list explains when the person is not a contact |
| PASS | `features/chat/thread.test.ts` | thread merging orders by seq, not by arrival, and ignores duplicates |
| PASS | `features/chat/thread.test.ts` | thread merging replaces the local copy when the stored message arrives, in either order |
| PASS | `features/chat/thread.test.ts` | thread merging keeps unsent messages after stored ones |
| PASS | `features/chat/thread.test.ts` | thread merging applies a status only when it is newer |
| PASS | `features/chat/thread.test.ts` | thread merging keeps messages pushed or sent while a resync request was in flight |
| PASS | `features/chat/thread.test.ts` | thread merging detects gaps and keeps older pages on refresh |

### components (19)

| Status | File | Test case |
|---|---|---|
| PASS | `components/shared/shared-components.test.tsx` | estimateSms counts a short GSM message as one segment |
| PASS | `components/shared/shared-components.test.tsx` | estimateSms splits long GSM messages at 153 characters |
| PASS | `components/shared/shared-components.test.tsx` | estimateSms switches to unicode with a 70 character limit |
| PASS | `components/shared/shared-components.test.tsx` | estimateSms masks phone numbers |
| PASS | `components/shared/shared-components.test.tsx` | ChannelBadge labels simulated SMS |
| PASS | `components/shared/shared-components.test.tsx` | ChannelBadge labels live SMS and not simulated |
| PASS | `components/shared/shared-components.test.tsx` | ChannelBadge shows no SMS mode for internet messages |
| PASS | `components/shared/shared-components.test.tsx` | MessageStatusLabel never presents accepted as delivered |
| PASS | `components/shared/shared-components.test.tsx` | MessageStatusLabel flags unconfirmed delivery for sent SMS |
| PASS | `components/shared/shared-components.test.tsx` | MessageBubble renders markup in the body as plain text |
| PASS | `components/shared/shared-components.test.tsx` | SmsCostEstimate uses demo credits only in simulation |
| PASS | `components/shared/shared-components.test.tsx` | SmsCostEstimate warns when live cost exceeds balance |
| PASS | `components/shared/shared-components.test.tsx` | MessageComposer sends only on explicit action |
| PASS | `components/shared/shared-components.test.tsx` | MessageComposer disables sending and explains why when blocked |
| PASS | `components/shared/shared-components.test.tsx` | MessageComposer shows the AI-assisted badge before sending |
| PASS | `components/shared/shared-components.test.tsx` | MessageComposer shows cost estimate only for SMS |
| PASS | `components/shared/shared-components.test.tsx` | ConfirmDialog confirms and closes |
| PASS | `components/shared/shared-components.test.tsx` | ModeSwitcher switches mode, updates the document and persists the choice |
| PASS | `components/shared/shared-components.test.tsx` | ModeSwitcher restores the stored mode |

### contacts (28)

| Status | File | Test case |
|---|---|---|
| PASS | `features/contacts/contacts-pages.test.tsx` | buddy list shows presence with a text label, the status message and the SMS badge |
| PASS | `features/contacts/contacts-pages.test.tsx` | buddy list explains an empty list and offers the next step |
| PASS | `features/contacts/contacts-pages.test.tsx` | buddy list shows a readable error with a retry |
| PASS | `features/contacts/contacts-pages.test.tsx` | buddy list filters by online, offline and favourites through the API |
| PASS | `features/contacts/contacts-pages.test.tsx` | buddy list filters by group |
| PASS | `features/contacts/contacts-pages.test.tsx` | buddy list toggles a favourite |
| PASS | `features/contacts/contacts-pages.test.tsx` | finding people sends nothing for one character, then searches after the pause |
| PASS | `features/contacts/contacts-pages.test.tsx` | finding people sends a request from a search result and then shows it as sent |
| PASS | `features/contacts/contacts-pages.test.tsx` | finding people explains an empty search without hinting at who is registered |
| PASS | `features/contacts/contacts-pages.test.tsx` | finding people shows the rate limit message from the server |
| PASS | `features/contacts/contacts-pages.test.tsx` | finding people adds a contact from the dialog with a validated note |
| PASS | `features/contacts/contacts-pages.test.tsx` | contact requests accepts a request |
| PASS | `features/contacts/contacts-pages.test.tsx` | contact requests rejects, and can reject and block |
| PASS | `features/contacts/contacts-pages.test.tsx` | contact requests cancels a sent request and shows a friendly message if it already resolved |
| PASS | `features/contacts/contacts-pages.test.tsx` | contact requests shows an empty state |
| PASS | `features/contacts/contacts-pages.test.tsx` | contact profile drawer shows the profile |
| PASS | `features/contacts/contacts-pages.test.tsx` | contact profile drawer assigns the contact to a group |
| PASS | `features/contacts/contacts-pages.test.tsx` | contact profile drawer asks before blocking, explains the effect, then blocks |
| PASS | `features/contacts/contacts-pages.test.tsx` | contact profile drawer does not block when the confirmation is cancelled |
| PASS | `features/contacts/contacts-pages.test.tsx` | contact profile drawer removes a contact after confirmation |
| PASS | `features/contacts/contacts-pages.test.tsx` | contact profile drawer saves a nickname |
| PASS | `features/contacts/contacts-pages.test.tsx` | groups creates a group and shows a server error for a duplicate name |
| PASS | `features/contacts/contacts-pages.test.tsx` | groups validates the name before sending |
| PASS | `features/contacts/contacts-pages.test.tsx` | groups deletes a group only after confirming that contacts are kept |
| PASS | `features/contacts/contacts-pages.test.tsx` | blocked, recent and privacy lists blocked people and unblocks after confirmation |
| PASS | `features/contacts/contacts-pages.test.tsx` | blocked, recent and privacy shows an empty blocked list |
| PASS | `features/contacts/contacts-pages.test.tsx` | blocked, recent and privacy shows recent contacts and conversations, and clears the recent list |
| PASS | `features/contacts/contacts-pages.test.tsx` | blocked, recent and privacy changes discovery settings from the settings page |

### credits (16)

| Status | File | Test case |
|---|---|---|
| PASS | `features/credits/credits.test.tsx` | credit overview shows the balance, the not-money notice and the history |
| PASS | `features/credits/credits.test.tsx` | credit overview shows holds as held, not as spent |
| PASS | `features/credits/credits.test.tsx` | credit overview explains reserved credits |
| PASS | `features/credits/credits.test.tsx` | credit overview pages through the history |
| PASS | `features/credits/credits.test.tsx` | credit overview handles an empty history |
| PASS | `features/credits/credits.test.tsx` | credit overview offers a retry when the history cannot be loaded |
| PASS | `features/credits/credits.test.tsx` | credit overview warns when credits are low |
| PASS | `features/credits/credits.test.tsx` | credit badge and low-credit warning shows the active ledger's balance as a link to the history |
| PASS | `features/credits/credits.test.tsx` | credit badge and low-credit warning marks a low balance |
| PASS | `features/credits/credits.test.tsx` | credit badge and low-credit warning stays out of the way when the balance cannot be loaded |
| PASS | `features/credits/credits.test.tsx` | credit badge and low-credit warning says plainly when there are no credits left |
| PASS | `features/credits/credits.test.tsx` | credit badge and low-credit warning is silent when the balance is fine |
| PASS | `features/credits/credits.test.tsx` | SMS cost preview shows the cost, the balance and what is left afterwards |
| PASS | `features/credits/credits.test.tsx` | SMS cost preview warns when the balance is low but still enough |
| PASS | `features/credits/credits.test.tsx` | SMS cost preview shows the insufficient-credits blocker and no after-balance |
| PASS | `features/credits/credits.test.tsx` | SMS cost preview does not talk about demo credits for a live route |

### hooks (13)

| Status | File | Test case |
|---|---|---|
| PASS | `hooks/hooks.test.tsx` | useDebouncedValue keeps the old value until the input has been still for the delay |
| PASS | `hooks/hooks.test.tsx` | useDebouncedValue restarts the wait on every change, so only the last value is published |
| PASS | `hooks/hooks.test.tsx` | useMediaQuery reports false where matchMedia does not exist |
| PASS | `hooks/hooks.test.tsx` | useMediaQuery follows the query as the window changes size and stops listening on unmount |
| PASS | `hooks/hooks.test.tsx` | useArrowKeyNavigation moves focus with the arrow keys and stops at both ends |
| PASS | `hooks/hooks.test.tsx` | useArrowKeyNavigation skips disabled items and ignores keys with a modifier |
| PASS | `hooks/hooks.test.tsx` | useSlashToSearch focuses the search box when / is pressed outside a text field |
| PASS | `hooks/hooks.test.tsx` | useSlashToSearch leaves / alone while the person is typing in another field |
| PASS | `hooks/hooks.test.tsx` | usePresence sends a heartbeat every 30 seconds and reports idle only after 5 quiet minutes |
| PASS | `hooks/hooks.test.tsx` | usePresence does nothing while signed out |
| PASS | `hooks/hooks.test.tsx` | useModePreference applies the new mode at once and saves it to the profile |
| PASS | `hooks/hooks.test.tsx` | useModePreference does not call the server when the mode is unchanged |
| PASS | `hooks/hooks.test.tsx` | useModePreference goes back to the previous mode when saving fails |

### lib (52)

| Status | File | Test case |
|---|---|---|
| PASS | `lib/env.test.ts` | parseEnv applies safe local defaults |
| PASS | `lib/env.test.ts` | parseEnv treats empty strings from a copied .env.example as unset |
| PASS | `lib/env.test.ts` | parseEnv rejects an invalid API URL with a readable message |
| PASS | `lib/env.test.ts` | parseEnv rejects an unknown environment name |
| PASS | `lib/error-handling.test.ts` | toUserFacingError reports network failures as offline and retryable |
| PASS | `lib/error-handling.test.ts` | toUserFacingError hides server fault details |
| PASS | `lib/error-handling.test.ts` | toUserFacingError treats 401 and 403 as forbidden and not retryable |
| PASS | `lib/error-handling.test.ts` | toUserFacingError shows client error messages and carries the request id |
| PASS | `lib/error-handling.test.ts` | toUserFacingError gives unknown errors a generic message |
| PASS | `lib/error-handling.test.ts` | shouldRetry retries network and 5xx errors up to the limit |
| PASS | `lib/error-handling.test.ts` | shouldRetry never retries client errors or unknown errors |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "Hello" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{{" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "Kumusta ka, Nanay?" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "éééééééééééééééééééééééééééééééééééééééééééééééééééééééééééééééééééééé" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "日本語" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "ññññññññññññññññññññññññññññññññññññññññññññññññññññññññññññññññññññññ😀" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字字" |
| PASS | `lib/sms.test.ts` | estimateSms matches the server's segment rules "Hi 😀" |
| PASS | `lib/api/client.test.ts` | ApiClient returns parsed JSON and builds the URL with query parameters |
| PASS | `lib/api/client.test.ts` | ApiClient sends the bearer token and idempotency key when provided |
| PASS | `lib/api/client.test.ts` | ApiClient omits the Authorization header when there is no token |
| PASS | `lib/api/client.test.ts` | ApiClient parses the error envelope and exposes the request id |
| PASS | `lib/api/client.test.ts` | ApiClient falls back to a generic error when the failing body is not an envelope |
| PASS | `lib/api/client.test.ts` | ApiClient maps a network failure to a network ApiError |
| PASS | `lib/api/client.test.ts` | ApiClient sends cookies for the refresh flow and handles 204 |
| PASS | `lib/api/client.test.ts` | ApiClient sends FormData as-is so the browser sets the multipart boundary |
| PASS | `lib/api/client.test.ts` | ApiClient flags a successful response with an unreadable body |
| PASS | `lib/auth/session.test.ts` | SessionStore starts unknown, then signs in from the refresh cookie |
| PASS | `lib/auth/session.test.ts` | SessionStore signs out when the refresh fails |
| PASS | `lib/auth/session.test.ts` | SessionStore shares one refresh between concurrent callers |
| PASS | `lib/auth/session.test.ts` | SessionStore notifies subscribers only on real changes |
| PASS | `lib/auth/session.test.ts` | ApiClient with a session retries once with a fresh token after an expired-token 401 |
| PASS | `lib/auth/session.test.ts` | ApiClient with a session does not loop when the retried request also fails |
| PASS | `lib/auth/session.test.ts` | ApiClient with a session never refreshes for wrong credentials or when signed out |
| PASS | `lib/realtime/client.test.ts` | realtime client builds the socket URL from the API base URL |
| PASS | `lib/realtime/client.test.ts` | realtime client backs off exponentially with full jitter, capped at 30 seconds |
| PASS | `lib/realtime/client.test.ts` | realtime client authenticates with the first frame, not the URL |
| PASS | `lib/realtime/client.test.ts` | realtime client reports status, heartbeats, and ignores duplicate events |
| PASS | `lib/realtime/client.test.ts` | realtime client reconnects after a drop, and resyncs via ready |
| PASS | `lib/realtime/client.test.ts` | realtime client refreshes the token once on 4401, then reconnects with the new token |
| PASS | `lib/realtime/client.test.ts` | realtime client stops when the session cannot be refreshed or the account is unavailable |
| PASS | `lib/realtime/client.test.ts` | realtime client only sends uplink frames while connected |

### notifications (29)

| Status | File | Test case |
|---|---|---|
| PASS | `features/notifications/notifications.test.tsx` | notification centre lists notifications newest first with unread state, grouping and no invented text |
| PASS | `features/notifications/notifications.test.tsx` | notification centre marks one notification as read |
| PASS | `features/notifications/notifications.test.tsx` | notification centre marks everything as read and disables the button when nothing is unread |
| PASS | `features/notifications/notifications.test.tsx` | notification centre filters to unread and dismisses |
| PASS | `features/notifications/notifications.test.tsx` | notification centre has an empty state, a loading state and an error with a retry |
| PASS | `features/notifications/notifications.test.tsx` | notification bell announces the unread count |
| PASS | `features/notifications/notifications.test.tsx` | notification bell shows no badge when everything is read |
| PASS | `features/notifications/notifications.test.tsx` | notification links {"type":"new_message","reference_type":"conversation","reference_id":"c-9"} leads to /messages/c-9 |
| PASS | `features/notifications/notifications.test.tsx` | notification links {"type":"sms_failed","reference_type":"message","reference_id":"m-1"} leads to /sms |
| PASS | `features/notifications/notifications.test.tsx` | notification links {"type":"contact_request","reference_type":"contact_request","reference_id":"r"} leads to /contacts |
| PASS | `features/notifications/notifications.test.tsx` | notification links {"type":"low_balance","reference_type":null,"reference_id":null} leads to /credits |
| PASS | `features/notifications/notifications.test.tsx` | notification links {"type":"security","reference_type":null,"reference_id":null} leads to /settings/profile |
| PASS | `features/notifications/notifications.test.tsx` | notification links {"type":"system","reference_type":"credit_transaction","reference_id":"t"} leads to /credits |
| PASS | `features/notifications/notifications.test.tsx` | notification links {"type":"system","reference_type":null,"reference_id":null} leads to null |
| PASS | `features/notifications/notifications.test.tsx` | notification settings shows every type and channel, with mandatory in-app notices locked |
| PASS | `features/notifications/notifications.test.tsx` | notification settings saves the changed settings |
| PASS | `features/notifications/notifications.test.tsx` | notification settings saves quiet hours and the low-credit threshold in credits |
| PASS | `features/notifications/notifications.test.tsx` | notification settings rejects an invalid threshold and identical quiet hours before calling the server |
| PASS | `features/notifications/notifications.test.tsx` | notification settings shows a server error and a switched-off email notice |
| PASS | `features/notifications/notifications.test.tsx` | browser notifications only asks for permission when the user presses the button |
| PASS | `features/notifications/notifications.test.tsx` | browser notifications explains a blocked or unsupported browser instead of nagging |
| PASS | `features/notifications/notifications.test.tsx` | browser notifications is hidden in the centre once permission was decided |
| PASS | `features/notifications/notifications.test.tsx` | browser notifications updates the badge and shows a system notification only in the background |
| PASS | `features/notifications/notifications.test.tsx` | browser notifications shows nothing when the tab is visible |
| PASS | `features/notifications/notifications.test.tsx` | browser notifications shows nothing when the server did not flag it for the browser (preference or quiet hours) |
| PASS | `features/notifications/notifications.test.tsx` | browser notifications shows nothing when permission is not granted |
| PASS | `features/notifications/notifications.test.tsx` | browser notifications shows nothing when permission is denied |
| PASS | `features/notifications/notifications.test.tsx` | browser notifications ignores malformed and unrelated events |
| PASS | `features/notifications/notifications.test.tsx` | browser notifications does not crash when the browser refuses to build a notification |

### profile (16)

| Status | File | Test case |
|---|---|---|
| PASS | `features/profile/profile-pages.test.tsx` | profile setup validates the username before sending |
| PASS | `features/profile/profile-pages.test.tsx` | profile setup offers suggestions when the username is taken and finishes with one |
| PASS | `features/profile/profile-pages.test.tsx` | profile settings sends only changed fields and confirms the save |
| PASS | `features/profile/profile-pages.test.tsx` | profile settings validates the bio length and display name |
| PASS | `features/profile/profile-pages.test.tsx` | profile settings shows the username and email as read-only |
| PASS | `features/profile/profile-pages.test.tsx` | profile settings refreshes an expired access token once and retries |
| PASS | `features/profile/profile-pages.test.tsx` | profile settings returns to sign in when the session cannot be renewed |
| PASS | `features/profile/profile-pages.test.tsx` | mobile number shows the code in a SIMULATED inbox and verifies the number |
| PASS | `features/profile/profile-pages.test.tsx` | mobile number shows the server's message for a wrong code |
| PASS | `features/profile/profile-pages.test.tsx` | mobile number rejects numbers without a country code in the browser |
| PASS | `features/profile/profile-pages.test.tsx` | photo and presence rejects unsupported and oversized files before uploading |
| PASS | `features/profile/profile-pages.test.tsx` | photo and presence uploads a photo as multipart form data |
| PASS | `features/profile/profile-pages.test.tsx` | photo and presence changes the presence preference |
| PASS | `features/profile/profile-pages.test.tsx` | sessions and account deletion lists sessions and signs out another device |
| PASS | `features/profile/profile-pages.test.tsx` | sessions and account deletion requires DELETE and the password, and reports a wrong password |
| PASS | `features/profile/profile-pages.test.tsx` | sessions and account deletion deletes the account, signs out and leaves |

### routes (24)

| Status | File | Test case |
|---|---|---|
| PASS | `routes/routes.test.tsx` | route guards sends visitors to sign in and remembers where they were going |
| PASS | `routes/routes.test.tsx` | route guards shows the app shell with server status to an onboarded user |
| PASS | `routes/routes.test.tsx` | route guards sends users without a finished profile to setup |
| PASS | `routes/routes.test.tsx` | route guards sends signed-in users away from the sign-in page |
| PASS | `routes/routes.test.tsx` | route guards shows a readable error when the profile cannot load |
| PASS | `routes/routes.test.tsx` | route guards keeps the style guide public |
| PASS | `routes/routes.test.tsx` | route guards renders a not-found page for unknown routes |
| PASS | `routes/modes/modes.test.tsx` | Classic mode shows a compact buddy list with nicknames, presence groups and unread indicators |
| PASS | `routes/modes/modes.test.tsx` | Classic mode opens a chat window from a buddy and labels it with the nickname |
| PASS | `routes/modes/modes.test.tsx` | Classic mode moves between buddies with the arrow keys |
| PASS | `routes/modes/modes.test.tsx` | Classic mode focuses the buddy search with the / key and filters the list |
| PASS | `routes/modes/modes.test.tsx` | Classic mode explains an empty buddy list |
| PASS | `routes/modes/modes.test.tsx` | Classic mode shows only the chat window on a phone once a chat is open |
| PASS | `routes/modes/modes.test.tsx` | Modern mode shows three columns on a desktop: chats, conversation, details and AI |
| PASS | `routes/modes/modes.test.tsx` | Modern mode keeps the AI assistant in the composer on small screens |
| PASS | `routes/modes/modes.test.tsx` | Modern mode puts an AI suggestion in the message box without sending it |
| PASS | `routes/modes/modes.test.tsx` | Modern mode opens a conversation from the People tab |
| PASS | `routes/modes/modes.test.tsx` | Modern mode explains an empty inbox |
| PASS | `routes/modes/modes.test.tsx` | switching modes saves the choice to the profile and keeps the same data on screen |
| PASS | `routes/modes/modes.test.tsx` | switching modes goes back to the previous mode when saving fails |
| PASS | `routes/modes/modes.test.tsx` | switching modes follows the saved profile preference over this device's stored one |
| PASS | `routes/modes/modes.test.tsx` | switching modes can be changed from settings too |
| PASS | `routes/modes/modes.test.tsx` | conversation controls asks before archiving and does nothing when cancelled |
| PASS | `routes/modes/modes.test.tsx` | conversation controls shows the archive tooltip on keyboard focus |

### sms (17)

| Status | File | Test case |
|---|---|---|
| PASS | `features/sms/sms-pages.test.tsx` | SMS conversation labels the mode and shows each message's channel, SIMULATED label and honest status |
| PASS | `features/sms/sms-pages.test.tsx` | SMS conversation shows replies as SMS in, marks them read, and updates status from real-time events |
| PASS | `features/sms/sms-pages.test.tsx` | SMS conversation explains a failure, warns when the outcome is unknown, and retries only after confirmation |
| PASS | `features/sms/sms-pages.test.tsx` | composing an SMS shows segments, estimated cost and warnings, and only sends after the confirmation dialog |
| PASS | `features/sms/sms-pages.test.tsx` | composing an SMS blocks sending until the sender confirms permission, then records it |
| PASS | `features/sms/sms-pages.test.tsx` | composing an SMS shows why a destination is unavailable and never offers to send |
| PASS | `features/sms/sms-pages.test.tsx` | composing an SMS surfaces a server refusal inside the confirmation dialog and keeps the text |
| PASS | `features/sms/sms-pages.test.tsx` | SMS conversation list and mode banner lists conversations with masked numbers, unread counts and the SIMULATED label |
| PASS | `features/sms/sms-pages.test.tsx` | SMS conversation list and mode banner shows a live banner, a paused notice and the verify-your-number prompt |
| PASS | `features/sms/sms-pages.test.tsx` | SMS conversation list and mode banner offers a next step when there are no conversations, and a retry on error |
| PASS | `features/sms/admin/admin-sms.test.tsx` | SMS administration shows providers without any secret, capabilities, unrouted replies and failures |
| PASS | `features/sms/admin/admin-sms.test.tsx` | SMS administration is not available to non-administrators |
| PASS | `features/sms/admin/admin-sms.test.tsx` | SMS administration pauses all sending and validates retry settings before saving |
| PASS | `features/sms/admin/admin-sms.test.tsx` | SMS administration requires typing the environment before activating live SMS, and shows the server's refusal |
| PASS | `features/sms/admin/admin-sms.test.tsx` | SMS administration sends a simulated reply through the API only in simulation mode |
| PASS | `features/sms/admin/admin-sms.test.tsx` | SMS administration lets the administrator leave the sender number out |
| PASS | `features/sms/admin/admin-sms.test.tsx` | SMS administration hides the reply simulator in live mode |

### test (15)

| Status | File | Test case |
|---|---|---|
| SKIP | `test/live/journeys.test.ts` | journey 1: a new user registers, confirms the email, completes the profile and reaches the dashboard |
| SKIP | `test/live/journeys.test.ts` | journey 2: Chikka to Chikka messaging adds a contact, chats in real time and keeps the same history for both |
| SKIP | `test/live/journeys.test.ts` | journey 3: SMS quotes, sends in simulation, tracks delivery, and shows the reply in the same thread |
| SKIP | `test/live/journeys.test.ts` | journey 4: AI assistance translates into a draft, records the decision, and sends only after the user does |
| SKIP | `test/live/journeys.test.ts` | journey 5: administration reviews SMS delivery, investigates a failed message and finds its audit record |
| SKIP | `test/live/live-api.test.ts` | live API: authentication and user management serves health and the API documentation |
| SKIP | `test/live/live-api.test.ts` | live API: authentication and user management registers, refuses sign-in until the email is confirmed, then verifies |
| SKIP | `test/live/live-api.test.ts` | live API: authentication and user management rejects wrong credentials identically for known and unknown emails |
| SKIP | `test/live/live-api.test.ts` | live API: authentication and user management completes onboarding and edits the profile |
| SKIP | `test/live/live-api.test.ts` | live API: authentication and user management uploads a photo, keeps presence alive and lists sessions |
| SKIP | `test/live/live-api.test.ts` | live API: authentication and user management verifies a mobile number with a SIMULATED code |
| SKIP | `test/live/live-api.test.ts` | live API: authentication and user management renews the access token from the httpOnly cookie |
| SKIP | `test/live/live-api.test.ts` | live API: authentication and user management resets the password and ends every existing session |
| SKIP | `test/live/live-api.test.ts` | live API: authentication and user management signs out and the token stops working at once |
| SKIP | `test/live/live-api.test.ts` | live API: authentication and user management deletes the account after re-authentication |

## Browser end-to-end (Playwright), by spec

48 cases: 48 passed, 0 failed, 0 skipped.

### admin.e2e.ts (2)

| Status | File | Test case |
|---|---|---|
| PASS | `admin.e2e.ts` | administrator dashboard > an administrator sees the overview, users and SMS administration |
| PASS | `admin.e2e.ts` | administrator dashboard > an ordinary user cannot open the admin area and the API refuses them |

### ai.e2e.ts (3)

| Status | File | Test case |
|---|---|---|
| PASS | `ai.e2e.ts` | AI assistant > is off until the person turns it on, and nothing is sent without them pressing Send |
| PASS | `ai.e2e.ts` | AI assistant > suggests smart replies from the conversation and lets the person reject them |
| PASS | `ai.e2e.ts` | AI assistant > turning the assistant off again hides its controls |

### auth.e2e.ts (4)

| Status | File | Test case |
|---|---|---|
| PASS | `auth.e2e.ts` | registration and login > a new person registers, confirms their email, sets up a profile and signs in again |
| PASS | `auth.e2e.ts` | registration and login > wrong credentials show one generic message and keep the person signed out |
| PASS | `auth.e2e.ts` | registration and login > registration form rejects a weak password and a missing consent before sending |
| PASS | `auth.e2e.ts` | registration and login > a returning person with a valid session is taken past the sign-in page |

### chat.e2e.ts (4)

| Status | File | Test case |
|---|---|---|
| PASS | `chat.e2e.ts` | Chikka-to-Chikka messaging > two people chat in real time and keep the same history after reload |
| PASS | `chat.e2e.ts` | Chikka-to-Chikka messaging > a message that contains markup is shown as text, never run |
| PASS | `chat.e2e.ts` | Chikka-to-Chikka messaging > people who are not contacts cannot start a conversation |
| PASS | `chat.e2e.ts` | Chikka-to-Chikka messaging > an outsider cannot open someone else's conversation |

### contacts.e2e.ts (3)

| Status | File | Test case |
|---|---|---|
| PASS | `contacts.e2e.ts` | contact management > finds a person by username, sends a request, and they accept it |
| PASS | `contacts.e2e.ts` | contact management > an unknown username finds nobody and says so |
| PASS | `contacts.e2e.ts` | contact management > rejecting a request leaves no contact, and removing a contact asks for confirmation |

### modes.e2e.ts (3)

| Status | File | Test case |
|---|---|---|
| PASS | `modes.e2e.ts` | Classic and Modern mode > switches between Modern and Classic, keeps the choice after reload and saves it |
| PASS | `modes.e2e.ts` | Classic and Modern mode > can be chosen from the settings page |
| PASS | `modes.e2e.ts` | Classic and Modern mode > a person who saved Classic gets Classic on a fresh sign-in |

### notifications.e2e.ts (2)

| Status | File | Test case |
|---|---|---|
| PASS | `notifications.e2e.ts` | notifications > a new message raises an unread notification that can be read and dismissed |
| PASS | `notifications.e2e.ts` | notifications > shows an empty state for a new person and a working settings page |

### profile.e2e.ts (4)

| Status | File | Test case |
|---|---|---|
| PASS | `profile.e2e.ts` | profile management > edits the display name and bio, and the change persists after a reload |
| PASS | `profile.e2e.ts` | profile management > rejects an over-long display name without saving |
| PASS | `profile.e2e.ts` | profile management > uploads a profile photo and refuses a file type that is not an image |
| PASS | `profile.e2e.ts` | profile management > verifies a mobile number from the simulated inbox |

### security.e2e.ts (18)

| Status | File | Test case |
|---|---|---|
| PASS | `security.e2e.ts` | unauthorised access > every protected endpoint refuses anonymous, malformed, unsigned and wrongly signed tokens |
| PASS | `security.e2e.ts` | unauthorised access > signed-out visitors are sent to sign-in from every private page |
| PASS | `security.e2e.ts` | cross-user data access > another person cannot read a contact, conversation, notification or SMS thread |
| PASS | `security.e2e.ts` | role escalation > a normal user cannot become an administrator by asking, or by editing their token |
| PASS | `security.e2e.ts` | role escalation > a token for someone else's session cannot be built by changing the subject |
| PASS | `security.e2e.ts` | webhook forgery > unsigned, wrongly signed, tampered and stale webhooks are rejected |
| PASS | `security.e2e.ts` | webhook forgery > a correctly signed webhook is accepted once and a replay is harmless |
| PASS | `security.e2e.ts` | rate limits > repeated wrong passwords lock the account, with Retry-After |
| PASS | `security.e2e.ts` | rate limits > sign-up is limited per address |
| PASS | `security.e2e.ts` | sensitive data exposure > responses never carry password data or tokens beyond the access token |
| PASS | `security.e2e.ts` | sensitive data exposure > errors use one safe envelope and an unknown origin is not allowed by CORS |
| PASS | `security.e2e.ts` | invalid input > malformed, oversize and hostile input is rejected cleanly |
| PASS | `security.e2e.ts` | invalid input > chat rejects an empty and an over-long message |
| PASS | `security.e2e.ts` | file upload restrictions > avatars accept images only, up to 2 MB, and reject disguised files |
| PASS | `security.e2e.ts` | file upload restrictions > chat attachments reject executables and oversize files |
| PASS | `security.e2e.ts` | session handling > refresh needs the CSRF header, and logging out ends the session everywhere |
| PASS | `security.e2e.ts` | session handling > signing out of other devices ends only the other devices |
| PASS | `security.e2e.ts` | session handling > a browser whose session was revoked elsewhere is returned to sign-in |

### sms.e2e.ts (5)

| Status | File | Test case |
|---|---|---|
| PASS | `sms.e2e.ts` | simulated SMS > sends a simulated SMS after confirmation and tracks it to delivered |
| PASS | `sms.e2e.ts` | simulated SMS > a reply from the other phone appears in the same thread, labelled simulated |
| PASS | `sms.e2e.ts` | simulated SMS > a message to a number that fails is shown as failed, never delivered, and is refunded |
| PASS | `sms.e2e.ts` | simulated SMS > without the recipient's consent the message cannot be reviewed or sent |
| PASS | `sms.e2e.ts` | simulated SMS > SMS is blocked until the sender has verified a mobile number |

