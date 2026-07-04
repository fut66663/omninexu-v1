"""CDP Facilitator JWT authentication.

Generates EdDSA-signed JWTs for the CDP x402 Facilitator
(/supported, /verify, /settle endpoints).

Credentials are read from ``Settings`` (``.env`` file):
    ``CDP_API_KEY_ID`` — API key ID (e.g. "1873f551-...")
    ``CDP_API_KEY_SECRET`` — base64-encoded Ed25519 key (64 bytes:
    32 seed + 32 public key)
"""

import base64
import json
import secrets
import time

from cryptography.hazmat.primitives.asymmetric import ed25519

# CDP Facilitator API base path
_FACILITATOR_PATH = "/platform/v2/x402"
_HOST = "api.cdp.coinbase.com"
_EXPIRATION_SECONDS = 120


def _load_private_key(secret: str) -> ed25519.Ed25519PrivateKey:
    """Load an Ed25519 private key from a CDP API key secret.

    The CDP API key secret is a base64-encoded 64-byte blob:
    the first 32 bytes are the Ed25519 seed.
    """
    raw = base64.b64decode(secret)
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw[:32])


def _make_jwt(
    key_id: str, private_key: ed25519.Ed25519PrivateKey, uri: str
) -> str:
    """Create a CDP-signed JWT for the given URI.

    Matches the CDP SDK's ``generateJwt`` format:
    - Algorithm: EdDSA (Ed25519)
    - Claims: sub, iss, uris (array), aud (optional)
    - Standard JWT claims: iat, nbf, exp
    - Header: alg=EdDSA, kid=<key_id>, typ=JWT, nonce=<random>
    """
    now = int(time.time())
    nonce = secrets.token_hex(16)

    header = {
        "alg": "EdDSA",
        "kid": key_id,
        "typ": "JWT",
        "nonce": nonce,
    }
    payload = {
        "sub": key_id,
        "iss": "cdp",
        "uris": [uri],
        "iat": now,
        "nbf": now,
        "exp": now + _EXPIRATION_SECONDS,
    }

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()

    signature = private_key.sign(signing_input)
    sig_b64 = _b64url(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def create_cdp_auth_headers(
    key_id: str | None,
    key_secret: str | None,
) -> dict[str, dict[str, str]]:
    """Generate CDP Facilitator auth headers for all three endpoints.

    Returns a dict with keys ``supported``, ``verify``, ``settle``,
    each mapping to an ``Authorization: Bearer <JWT>`` header dict.
    """
    if not key_id or not key_secret:
        raise ValueError(
            "CDP_API_KEY_ID and CDP_API_KEY_SECRET must be provided"
        )

    private_key = _load_private_key(key_secret)
    bp = _FACILITATOR_PATH

    endpoints = {
        "supported": f"GET {_HOST}{bp}/supported",
        "verify": f"POST {_HOST}{bp}/verify",
        "settle": f"POST {_HOST}{bp}/settle",
    }

    return {
        name: {"Authorization": f"Bearer {_make_jwt(key_id, private_key, uri)}"}
        for name, uri in endpoints.items()
    }
