# Automação integrada v2

## Mudança de filosofia

A tela do representante NÃO escolhe código reduzido, faca, DXF, espessura física ou diâmetro em mm.
Ela recebe o que normalmente chega do cliente:

- Referência
- TAM
- Cor
- Arte em imagem
- Cliente / representante / observações

A combinação referência + TAM + cor pode ser nova e não precisa existir como produto acabado no Consistem.

## Dados Consistem incorporados

`docs/data/referencias_consistem.json` foi gerado de `CCCGI650TAB1.xlsx` e indexa 3236 referências de botão.
Ele é interno e serve para resolver engenharia sem expor campos técnicos na interface.

`docs/data/pastilhas_consistem.json` foi gerado de `CCCGI650TAB1 (1).xlsx`:

- 50533 linhas no relatório
- 9748 linhas com descrição contendo PASTILHA
- 9516 pastilhas regulares no padrão TAM / espessura / C####
- 2280 cores distintas
- 2060 registros de pastilha com saldo positivo

`docs/data/pastilhas_fotos_index.json` representa o acervo de fotos já existente em `pastilhas.json`.

## Comportamento da tela

### Botão
A pessoa digita livremente referência, TAM e cor. A tela NÃO obriga a combinação a existir como código reduzido.
Se houver dados históricos, mostra somente status úteis (referência conhecida, pastilha conhecida, foto disponível).

### Outro item
A pessoa envia uma foto do item. O protótipo usa a imagem como superfície 2D de pior caso e posiciona a arte em cima.

### Personalização
A entrada é uma imagem (PNG/JPG/WebP/SVG), não texto/fonte. Há apenas controles de:

- escala
- rotação
- posição X/Y
- curvatura

### Ficha
Solicita somente cliente, representante e observações. Código personalizado é `AUTO`; pedido/projeto não aparece.

## Sobre o antigo “Job Único”

Ele continua existindo como contrato interno de dados, mas foi removido da experiência do representante.
O botão “Gerar Ficha Técnica” futuramente fará um POST para o backend com esse objeto interno, executará Blender/render/PDF e mostrará apenas progresso/resultado.

No protótipo há um `<details>` de desenvolvimento para inspecionar/baixar esse JSON durante a construção do backend.
