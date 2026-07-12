import base64
import hashlib
from datetime import timedelta, timezone, datetime

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization


def prepare_account_name_for_jwt(raw_account: str) -> str:
    account = raw_account
    if ".global" not in account:
        idx = account.find(".")
        if idx > 0:
            account = account[0:idx]
    else:
        idx = account.find("-")
        if idx > 0:
            account = account[0:idx]
    return account.upper()


def generate_jwt(account: str, user: str, private_key_path: str, lifetime_minutes: int = 59) -> str:
    account_for_jwt = prepare_account_name_for_jwt(account)
    qualified_username = f"{account_for_jwt}.{user.upper()}"

    with open(private_key_path, "rb") as f:
        private_key = serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

    public_key_raw = private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(public_key_raw).digest()).decode("utf-8")

    now = datetime.now(timezone.utc)
    payload = {
        "iss": f"{qualified_username}.{fingerprint}",
        "sub": qualified_username,
        "iat": now,
        "exp": now + timedelta(minutes=lifetime_minutes),
    }
    token = jwt.encode(payload, key=private_key, algorithm="RS256")
    return token if isinstance(token, str) else token.decode("utf-8")
