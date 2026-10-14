# Ficha Técnica v7 — layout das fichas reais

Esta versão altera somente o template `ficha_pdf.py` do Catálogo Geral/Automação.

## Referências visuais

Reconstruído a partir dos PDFs enviados pelo usuário, incluindo:
- P4975 / Ref. 13764
- P4977 e P4984 / Ref. 13766
- P4999 / Refs. 10613/10616
- P5000 / Ref. 13776
- P5008 / Ref. 13781
- P5037 / Ref. 13787
- P5150 / Ref. 1350 / TAM 18/28/30

Elementos mantidos:
- folha A4 única, cabeçalho "Ficha Técnica | Personalização a Laser"
- especificações na coluna esquerda, valores em azul/turquesa
- caixa cinza de detalhamento à direita com faixa turquesa
- simulação reduzida e ampliada com muito espaço branco
- logo oficial fornecida, rodapé "Transformamos o essencial no seu diferencial."

## Regras do estágio atual

- Continua usando `automacao.html` e seu formulário REF/TAM/COR/arte.
- Não há 3D nem Blender.
- Nenhuma dimensão de diâmetro ou espessura é inventada a partir de TAM.
- Código personalizado P... e Pedido são deixados em branco até a etapa interna.
- Pequena observação no PDF esclarece que a simulação é 2D.
- A prévia do navegador é incluída como imagem, NÃO como render de perspectiva real.
- O código usa ReportLab + Pillow e não precisa de Chrome/Edge no servidor.

## Iniciar

Extraia, execute `INICIAR_SERVIDOR.bat` na pasta principal e abra:
`http://localhost:8000/automacao.html`

Os PDFs são guardados em `server_data/solicitacoes/AAAA/MM/<ID>/ficha_tecnica.pdf`.

## Troca do template

Em uma instalação v6 existente, os únicos arquivos necessários são:
- `ficha_pdf.py` (sobrescrever no diretório principal)
- `assets/logo_brasil_botoes_oficial.png` (nova pasta)

As APIs e o resto do site permanecem iguais.
