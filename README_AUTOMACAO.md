# Esqueleto Integrado — Automação de Fichas

Este protótipo transforma a Automação em uma página irmã de `pastilhas.html`,
mas usando o mesmo `produtos.json` do Catálogo Geral.

## O que já funciona

- Novo card "Automação de Fichas" no portal `index.html`.
- Botão dentro do modal do `catalogo_geral.html` para abrir o produto já selecionado.
- `automacao.html` recebe `?reduzido=...` e carrega o mesmo produto do Catálogo Geral.
- Busca de produto por reduzido, referência, descrição ou cor.
- Prévia 2D simples da personalização.
- Estrutura de mapeamento referência+tamanho -> FRONT/BACK DXF.
- Mapeamento temporário salvo em `localStorage`.
- Geração/download de um `job.json`, que será o contrato do backend.
- Campos básicos da futura Ficha Técnica.

## O que ainda NÃO faz

- Não executa Blender.
- Não cria o `.blend`.
- Não renderiza a perspectiva.
- Não gera a Ficha Técnica em PDF.
- Não grava `facas.json` no servidor.

Essas ações exigem o backend Python que será a próxima etapa.

## facas.json

Estrutura proposta:

```json
{
  "version": 1,
  "mappings": {
    "REFERENCIA|TAMANHO": {
      "front_dxf": "facas/frente.dxf",
      "back_dxf": "facas/verso.dxf",
      "target_diameter_mm": 0,
      "target_thickness_mm": 0
    }
  }
}
```

Há também `facas.example.json` apenas para demonstrar o formato.

## job.json

O `automacao.html` gera um único objeto contendo:

- `product`
- `geometry`
- `personalization`
- `ficha`
- `requested_outputs`

A próxima etapa pode expor algo como:

`POST /api/jobs`

O backend salva o job, resolve os caminhos DXF, chama Blender em background e,
quando terminar, devolve os caminhos dos renders e da Ficha PDF.

## Filosofia

Não colocar Blender, Estampador e Ficha como sistemas independentes na interface.
O usuário vê um fluxo único. Internamente, cada um continua sendo um módulo.
