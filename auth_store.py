"""Private usuarios.json, password hashing, sessions and fine-grained permissions."""
from __future__ import annotations
import hashlib, hmac, json, os, secrets, threading, time
from pathlib import Path

HERE=Path(__file__).resolve().parent
USERS_FILE=HERE/'usuarios.json'
AREAS=('catalogo','pastilhas','automacao','cores_preview','engenharia','subsites','admin')
ROLE_DEFAULTS={
 'cliente':['catalogo'],
 'representante':['catalogo','pastilhas','automacao'],
 'funcionario':['catalogo','pastilhas','cores_preview','automacao','subsites'],
 'admin':list(AREAS),
}
SESSIONS={}
LOCK=threading.RLock()
LIFETIME=12*60*60
COOKIE='bb_session'

def password_hash(value: str) -> str:
    salt=secrets.token_bytes(16)
    digest=hashlib.pbkdf2_hmac('sha256',value.encode(),salt,360000)
    return f'pbkdf2_sha256$360000${salt.hex()}${digest.hex()}'

def verify_password(password: str, stored: str) -> bool:
    try:
        algo,n,salt_hex,digest_hex=stored.split('$')
        if algo!='pbkdf2_sha256': return False
        n=int(n)
        if n<100000 or n>1000000: return False
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt_hex),n)
        return hmac.compare_digest(digest,bytes.fromhex(digest_hex))
    except (ValueError,TypeError):
        return False

def load_users() -> dict:
    with LOCK:
        if not USERS_FILE.is_file():
            raise RuntimeError('usuarios.json privado ausente. Execute a migração primeiro.')
        data=json.loads(USERS_FILE.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or not isinstance(data.get('usuarios'),list):
            raise RuntimeError('usuarios.json inválido: esperada uma lista de usuários.')
        return data

def save_users(data: dict) -> None:
    with LOCK:
        if not isinstance(data,dict) or not isinstance(data.get('usuarios'),list):
            raise ValueError('Banco de usuários inválido.')
        path=USERS_FILE.with_suffix('.json.part')
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(path, USERS_FILE)

def find_user(username: str, users: list) -> dict|None:
    name=str(username or '').strip().casefold()
    if not name: return None
    return next((u for u in users if str(u.get('username','')).casefold()==name or str(u.get('slug','')).casefold()==name or str(u.get('id','')).casefold()==name),None)

def safe_user(user: dict) -> dict:
    return {k:user.get(k) for k in ('id','nome','username','slug','role','ativo','permissoes')}

def has(user: dict|None, area: str) -> bool:
    if not user or user.get('ativo') is not True: return False
    return area in user.get('permissoes',[])

def create_session(user: dict) -> tuple[str,str]:
    token=secrets.token_urlsafe(40)
    csrf=secrets.token_urlsafe(24)
    with LOCK:
        SESSIONS[token]={'user_id':user['id'],'expires':time.time()+LIFETIME,'csrf':csrf}
    return token,csrf

def get_session(token: str|None):
    if not token: return None,None
    with LOCK:
        entry=SESSIONS.get(token)
        if entry and time.time()>entry['expires']:
            SESSIONS.pop(token,None)
            return None,None
    if not entry: return None,None
    user=next((u for u in load_users()['usuarios'] if u['id']==entry['user_id']),None)
    if not user or not user.get('ativo'):
        with LOCK: SESSIONS.pop(token,None)
        return None,None
    return user,entry

def destroy_session(token: str|None):
    if token:
        with LOCK: SESSIONS.pop(token,None)
