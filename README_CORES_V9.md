# Brasil Botões — Prévia de Cores v9

Esta atualização mantém o **Catálogo Geral + Automação + Ficha PDF (Nexa)** da versão anterior e acrescenta prévias de cores ilustrativas a partir do arquivo **Cores1.xlsx**.

## Como iniciar

No diretório principal, execute `INICIAR_SERVIDOR.bat` e abra:

- `http://localhost:8000/cores_preview.html` — galeria de cores com pesquisa e filtros;
- `http://localhost:8000/automacao.html` — o campo COR controla a prévia do botão.

A nova galeria também aparece no portal (`index.html`) e a Automação tem um atalho próximo ao campo Cor.

## O que faz

- Carrega os **3.301 códigos** da aba `COD` do `Cores1.xlsx`.
- Dá prioridade a uma **foto real de produto da mesma REF+COR** ou foto/pastilha indexada quando disponível.
- Sem foto utilizável, usa uma prévia ilustrativa baseada nas **palavras do cadastro**.
- Diferencia cor única, borda/fundo, camadas, mesclado/rajado, degradê, tartaruga, madeira e transparente.
- Códigos sem informação visual adequada aparecem como **indefinidos** (botão neutro com `?`).
- A prévia exportada pelo `automacao.html` inclui o padrão visual dos furos e, como antes, pode integrar o PDF.
- Cada REF+TAM pode usar um padrão de furos reaproveitável, com número de furos derivado do histórico Consistem e afastamento visual influenciado pela distância de furos disponível no cadastro.

**ATENÇÃO:** Este é um simulador comercial. Não reproduz cor RGB medido, acabamento físico exato, espessura de camadas, posição real dos furos nem geometria especial. Não use como desenho técnico. A posição exata dos furos precisa de validação por faca/planta.

## Arquivos principais

```text
/docs/cores_preview.html
/docs/automacao.html
/docs/js/color_preview.js
/docs/js/hole_preview.js
/docs/data/cores_catalogo.json
/docs/data/cores_overrides.json
/docs/data/cores_review.json
/docs/data/hole_patterns.json
/docs/data/ref_hole_map.json
/gerar_cores_json.py
```

`cores_catalogo.json`: texto original mais `preview.kind`, `preview.palette`, `preview.effects` e `preview.confidence` para cada código.

`cores_review.json`: códigos de baixa confiança, indefinidos e duplicados, para correção futura.

`cores_overrides.json`: correções manuais de cor. Exemplo para **uma cor verificada**:

```json
{
  "version": 1,
  "colors": {
    "C1234": {
      "kind": "border_core",
      "palette": ["#40362f", "#d2b98a"],
      "effects": [],
      "confidence": "manual"
    }
  }
}
```

A primeira cor na lista é a borda e a segunda é o fundo/centro. Guarde essa intervenção como visual, não técnico. O script de importação **nunca sobrescreve as correções**.

`hole_patterns.json`: biblioteca dos padrões ilustrativos (0–9 furos) em unidades relativas ao raio da prévia, não em mm.

`ref_hole_map.json`: REF → TAM → `pattern`, `count`, distância de furos e broca do Consistem; também aceita configurações revisadas manualmente. Para padrões especiais, adicione um novo padrão em `hole_patterns.json` e associe-o a REF/TAM no mapa. Medidas e furos especiais devem ser verificados manualmente antes de serem tratados como precisos.

## Atualizando com uma planilha nova

Deixe o novo Excel em algum lugar do PC e rode, na pasta principal do site:

```bat
py gerar_cores_json.py "C:\caminho\Cores1.xlsx"
```

Isso atualiza `docs/data/cores_catalogo.json` e `docs/data/cores_review.json` sem modificar o arquivo Excel, e sem instalar dependências externas.

**Não exclua** o seu `zipbomb.zip`/pacote de fontes Nexa: as fichas PDF da versão anterior continuam usando a fonte fornecida por você. Arquivos de fonte não estão incluídos neste pacote.

## Limitação das fotos

Um código no índice de fotos pode apontar para imagem ausente no diretório atual — especialmente se você compartilhou o site sem as fotos. O navegador tenta abrir a foto; se falhar, volta à receita ilustrativa, quando houver.
