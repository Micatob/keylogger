import os
import base64
import json

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


_SALT = "keylogger_v1".encode()
_KEY_CACHE = {}


def derive_key(password: str, salt: bytes = _SALT) -> bytes:
    cache_key = f"{password}:{salt.decode()}"
    if cache_key in _KEY_CACHE:
        return _KEY_CACHE[cache_key]
    if not _HAS_CRYPTO:
        result = password.encode().ljust(32, b"\0")[:32]
        _KEY_CACHE[cache_key] = result
        return result
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600000)
    result = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    _KEY_CACHE[cache_key] = result
    return result


_FERNET_CACHE = {}


def _get_fernet(key: str):
    if key not in _FERNET_CACHE:
        _FERNET_CACHE[key] = Fernet(derive_key(key))
    return _FERNET_CACHE[key]


def encrypt(plaintext: str, key: str = "") -> str:
    if not plaintext:
        return ""
    if _HAS_CRYPTO and key:
        f = _get_fernet(key)
        return f.encrypt(plaintext.encode()).decode()
    return base64.b64encode(plaintext.encode()).decode()


def decrypt(ciphertext: str, key: str = "") -> str:
    if not ciphertext:
        return ""
    if _HAS_CRYPTO and key:
        try:
            f = _get_fernet(key)
            return f.decrypt(ciphertext.encode()).decode()
        except Exception:
            pass
    try:
        return base64.b64decode(ciphertext).decode()
    except Exception:
        return ciphertext


def encrypt_dict(data: dict, key: str) -> str:
    return encrypt(json.dumps(data), key)


def decrypt_dict(ciphertext: str, key: str) -> dict:
    raw = decrypt(ciphertext, key)
    try:
        return json.loads(raw)
    except Exception:
        return {}


def load_encrypted_config(config_path: str, master_key: str) -> dict:
    if not os.path.isfile(config_path):
        return {}
    try:
        with open(config_path, "r") as f:
            return decrypt_dict(f.read(), master_key)
    except Exception:
        return {}


def save_encrypted_config(data: dict, config_path: str, master_key: str):
    encrypted = encrypt_dict(data, master_key)
    with open(config_path, "w") as f:
        f.write(encrypted)
