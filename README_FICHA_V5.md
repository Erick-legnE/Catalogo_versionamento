# Brasil Botões — Catálogo + Automação v5 (Ficha PDF)

Execute **INICIAR_SERVIDOR.bat** na pasta principal e abra `http://localhost:8000/automacao.html`.

## Fluxo atual

1. Representante informa REF/TAM/COR ou envia foto de outro item.
2. Adiciona uma ou mais artes e define escala **0–500%**, rotação, posição e curvatura.
3. Informa cliente, representante e observações.
4. Clica em **Gerar e salvar Ficha Técnica (PDF)**.
5. O servidor grava os originais, a prévia 2D, o JSON, o manifest e `ficha_tecnica.pdf`.
6. A página mostra **Abrir PDF** e **Baixar PDF**.

O documento usa as seções da Ficha Técnica anterior como referência: dados comerciais, identificação, detalhes da personalização e simulação. O documento é identificado como **prévia para aprovação**, porque **não existem medições reais nem um modelo 3D nesta etapa**.

## Endpoints

- `GET /api/health`
- `POST /api/fichas/export` (novo nome)
- `POST /api/solicitacoes/export` (alias compatível)
- `GET /api/solicitacoes/{id}`
- `GET /api/solicitacoes/{id}/pdf` (prévia inline)
- `GET /api/solicitacoes/{id}/pdf?download=1`
- `GET /api/solicitacoes/{id}/files/{filename}`

## Dados salvos

```
server_data/solicitacoes/AAAA/MM/<id>/
   solicitacao.json
   manifest.json
   preview.png
   arte_01.png
   arte_02.jpg
   ficha_tecnica.pdf
```

`AUTOMACAO_STORAGE_DIR` pode mudar a pasta de saída.

**Atenção para uso fora de localhost:** implemente autenticação e controle de acesso antes de disponibilizar os endpoints na rede. As fichas incluem arquivos de clientes e não devem ficar publicamente acessíveis.

O PNG do botão pode utilizar uma foto ilustrativa, não necessariamente uma fotografia do produto exato quando a combinação é inédita. **Nunca trate a prévia como confirmação de cor real ou dimensions físicas**. SVG é guardado como original (o PDF mostra prévia renderizada do navegador).
