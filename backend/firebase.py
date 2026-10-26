"""Checks a Firebase ID token: Firebase's proof that this phone number just passed the SMS code.

Firebase sends the SMS and checks the code in the browser. The browser then hands us the ID token,
and we verify its signature with Google's public certificates, following
https://firebase.google.com/docs/auth/admin/verify-id-tokens#verify_id_tokens_using_a_third-party_jwt_library
"""
import json
import re
import threading
import time
import urllib.request
from typing import Any

import jwt
from cryptography.x509 import load_pem_x509_certificate

CERTS_URL = "https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com"

_lock = threading.Lock()
_keys: dict[str, Any] = {}
_keys_until = 0.0


class InvalidToken(Exception):
    pass


def _fetch_keys() -> None:
    global _keys, _keys_until
    with urllib.request.urlopen(CERTS_URL, timeout=10) as res:
        certs: dict[str, str] = json.load(res)
        # Google says how long to keep them in Cache-Control: max-age.
        m = re.search(r"max-age=(\d+)", res.headers.get("Cache-Control", ""))
    _keys = {kid: load_pem_x509_certificate(pem.encode()).public_key() for kid, pem in certs.items()}
    _keys_until = time.time() + (int(m.group(1)) if m else 3600)


def _key_for(kid: str) -> Any:
    with _lock:
        # Refetch when the cache is old, or when Google has rotated to a key we haven't seen.
        if time.time() >= _keys_until or kid not in _keys:
            _fetch_keys()
        return _keys.get(kid)


def verify(id_token: str, project_id: str) -> tuple[str, str]:
    """Returns (firebase_uid, phone_number like '+919876543210'). Raises InvalidToken."""
    try:
        header = jwt.get_unverified_header(id_token)
    except jwt.PyJWTError as e:
        raise InvalidToken("Not a Firebase token") from e
    if header.get("alg") != "RS256" or not header.get("kid"):
        raise InvalidToken("Not a Firebase token")
    try:
        key = _key_for(header["kid"])
    except OSError as e:
        raise InvalidToken("Couldn't reach Google to check the login, try again") from e
    if key is None:
        raise InvalidToken("Unknown signing key")
    try:
        claims = jwt.decode(
            id_token, key, algorithms=["RS256"], audience=project_id,
            issuer=f"https://securetoken.google.com/{project_id}",
            options={"require": ["exp", "iat", "sub", "auth_time"]}, leeway=30,
        )
    except jwt.PyJWTError as e:
        raise InvalidToken("Login expired or invalid, try again") from e
    if not claims["sub"] or claims["auth_time"] > time.time() + 30:
        raise InvalidToken("Login expired or invalid, try again")
    phone = claims.get("phone_number")
    if not phone:
        raise InvalidToken("This login has no phone number")
    return claims["sub"], phone
