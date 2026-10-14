from __future__ import annotations
import getpass, sys, uuid
import auth_store as a

def main():
    data=a.load_users()
    action=sys.argv[1] if len(sys.argv)>1 else 'add-admin'
    if action!='add-admin':
        raise SystemExit('Uso: py CRIAR_ADMIN.py add-admin')
    username=input('Login do administrador: ').strip()
    if not username or a.find_user(username,data['usuarios']):
        raise SystemExit('Usuário vazio ou já cadastrado.')
    password=getpass.getpass('Senha (mínimo 12 caracteres recomendado): ')
    confirm=getpass.getpass('Confirme a senha: ')
    if password!=confirm or len(password)<8:
        raise SystemExit('Senhas diferentes ou muito curtas.')
    data['usuarios'].append({'id':'u_'+uuid.uuid4().hex,'nome':input('Nome: ').strip() or 'Administrador',
        'slug':'','username':username,'password_hash':a.password_hash(password),
        'role':'admin','permissoes':list(a.AREAS),'ativo':True})
    a.save_users(data)
    print('Administrador criado no usuarios.json privado. Use este login no portal.')
if __name__=='__main__':main()
