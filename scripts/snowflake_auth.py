import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization


def load_private_key():
    """Load the Snowflake RSA private key.

    Local dev: SNOWFLAKE_PRIVATE_KEY_PATH points at a .p8 file on disk.
    Deployed (e.g. Hugging Face Spaces): SNOWFLAKE_PRIVATE_KEY holds the
    raw PEM content directly as a secret env var -- no file on disk needed.
    """
    pem_content = os.environ.get("SNOWFLAKE_PRIVATE_KEY")
    if pem_content:
        if "\\n" in pem_content and "\n" not in pem_content:
            pem_content = pem_content.replace("\\n", "\n")
        key_bytes = pem_content.encode("utf-8")
    else:
        with open(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"], "rb") as f:
            key_bytes = f.read()
    return serialization.load_pem_private_key(key_bytes, password=None, backend=default_backend())


def private_key_der(private_key=None):
    """DER-encoded bytes, the format snowflake.connector.connect(private_key=...) expects."""
    key = private_key or load_private_key()
    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
