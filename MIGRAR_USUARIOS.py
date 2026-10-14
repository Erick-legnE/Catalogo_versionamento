from __future__ import annotations
import json, sys, os
from pathlib import Path
import auth_store as auth
ROOT=Path(__file__).resolve().parent
OLD=ROOT/'docs'/'usuarios.json'
NEW=ROOT/'usuarios.json'
if NEW.exists():
    raise SystemExit('usuarios.json privado já existe. Não sobrescrevi.')
if not OLD.is_file():
    raise SystemExit('Não encontrei docs/usuarios.json. Use seu backup antigo com os logins.')
rows=json.loads(OLD.read_text(encoding='utf-8'))
new=[]
for x in rows:
    role={'clientes':'cliente','representantes':'representante'}.get(str(x.get('tipo','')).lower(),'representante')
    pwd=x.get('password')
    if pwd is None: raise SystemExit('Senha ausente em registro antigo; abortado.')
    new.append({'id':x['id'],'nome':x.get('nome',''),'slug':x.get('slug',''),
        'username':x['username'],'password_hash':auth.password_hash(str(pwd)),
        'role':role,'permissoes':list(auth.ROLE_DEFAULTS[role]),'ativo':bool(x.get('ativo',True))})
auth.save_users({'version':2,'usuarios':new})
for folder in ('docs','src','dist'):
    p=ROOT/folder/'usuarios.json'
    if p.exists():p.unlink()
print('Migradas',len(new),'contas. Senhas agora armazenadas como hashes; arquivos públicos removidos.')
