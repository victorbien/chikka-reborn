from app.core.privacy import mask_email


def test_mask_email_keeps_first_letter_and_domain() -> None:
    assert mask_email("marites@example.com") == "m***@example.com"


def test_mask_email_handles_missing_or_malformed_values() -> None:
    assert mask_email(None) is None
    assert mask_email("") is None
    assert mask_email("not-an-email") is None
