# Fluxo Planner — importação e Blender opcional

## Testar a ficha

```powershell
python -m unittest scripts.test_planner_work -v
```

## Importar uma exportação do Consistem sem SQL

```powershell
python scripts/consistem_sync.py --source C:\entrada\consistem.csv --output server_data\consistem_sync\cadastros.csv --once
```

Para acompanhar um arquivo exportado periodicamente, acrescente `--watch`.
O intervalo padrão é 60 segundos; use `--interval 60` para deixá-lo explícito.
O importador normaliza os cabeçalhos, elimina duplicidades e grava `sync_report.json` ao lado do CSV.

## Gerar um botão no Blender

O gerador lê `referencias_consistem.json` e `hole_patterns.json`, usa referência + TAM para posicionar os furos e salva um `.blend` separado:

```powershell
blender --background --python scripts/blender_button.py -- --reference 16 --size 18 --output outputs\button_16_18.blend --render
```

O servidor web continua gerando a Ficha PDF e a prévia 2D mesmo quando Blender não está instalado. O `.blend` é um artefato opcional do fluxo de produção.
