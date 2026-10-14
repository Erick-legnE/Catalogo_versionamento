# Catálogo Geral v10 — Acesso por usuário

O arquivo **`usuarios.json` fica na pasta principal**, AO LADO de `server.py`, nunca dentro de `docs/`.
Ele mantém os 136 usuários existentes com a senha armazenada como `password_hash` (PBKDF2 SHA-256) e os campos `role`, `permissoes`, `ativo`.

## Iniciar
1. Extraia o ZIP completo em uma pasta nova. NÃO substitua apenas `docs/` de uma instalação antiga.
2. Execute `CRIAR_ADMIN.bat` **uma vez** e escolha o novo login/senha administrativa. Não há senha mestra pronta.
3. Execute `INICIAR_SERVIDOR.bat` e visite `http://localhost:8000`.
4. Entre com seu login. Como admin, abra **Administração de Usuários** no portal.
5. Altere as permissões por usuário, cadastre funcionários e desative contas quando necessário.

## Permissões editáveis
- `catalogo`: Catálogo Geral
- `pastilhas`: catálogo de Pastilhas
- `automacao`: Ficha/Automação
- `cores_preview`: galeria de cores (representantes não recebem por padrão)
- `engenharia`: seções técnicas futuras
- `subsites`: abrir qualquer subcatálogo individual (reps e clientes sem esta permissão veem só o próprio)
- `admin`: administração de usuários.

O servidor verifica cada acesso direto a páginas, além de esconder os cards no portal. API de Fichas exige login e permissão; fichas novas são restritas ao usuário que as criou ou a um admin.

## ATUALIZAÇÃO DE UMA INSTALAÇÃO ANTIGA (patch)
1. Pare o servidor. Faça backup da pasta.
2. Copie os arquivos do patch para a pasta **raiz** do site (incluindo `server.py`, `docs/index.html`).
3. Se o `usuarios.json` privado ainda não existir, execute `py MIGRAR_USUARIOS.py` ANTES de reiniciar. Usa `docs/usuarios.json` anterior, gera hashes privados e remove o arquivo público. Não elimina nenhuma conta.
4. Execute `CRIAR_ADMIN.bat` e depois `INICIAR_SERVIDOR.bat`.
5. Se ainda existir `docs/usuarios.json` antigo em algum local servido, remova-o. O novo servidor o bloqueia de qualquer forma.

Não publique esse ZIP como site estático; a autorização depende de `server.py`. É uma implementação local de desenvolvimento. Para rede/internet de produção use HTTPS, uma store persistente de sessões, controles de rede e políticas para senhas/redefinição.

## Exemplo de usuário (sem senha)
```
{
  "id":"u_...",
  "nome":"Funcionário",
  "username":"funcionario",
  "role":"funcionario",
  "ativo":true,
  "permissoes":["catalogo","pastilhas","automacao","cores_preview"]
}
```
