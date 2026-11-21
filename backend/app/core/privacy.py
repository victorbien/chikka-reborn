import ipaddress


def mask_phone(e164: str) -> str:
    """+639171234567 -> +63****4567 (country code and last four digits only).

    Mirrors private.mask_phone in the database so logs and audit rows agree.
    """
    if len(e164) < 8:
        return "****"
    return f"{e164[:3]}****{e164[-4:]}"


def mask_email(email: str | None) -> str | None:
    """marites@example.com -> m***@example.com. Enough for an admin to tell accounts apart."""
    if not email or "@" not in email:
        return None
    local, _, domain = email.rpartition("@")
    return f"{local[:1]}***@{domain}"


def ip_prefix(ip: str | None) -> str | None:
    """Coarse network prefix for audit rows: /24 for IPv4, /48 for IPv6. Never a full address."""
    if not ip:
        return None
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return None
    prefix = 24 if address.version == 4 else 48
    network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
    return str(network)
