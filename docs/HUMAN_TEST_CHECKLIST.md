# Human-test checklist for the site-to-3D workflow

The items below were not human-tested in a real browser and/or on a machine
with Blender. They are deliberately separate from the automated checks. Mark
each item only after observing the result yourself and record the request ID,
reference, TAM, colour, font filename, and any visible or server-side error.

## Browser and authentication

- [ ] Log in as an administrator and open `automacao.html`.
- [ ] Log in as a normal client and confirm that the Automação page, request
      list, and protected request API follow the intended access policy.
- [ ] Confirm that an anonymous visitor can see only the public catalog area.
- [ ] Repeat the relevant checks on a narrow/mobile viewport and in light and
      dark themes.

## Imported-font interface

- [ ] Choose each of the six specimen fonts once: Arial, Times New Roman,
      Georgia, Trebuchet MS, Courier New, and Bahnschrift.
- [ ] Type text before confirming it and verify that the imported font appears
      immediately in the native-text draft preview.
- [ ] Replace an imported font with another imported font and confirm that the
      draft preview changes without duplicating the artwork layer.
- [ ] Select a valid TTF and a valid OTF under 10 MB.
- [ ] Select a non-font file, a corrupt font, and a font larger than 10 MB;
      confirm that the interface rejects each one with a useful message.
- [ ] Clear the font input and confirm that the request no longer declares an
      imported font.
- [ ] Reload the page before saving and confirm that no stale object URL or
      stale font selection is used.

## PDF and request package

- [ ] Generate a text-only request with an imported font.
- [ ] Generate a mixed text-and-image request with an imported font.
- [ ] Open the PDF and confirm that the actual parsed family name, text, and
      artwork description are correct.
- [ ] Inspect the request manifest and confirm the stored font filename,
      original filename, family, subfamily, byte count, and SHA-256 digest.
- [ ] Confirm that the same font metadata is present in `solicitacao.json`.
- [ ] Test a request that declares an imported font but omits the multipart
      font file and confirm that the server rejects it.
- [ ] Test a request containing only an image and confirm that Blender is not
      incorrectly queued as a native-text render.

## Queue and worker

- [ ] As an administrator, click `Gerar 3D` for a saved text request and
      confirm the status changes to `rendering_3d`.
- [ ] Start the worker with the real `AUTOMACAO_STORAGE_DIR`,
      `AUTOMACAO_BLENDER_EXE`, and `AUTOMACAO_BLENDER_BASE_DIR` values.
- [ ] Confirm that `button_<reference>_<TAM>.blend` is selected for the exact
      reference and size.
- [ ] Confirm that one text layer produces one Blender step and that multiple
      text layers are applied sequentially.
- [ ] Confirm that image layers are not accidentally sent to the text Boolean
      path.
- [ ] Confirm that an uploaded font is loaded by Blender rather than replaced
      by Arial or another system font.
- [ ] Confirm that a missing uploaded font, missing base blend, missing
      executable, timeout, and malformed report become `render_error` with a
      useful history message.
- [ ] Confirm that a stale or concurrent worker lock does not duplicate work.
- [ ] Confirm that a successful request exposes the `.blend`, final PNG, and
      JSON report links in `solicitacoes.html`.
- [ ] Confirm that a different authenticated user cannot download another
      user's Blender files.

## Geometry and visual inspection

- [ ] Inspect the generated `.blend` face-on and from an oblique angle.
- [ ] Confirm that the text is genuinely recessed or raised according to the
      selected effect and is not merely a floating text object.
- [ ] Confirm that the geometry report shows changed vertex/polygon counts for
      Boolean engraving and zero boundary/non-manifold edges.
- [ ] Test front and reverse-face selections, including mirrored orientation,
      rotation, position, scale, flip controls, and positive/negative
      curvature.
- [ ] Test short text, long text, spaces, accents, numbers, punctuation, and
      narrow glyphs such as `I` and `1`.
- [ ] Test the smallest and largest supported TAM values and text close to the
      sewing holes and perimeter.
- [ ] Test both ENGRAVE and RAISE modes with the six fonts.
- [ ] Confirm the 0.20 mm reverse-pastilha recess in the actual model, not only
      in the JSON report.
- [ ] Confirm that the reverse recess exposes the intended other C colour and
      that the result agrees with the physical pastilha construction.
- [ ] Compare the Blender render against the browser preview while remembering
      that the browser preview is illustrative and not a dimensional scan.

## Production acceptance

- [ ] Verify dimensions, thickness, hole count, hole radius, hole spacing, and
      front/back face selection against the correct Consistem record.
- [ ] Verify that the 0.20 mm operation does not violate minimum remaining
      thickness for the particular pastilha.
- [ ] Confirm the final `.blend`, report, PNG, PDF, and request metadata are
      archived together under the intended request ID.
- [ ] Obtain a human manufacturing review before using any generated result as
      a production instruction.
