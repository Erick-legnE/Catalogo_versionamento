# Automação v8 - Fonte Nexa oficial nas Fichas

O layout do PDF da v7 foi preservado, mas agora usa:
- Nexa Bold: títulos e rótulos técnicos
- Nexa Regular: valores e corpo
- Nexa Light: "| Personalização a Laser" no título

## IMPORTANTE - Arquivo de fonte privado

A fonte NÃO acompanha o ZIP deste projeto. Use o ZIP de fontes Nexa que você
já tem em seu computador (o mesmo que você enviou na conversa).

1. Extraia este projeto.
2. Coloque **zipbomb.zip** na pasta principal, AO LADO de `server.py`
   (você também pode renomear o arquivo para `Nexa.zip`).
3. Execute `INICIAR_SERVIDOR.bat`.
4. Gere a ficha normalmente pelo `automacao.html`.

Também funciona com uma pasta ZIP externa, configurando a variável:

```bat
set NEXA_FONT_ZIP=C:\Caminho\do\seu\Nexa.zip
py server.py
```

O servidor lê apenas 3 fontes Nexa necessárias e converte os contornos de
OTF para TrueType em memória, pois ReportLab não aceita CFF diretamente. A
fonte nunca é extraída em disco e os arquivos de fonte não são distribuídos.
O PDF gerado inclui os glifos necessários para visualização consistente.

Sem o arquivo de fonte, a geração de PDF avisa sobre a ausência da Nexa,
em vez de produzir outra Ficha com uma fonte substituta silenciosamente.

## Escopo
Somente tipografia do PDF (e dependência de carregamento). Todos os campos,
layout, imagens, botões e fluxo do backend permanecem os da v7.
