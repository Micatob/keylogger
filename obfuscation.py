import base64

def obf(s: str) -> str:
    return base64.b64encode(s.encode('utf-8')).decode('utf-8')

def deobf(s: str) -> str:
    return base64.b64decode(s).decode('utf-8')
