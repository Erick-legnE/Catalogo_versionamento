# Guia de uso do sistema

## 1. Iniciar o site

1. Execute `CRIAR_ADMIN.bat` uma vez para criar o primeiro acesso administrativo.
2. Execute `INICIAR_SERVIDOR.bat`.
3. Abra `http://127.0.0.1:8000/`.
4. Entre em **Automação** para enviar a solicitação, as artes e gerar a Ficha. Entre em **Administração** somente com uma conta administradora.

Se o site não iniciar, execute `py -m pip install -r requirements.txt` na pasta do projeto e tente novamente.

## 2. Catálogo e referência

Use o catálogo para localizar a referência, TAM e cor. A Ficha usa estes três campos para completar dados técnicos de `docs/data/referencias_consistem.json`, `docs/produtos.json` e `docs/data/cores_catalogo.json`.

Antes de aprovar uma Ficha, confirme que referência, TAM, cor e furação mostrados nela correspondem ao item físico. Dados ausentes devem ser corrigidos na fonte, nunca inventados no PDF.

## 3. Gerar uma Ficha

1. Abra Automação e selecione **Botão**.
2. Informe referência, TAM e cor.
3. Envie a prévia do botão e ao menos uma arte de personalização.
4. Gere a Ficha e revise o PDF antes de mover a solicitação para produção.

Para comparar uma Ficha com a execução Blender/Consistem, salve o item da Ficha em JSON e rode:

```powershell
py scripts\ficha_consistency.py `
  --provenance versions\...\botao.consistem.json `
  --item-json scripts\fixtures\ficha_item_13646.json `
  --report outputs\ficha_consistency.json
```

O relatório precisa indicar `ok: true` antes da liberação.

## 4. Gerar botão 3D pelo Consistem

O comando abaixo usa a planilha para escolher o registro e a faca, copia o construtor original para uma versão configurada e salva o `.blend` novo. Os scripts originais não são alterados.

```powershell
py scripts\consistem_blender_runner.py `
  --consistem "C:\caminho\CCCGI650TAB1.xlsx" `
  --reference 13646 --size 18 `
  --builder "C:\Users\Aprendiz Financeiro\Downloads\Erick\Scripts\blender\criador_blender.py" `
  --blender "C:\caminho\blender.exe" `
  --faca-dir "C:\caminho\facas" `
  --back-dxf "C:\caminho\op-40-44.dxf" `
  --output versions\minha-versao\button_13646_18.blend
```

Para textura, acrescente `--texture-script`, as três imagens, `--color-code`, e opcionalmente `--texture-mode PHOTO`. O arquivo geométrico permanece intacto: a textura agora roda numa cópia `*_textured.blend`.

## 5. Personalizados: nomes, letras e imagens

Comece sempre com um `.blend` base e salve um arquivo novo:

```powershell
& "C:\caminho\blender.exe" --background "base.blend" `
  --python scripts\blender_personalizado.py -- `
  --output "versions\ana.blend" --text "ANA" `
  --mode RAISE --font-size 2.6 --color EAD7A2 `
  --render --preview-camera
```

Opções principais:

- `--text "NOME"`: nome, letras, números e acentos.
- `--mode RAISE`: relevo visual.
- `--mode ENGRAVE --geometry BOOLEAN`: gravação real no mesh, apenas para texto.
- `--image "C:\arte\logo.png"`: prévia de imagem/logo na face.
- `--position "2,-1"`: deslocamento em mm na face, horizontal e vertical.
- `--rotation 15`: giro em graus.
- `--face FRONT|BACK|TOP`: face alvo. Use `FRONT` para os botões gerados pelo construtor atual.
- `--font "C:\fonte\minha_fonte.ttf"`: fonte opcional.

Imagens raster servem para simulação e aprovação visual. Para gravar um logotipo na produção, converta a arte aprovada para vetor e valide o contorno antes de fazer o corte.

## 6. Onde ficam as versões

Use uma subpasta em `versions/` por tentativa. Cada execução deve manter:

- `.blend` base e `.blend` personalizado/texturizado;
- `.png` de preview;
- `.consistem.json` com origem e geometria esperada;
- relatório de textura ou de consistência.

Nunca substitua o arquivo anterior se a intenção for comparar resultados.

## 7. Liberação, auditoria e backup

Antes da produção, valide a pasta da versão:

```powershell
py scripts\release_preflight.py --version-dir versions\minha-versao
```

O comando só lê arquivos. Ele exige `.blend` e proveniência do Consistem e falha quando algum deles estiver ausente ou inválido.

Alterações administrativas e mudanças de status agora entram em `server_data/audit.ndjson` (ou ao lado de `AUTOMACAO_STORAGE_DIR`). O log registra operador, ação, alvo e data, sem senha.

Depois de copiar `server_data/` para um disco ou local externo, valide a cópia antes de depender dela:

```powershell
py scripts\backup_validate.py --backup-dir "D:\Backups\BrasilBotoes\server_data"
```

O validador verifica manifests e cabeçalhos de Fichas PDF. Ele não altera o backup.
