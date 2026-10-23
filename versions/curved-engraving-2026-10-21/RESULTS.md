# Curved engraving verification

Date: 2026-10-21

## Result

True curved engraving passed on three distinct button references. The Blender text mesh uses the same normalized parabolic deformation and edge compression as the Automacao Fichas preview before becoming the Boolean cutter.

| Reference | TAM | Name | Font | Curvature | Depth | Rotation in Blender | Vertices before / after | Result |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | --- |
| 13646 | 18 | LUNA | Arial | +0.70 | 0.35 mm | 0 degrees | 15,914 / 35,957 | PASS |
| 13654 | 24 | ARTHUR | Georgia | -0.65 | 0.45 mm | +10 degrees | 16,066 / 79,844 | PASS |
| 13659 | 32 | ISABELA | Trebuchet MS | +0.90 | 0.55 mm | -14 degrees | 16,170 / 143,545 | PASS |

## Structural verification

Every finished button has zero boundary edges and zero non-manifold edges. Each body vertex count changed substantially, proving that the curved lettering was subtracted from the button rather than left as a separate object above it.

The reports also record nonzero local Y displacement ranges for the actual cutter meshes:

- LUNA: -0.479646 to +0.243817 local units.
- ARTHUR: -0.239155 to +0.592296 local units.
- ISABELA: -0.682022 to +0.348197 local units.

## Visual verification

- LUNA demonstrates positive curvature on a compact TAM 18 button.
- ARTHUR demonstrates the opposite curvature direction on TAM 24.
- ISABELA demonstrates strong positive curvature, a longer name, and additional rotation on TAM 32.
- All names are upright, readable, within the usable face, and clear of the sewing holes.

## Artifacts

- `personalized/engraving_matrix_contact_sheet.png`: labelled three-case comparison.
- `personalized/summary.json`: machine-readable structural results.
- `personalized/ref_*.blend`: finished curved engraving meshes.
- `personalized/ref_*_inspection.png`: neutral face-on Workbench inspections.
- `personalized/ref_*.json`: complete Blender reports including curvature diagnostics.
