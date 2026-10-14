# Catálogo Geral + Automação v4 — backend local

Esta versão coloca o primeiro backend real diretamente no projeto principal.

## Como iniciar

NÃO use `py -m http.server` nesta versão.

Dê dois cliques em:

    INICIAR_SERVIDOR.bat

ou:

    py server.py

Abra:

    http://localhost:8000/
    http://localhost:8000/automacao.html

## O que o botão da Automação faz

`Salvar solicitação no servidor` envia:

- `solicitacao.json`
- `manifest.json`
- `preview.png`
- todas as artes de personalização (`arte_01`, `arte_02`, ...)
- a imagem base quando o modo é `Outro item`

para:

    server_data/
      solicitacoes/
        AAAA/
          MM/
            <id-da-solicitacao>/

Exemplo:

    server_data/solicitacoes/2026/10/
      20261009_120000_ref-13649_tam-28_c3263_ab12cd34/
        solicitacao.json
        manifest.json
        preview.png
        arte_01.png
        arte_02.svg

## Endpoint atual

    GET  /api/health
    POST /api/solicitacoes/export
    GET  /api/solicitacoes/{id}
    GET  /api/solicitacoes/{id}/files/{filename}

Esse diretório será a entrada da próxima etapa:

    solicitação armazenada
        -> resolver técnico
        -> Blender headless
        -> GLB/renders
        -> Ficha PDF

## Mover o armazenamento

No Windows:

    set AUTOMACAO_STORAGE_DIR=D:\BrasilBotoesData\solicitacoes
    py server.py

Assim os arquivos ficam fora da pasta do site.

## Observação

Esta versão ainda NÃO chama Blender nem gera o PDF.
Ela implementa somente o primeiro loop real:

    automacao.html -> FastAPI -> filesystem local
