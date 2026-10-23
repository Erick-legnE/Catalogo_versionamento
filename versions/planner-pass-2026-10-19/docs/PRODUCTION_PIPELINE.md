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
