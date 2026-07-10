"""Small shared security helpers used by CLI, web, and adapters."""

from __future__ import annotations

import os
import ipaddress
import socket
from urllib.parse import urlparse

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def validate_llm_url(url: str) -> str | None:
    """SSRF guard for user-supplied local LLM endpoints.

    Empty URLs are allowed and mean "use the backend default" (returns
    None). Non-empty URLs must be http(s). Loopback hosts are allowed by
    default. RFC1918/private hosts are allowed only when explicitly named in
    SOCIOSIM_LLM_ALLOWED_HOSTS; link-local metadata hosts, multicast and
    reserved ranges are always blocked.

    Returns the exact IP address that passed the checks (E-05): callers
    that make the request must TCP-connect to THIS pinned address (keeping
    the original hostname for the Host header / TLS SNI) rather than
    resolving DNS again, which would reopen the validate-then-rebind
    TOCTOU window this guard exists to close.
    """
    if not url:
        return None
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise ValueError("llm_base_url scheme must be http or https")
    host = p.hostname or ""
    try:
        # An IP-literal host (127.0.0.1, ::1, 10.0.0.5, ...) pins itself.
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and literal.is_loopback:
        return str(literal)
    if host in LOOPBACK_HOSTS:
        # Named loopback ("localhost"): pin the canonical loopback address
        # rather than trusting a later resolver call.
        return "127.0.0.1"
    allowed_private = {
        h.strip().lower()
        for h in os.environ.get("SOCIOSIM_LLM_ALLOWED_HOSTS", "").split(",")
        if h.strip()
    }
    try:
        infos = socket.getaddrinfo(host, p.port or 80)
    except OSError as exc:
        raise ValueError(f"llm_base_url host not resolvable: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise ValueError(
                f"llm_base_url host {ip} is link-local/metadata/reserved")
        if ip.is_loopback:
            continue
        if ip.is_private and (host.lower() in allowed_private or str(ip) in allowed_private):
            continue
        if ip.is_private:
            raise ValueError(
                "llm_base_url private hosts require SOCIOSIM_LLM_ALLOWED_HOSTS")
        else:
            raise ValueError(
                f"llm_base_url must point to a loopback/allowed private host (got public {ip})")
    # Every resolved address passed; pin the first one.
    return str(ipaddress.ip_address(infos[0][4][0]))
