from contextlib import nullcontext
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit

import httpx


class URLSecurityError(ValueError):
    pass


def _is_public_address(address):
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def validate_public_url(url, allow_private=False, resolver=None):
    if not isinstance(url, str) or not url.strip():
        raise URLSecurityError("URL must be a non-empty string")
    if len(url) > 2048:
        raise URLSecurityError("URL exceeds the maximum length")

    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise URLSecurityError("Only http and https URLs are allowed")
    if not parsed.hostname:
        raise URLSecurityError("URL must include a hostname")
    if parsed.username or parsed.password:
        raise URLSecurityError("Credentials in crawler URLs are not allowed")

    hostname = parsed.hostname.rstrip(".").lower()
    if not allow_private and hostname in {"localhost", "localhost.localdomain"}:
        raise URLSecurityError("Private or local network URLs are not allowed")

    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as e:
        raise URLSecurityError("URL contains an invalid port") from e

    try:
        ipaddress.ip_address(hostname.split("%", 1)[0])
        addresses = {hostname}
    except ValueError:
        resolver = resolver or socket.getaddrinfo
        try:
            addresses = {
                item[4][0] for item in resolver(
                    hostname, port, type=socket.SOCK_STREAM
                )
            }
        except (OSError, socket.gaierror) as e:
            raise URLSecurityError(f"Could not resolve URL hostname: {e}") from e

    if not addresses:
        raise URLSecurityError("URL hostname did not resolve")
    if not allow_private and any(
        not _is_public_address(address) for address in addresses
    ):
        raise URLSecurityError("Private or local network URLs are not allowed")

    return parsed.geturl()


def fetch_public_url(
    url,
    *,
    allow_private=False,
    max_redirects=5,
    timeout=15,
    max_bytes=5_000_000,
    client=None,
    resolver=None,
):
    """Fetch text content while validating DNS and every redirect target."""
    owned_client = client is None
    if owned_client:
        client = httpx.Client(
            follow_redirects=False,
            timeout=timeout,
            trust_env=False,
        )

    manager = client if owned_client else nullcontext(client)
    current = url
    redirect_statuses = {301, 302, 303, 307, 308}

    with manager as active_client:
        for redirect_count in range(max_redirects + 1):
            current = validate_public_url(
                current, allow_private=allow_private, resolver=resolver
            )
            with active_client.stream(
                "GET", current, headers={"User-Agent": "AIKA/1.0"}
            ) as response:
                if response.status_code in redirect_statuses:
                    location = response.headers.get("location")
                    if not location:
                        raise URLSecurityError(
                            "Redirect response did not include a location"
                        )
                    if redirect_count >= max_redirects:
                        raise URLSecurityError("Crawler redirect limit exceeded")
                    current = urljoin(current, location)
                    continue

                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if content_type and not any(
                    allowed in content_type
                    for allowed in ("text/", "application/xhtml+xml")
                ):
                    raise URLSecurityError(
                        f"Unsupported crawler content type: {content_type}"
                    )

                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise URLSecurityError(
                            "Crawler response exceeded the maximum size"
                        )
                encoding = response.encoding or "utf-8"
                return current, bytes(body).decode(encoding, errors="replace")

    raise URLSecurityError("Crawler redirect limit exceeded")
