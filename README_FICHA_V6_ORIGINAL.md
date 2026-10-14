# Ficha original integrada no Catálogo Geral (v6)

Esta versão NÃO redesenha a Ficha. O PDF é gerado a partir do HTML/CSS `.sheet` do
`brasil-botoes-fichas(1).zip` fornecido pelo usuário.

## O que é reaproveitado diretamente
- Cabeçalho `Ficha Técnica | Personalização a Laser` e data no topo
- Coluna de dados técnicos na esquerda
- Retângulo cinza de detalhamento com borda teal na direita
- Duas imagens lado a lado (pequena / ampliada)
- Assinatura Brasil Botões + slogan na base
- Regras tipográficas e cores da folha original (`style_original.css`)

## Ajustes necessários
- Fonte de dados: automacao.html (REF, TAM, COR, representante, cliente, observações).
- Campos ainda não conhecidos NÃO recebem valores inventados.
- Código personalizado não definido aparece como traço (processo posterior).
- Legendas das imagens indicam simulação (ainda não existe modelo 3D nem escala real verificada).
- Imagens são as previsualizações 2D do site, redimensionadas para as caixas antigas.

## Requisito do gerador de PDF
Chrome ou Microsoft Edge deve estar instalado na máquina Windows do servidor.
No Windows 10/11 isso normalmente já é verdade. Caso queira definir o caminho:

    set FICHA_BROWSER_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
    py server.py

A geração é feita em modo headless, sem abrir janela. Não há dependência de Blender.

## Execução

    INICIAR_SERVIDOR.bat
    http://localhost:8000/automacao.html

Arquivos gerados automaticamente:

    server_data/solicitacoes/AAAA/MM/ID/ficha_tecnica.pdf
    server_data/solicitacoes/AAAA/MM/ID/ficha_tecnica.html

No futuro é possível editar o HTML da ficha usando o original como referência.
