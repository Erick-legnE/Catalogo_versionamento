# Size-preserving curved engraving correction

Date: 2026-10-21

## Defect found

The first curved-text implementation deformed every vertical slice of the text mesh and compressed the outer slices. This altered individual letter proportions and expanded the text's vertical envelope. The nominal Ficha width and height were unchanged, but the visible glyph geometry was not.

## Correction

The browser preview and Blender generator now use rigid per-character curve placement:

1. The original text is scaled to the requested Ficha footprint.
2. Blender converts the text to a mesh and identifies its connected components.
3. Components are consolidated into the expected number of non-space characters.
4. Each character receives one vertical offset and one tangent rotation along the curve.
5. No character receives local scaling, compression, or per-vertex warping.

A rigid rotation and translation preserve all distances inside a character. The generated reports calculate the maximum change in distance from every vertex to its character pivot.

## Verified cases

| Reference | TAM | Name | Character groups | Maximum radius error | Boundary / non-manifold | Result |
| --- | ---: | --- | ---: | ---: | --- | --- |
| 13646 | 18 | LUNA | 4 | 0.000000102 | 0 / 0 | PASS |
| 13654 | 24 | ARTHUR | 6 | 0.000000235 | 0 / 0 | PASS |
| 13659 | 32 | ISABELA | 7 | 0.000000118 | 0 / 0 | PASS |

The errors are floating-point rounding and are far below any visible or manufacturing-relevant dimension.

## Preserved comparison

- `../curved-engraving-2026-10-21/` contains the original slice-deformed results.
- `personalized/` contains the corrected rigid-glyph results.
- `personalized/engraving_matrix_contact_sheet.png` is the corrected visual comparison.
- `personalized/summary.json` records topology, grouping, and size-preservation checks.
