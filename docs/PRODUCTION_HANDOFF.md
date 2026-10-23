# Handoff de produção e liberação

## Responsáveis

| Etapa | Responsável | Evidência exigida |
| --- | --- | --- |
| Cadastro | Engenharia/Cadastro | referência, TAM, cor, faca e furação conferidos no Consistem |
| Modelagem | Desenvolvimento 3D | `.blend` base e `.consistem.json` na pasta da versão |
| Textura e personalização | Criação | `.blend` derivado, preview PNG e arte aprovada |
| Ficha | Atendimento/Engenharia | PDF revisado e relatório de consistência sem divergências |
| Liberação | Responsável de produção | checklist completo e aprovação registrada |

## Critérios de aceitação

1. A referência e o TAM encontram uma única linha válida no Consistem.
2. A faca frontal e a faca traseira existem e foram registradas na proveniência.
3. Diâmetro, espessura, furação e cor da Ficha batem com a proveniência.
4. A arte está dentro da área aprovada e o preview foi revisado.
5. O arquivo base continua preservado ao lado da versão texturizada ou personalizada.
6. O operador registra a versão aprovada antes de enviar para produção.

## Gate de liberação

Não liberar quando qualquer item acima falhar, quando a Ficha indicar campo técnico pendente, ou quando a personalização exigir vetor e só houver uma imagem raster. Corrija a fonte e gere uma nova versão.

## Change log

Para cada alteração, registre data, referência/TAM, motivo, arquivo anterior, arquivo novo, quem revisou e resultado. Guarde o registro junto da pasta `versions/` da execução.
