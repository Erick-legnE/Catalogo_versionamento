# Automação v3

Mudanças visíveis:
- "Solicitação preparada" removido como conceito enganoso.
- O protótipo agora deixa claro que nada é enviado enquanto o backend não existe.
- Arte da personalização aceita múltiplas imagens.
- Cada imagem é uma camada independente com escala, rotação, X, Y e curvatura.
- Furos da prévia visual foram aumentados.
- O JSON interno agora usa `personalization.assets[]`.

Facas:
- `facas_library/` contém as cópias organizadas e os relatórios.
- `docs/data/facas.json` contém o mesmo registry para testes.
- O arquivo original nunca é renomeado/apagado.

Importante:
O ID no nome de uma faca não deve ser tratado automaticamente como referência
comercial. A arquitetura correta é:

referência -> referencias_consistem.json -> faca_frente -> facas.json -> DXF
