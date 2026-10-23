# Six-reference engraving verification

Date: 2026-10-21

## Result

All six references passed structural and visual inspection. Each engraving changed the button mesh, retained zero boundary edges and zero non-manifold edges, and remained upright and readable in the face-on Workbench inspection render.

| Reference | TAM | Name | Font | Depth | Rotation in Blender | Vertices before / after | Result |
| --- | ---: | --- | --- | ---: | ---: | ---: | --- |
| 13646 | 18 | LIA | Arial | 0.35 mm | 0 degrees | 15,914 / 28,455 | PASS |
| 13647 | 18 | NOAH | Georgia | 0.30 mm | 0 degrees | 15,906 / 44,523 | PASS |
| 13648 | 18 | EVA | Times New Roman | 0.40 mm | 12 degrees | 15,890 / 30,320 | PASS |
| 13649 | 32 | MIGUEL | Courier New | 0.50 mm | -15 degrees | 16,178 / 99,492 | PASS |
| 13654 | 24 | SOFIA | Trebuchet MS | 0.45 mm | -8 degrees | 16,066 / 61,219 | PASS |
| 13659 | 32 | HELENA | Arial | 0.55 mm | 18 degrees | 16,170 / 117,695 | PASS |

## Verification performed

- Generated three new base buttons from their registered Consistem rows and DXF profiles: references 13648, 13654, and 13659.
- Reused the previously verified base buttons for references 13646, 13647, and 13649.
- Generated each engraving from a schema-5 Automacao Fichas request fixture.
- Verified that Blender changed the body vertex count for every case.
- Verified zero boundary and non-manifold edges for every finished mesh.
- Rendered the selected engraved face with the regular preview camera.
- Rendered a neutral orthographic Workbench inspection image with cavity shading.
- Visually inspected all six cases for reading order, orientation, position, clipping, and collision with sewing holes.

The batch exposed and corrected a preview-camera defect: the old product camera always stood on world -Y and therefore photographed the opposite face for Automacao's front-face engravings. The camera and lights now derive their orientation from the selected surface basis.

## Artifacts

- `personalized/engraving_matrix_contact_sheet.png`: labelled visual comparison.
- `personalized/summary.json`: machine-readable geometry and artifact report.
- `personalized/ref_*.blend`: six finished Blender files.
- `personalized/ref_*.png`: corrected product renders.
- `personalized/ref_*_inspection.png`: neutral face-on inspection renders.
- `bases/`: newly generated Consistem base buttons and provenance for references 13648, 13654, and 13659.

## Remaining limitation

This matrix validates straight text. Nonzero text curvature is still deliberately rejected until curved text can be converted into dependable manufacturing geometry.
