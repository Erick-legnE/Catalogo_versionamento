# Production pipeline

The production path is reference-first:

1. Read one Consistem row by reference and TAM.
2. Stage a copy of the original `criador_blender.py`.
3. Configure dimensions, thickness, front faca, hole count, drill radius, and hole spacing.
4. Build and save a versioned `.blend` without modifying the original script.
5. Optionally stage `textura_blender.py` and apply front, verso, and side images.
6. Save a textured `.blend`, JSON provenance, and texture analysis report.
7. Verify dimensions, hole metadata, topology, face counts, and report output.

The runner keeps every generated staged script next to its output so a result can
be reproduced or compared later.

## Site-to-Blender integration

The site now queues a saved request through `POST /api/solicitacoes/{id}/render`.
Only an administrator can call this endpoint.  It changes the request to
`rendering_3d`; it does not launch Blender in the web process.

Run the worker on the machine that has Blender and the base `.blend` files:

```powershell
$env:AUTOMACAO_STORAGE_DIR = 'D:\BrasilBotoesData\solicitacoes'
$env:AUTOMACAO_BLENDER_EXE = 'C:\Program Files\Blender Foundation\Blender 4.5\blender.exe'
$env:AUTOMACAO_BLENDER_BASE_DIR = 'D:\BrasilBotoesData\base_blends'
python scripts\blender_worker.py --loop
```

The base directory must contain files named `button_<reference>_<TAM>.blend`,
for example `button_13646_18.blend`.  The worker claims queued manifests,
processes each native text layer through `scripts/blender_personalizado.py`,
and writes `blender/personalized.blend`, reports, renders, and subprocess logs
inside that request's folder.  Successful requests become `rendered_3d`; a
missing base file, missing Blender executable, timeout, or Blender failure
becomes `render_error` with the reason recorded in the request history.
The worker also requires the report and PNG render to exist.  Boolean steps
must prove that the body vertex count increased and that boundary and
non-manifold edge counts are zero.  The request page exposes the resulting
`.blend` and preview links only after this evidence gate passes.

The worker can be checked without launching Blender:

```powershell
python scripts\blender_worker.py --once --dry-run
```

### Imported-font and reverse-pastilha contract

The Automação page accepts one optional `.ttf` or `.otf` file up to 10 MB.
The server validates it with `fontTools`, stores it inside the request package,
records its family, SHA-256 digest, and original name, and gives the exact
stored file to Blender through `solicitacao.json`.  A worker must fail rather
than silently substitute a system font when a request declares an uploaded
font whose file is missing.

Every pastilha request also records the production rule
`pastilha_back_face_recess_mm: 0.2`.  This means the reverse background is
removed by 0.20 mm and can reveal the other C colour.  The colour saved in the
request is catalogue-derived visual provenance, not a physical colour
measurement.  The present worker carries this rule in its Blender report; a
base-button construction must implement the corresponding recess before a
manufacturing claim is made.

Six reproducible font specimens can be generated locally with:

```powershell
python scripts\generate_font_examples.py
```

This creates six PNG cards, a manifest, and a visual-review PDF under
`output\font_examples_2026-10-23` and `output\pdf`.

## Full command

```powershell
python scripts/consistem_blender_runner.py `
  --consistem "C:\data\CCCGI650TAB1.xlsx" `
  --reference 13646 --size 18 `
  --builder "C:\path\criador_blender.py" `
  --blender "C:\path\blender.exe" `
  --faca-dir "C:\path\facas" `
  --back-dxf "C:\path\facas\op-40-44.dxf" `
  --output outputs\button_13646_18.blend `
  --render outputs\button_13646_18.png `
  --texture-script "C:\path\textura_blender.py" `
  --front-image "C:\path\C2622 - Frente.png" `
  --verso-image "C:\path\C2622 - Verso.png" `
  --side-image "C:\path\pastilhas_C2622_lado_clean.png" `
  --color-code C2622 --texture-mode PHOTO
```

## Release acceptance checklist

- [ ] Consistem reference and TAM resolve to exactly one row.
- [ ] Front faca DXF exists and the back DXF is explicitly selected.
- [ ] Dimensions and thickness match the row.
- [ ] Hole count, radius, and spacing match the row.
- [ ] Topology has no boundary or non-manifold edges.
- [ ] Texture preflight passes for all required photographs.
- [ ] Four canonical material slots are installed without changing geometry.
- [ ] `.blend`, provenance JSON, and texture report are saved together.
- [ ] Ficha fields and 3D metadata agree before production release.
