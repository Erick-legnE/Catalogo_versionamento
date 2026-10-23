# Brasil Botões — catálogo e automação

Portal local para consulta de produtos, prévias de cores e criação de Fichas Técnicas em PDF. A interface pública é servida por `docs/`; as áreas de automação e administração usam o backend FastAPI em `server.py`.

## Executar localmente

1. Instale Python 3.11+.
2. Execute `py -m pip install -r requirements.txt`.
3. Crie o primeiro administrador com `CRIAR_ADMIN.bat`.
4. Inicie com `INICIAR_SERVIDOR.bat` e abra `http://127.0.0.1:8000/`.

O catálogo geral, Pastilhas e Prévia de Cores são públicos. Automação, catálogos individuais e Administração continuam protegidos por login e permissões.

## Imagens locais

The folders `imagens/` and `docs/imagens/` are intentionally excluded from Git because they contain several gigabytes of local product photos. Use object storage or Git LFS for a future public image release.

## Dados privados

`usuarios.json` é criado somente no computador que executa o servidor e fica ignorado pelo Git. Ele contém hashes de senha, nunca senhas em texto puro. `server_data/` guarda as solicitações e arquivos enviados localmente e também não deve ser publicado.

Para mover os arquivos enviados para fora do projeto, defina `AUTOMACAO_STORAGE_DIR` antes de iniciar. O limite padrão é 30 MB por arquivo, 120 MB por solicitação e 12 artes.

## Publicar no GitHub com segurança

- Não versione `usuarios.json`, planilhas internas, backups, arquivos `.blend` ou `server_data/`.
- Gere um administrador novo em cada instalação; não existe senha mestra no código.
- Para rede ou internet, use HTTPS, um proxy reverso, armazenamento persistente de sessões e uma política de redefinição de senha.
- O servidor embutido é adequado para uso local e desenvolvimento. Faça uma revisão de infraestrutura antes de expor o backend à internet.

## Arquitetura de prévias

As prévias de cores são ilustrações comerciais: regras e ajustes manuais transformam as descrições do cadastro em receitas visuais. O sistema de padrões de furos mantém a mesma ideia de dados compartilhados para prévia, Ficha e futuras integrações com Blender.
