# GLB plate import and cut audit (Blender 5.2)

Run date: 2026-10-21. The audit imported all nine delivered GLBs into empty factory scenes. It measured the default import, Blender's `merge_vertices=True` option, and the extension's validated safe-repair operator. Cut previews used transient in-memory copies. The source GLB and paired BLEND files were never saved or modified.

## Import and repair

| GLB | Raw open edges | `merge_vertices=True` open edges | Safe repair open edges | Slots |
|---|---:|---:|---:|---:|
| Arco | 3236 | 3236 | 0 | 2 |
| Cavalete | 362 | 244 | 0 | 2 |
| Chest | 1994 | 1372 | 0 | 3 |
| Mesa | 400 | 322 | 0 | 2 |
| Número | 2384 | 2384 | 0 | 1 |
| Osso | 14230 | 14230 | 0 | 2 |
| Osso V2 | 13598 | 13598 | 0 | 2 |
| QR Inclinada | 4218 | 4102 | 0 | 2 |
| QR Inclinada V2 | 1750 | 1750 | 0 | 1 |

The extension repair closed and validated all nine imports as a separate mesh datablock, with one connected component and unchanged dimensions and volume. The Blender importer option left open edges on all nine models.

## MATERIAL and LOOP cuts

The final run covered 46 cases across the nine imports: 32 MATERIAL and 14 LOOP. It produced 21 previews with two valid closed positive-volume solids (12 MATERIAL, 9 LOOP). Those previews were committed and reverted, and the imported repaired source mesh signature was unchanged. For every requested 0.1 mm clearance case, the effective clearance recorded in the scene matched 0.1 mm; no preset reset remained in the harness. The Osso and Osso V2 material cuts show the expected volume reduction from the gap: 5281 to 4814 mm³ and 5192 to 4732 mm³ respectively, while both parts remain closed.

After the final prism-sanitization and Boolean-retry change, I reran the affected Chest GLB at the exact 2 mm depth. All three cases passed both direct material geometry and the preview/commit/revert operators: material 0 region 0 at 0 mm gap; material 0 region 0 at 0.1 mm gap applied to the extracted part; and material 1 region 0 at 0.1 mm gap applied to the extracted part. Every preview contains two valid closed solids, the measured gap matches the request, and the repaired source signature remains unchanged. Extracted-part volumes were 6232.135, 5866.006, and 5866.512 mm³; mate volumes were 212101.527, 212101.527, and 212100.987 mm³. See [chest_glb_followup.json](chest_glb_followup.json).

Edit Mode face-boundary capture selected actual material regions. Thirteen captures were recorded; the run also deliberately changed from LOOP back to MATERIAL with the capture still active. The baseline run reproduced the stale Loop seed bug on Arco: MATERIAL after LOOP failed with “selected face does not belong to captured contour.” The integrated fix removed that stale-seed failure; the equivalent material cases now either produce valid solids or return geometry-specific rejections. Other rejected regions reported a depth overhang, empty extraction, uncertain local thickness, a collapsed/degenerate prism, a non-closing loop, zero-volume output, or a clearance that crosses small openings. These are geometry/configuration constraints of the attempted region/depth, not the stale-mode failure.

Número and QR V2 have one genuinely uniform green material in both GLB and matching BLEND files. Neither file has color attributes, UV layers, image textures, or a second material; both have the same Principled Base Color and diffuse color. Dimensions also match within 0.01 mm. Their all-faces material selection is correctly rejected as “all faces already use this material.” Details are in [single_material_counterparts.json](single_material_counterparts.json).

The focused QR test applies safe repair to both the QR GLB and paired BLEND, selects material region 0, then checks depth 0.1 mm with zero gap and depth 5 mm with 0.1 mm gap. Both sources produce two closed solids at 0.1 mm depth with no gap, and both reject the 0.1 mm FDM clearance because it crosses/collapses the same real small openings. Source signatures remain unchanged. See [qr_fdm_glb_vs_blend.json](qr_fdm_glb_vs_blend.json).

## Review files and reproduction

The `.blend` review files contain actual successful previews and both closed parts:

- `Placa_Arco_Chest_Inteira_MATERIAL_preview.blend`
- `Placa_Arco_Chest_Inteira_LOOP_preview.blend`
- `Placa_Mesa_Chest_Inteira_MATERIAL_preview.blend`
- `Placa_Osso_Chest_V2_Inteira_MATERIAL_preview.blend`
- `Placa_Osso_Chest_V2_Inteira_LOOP_preview.blend`

Full per-file JSON and the run summary are alongside this document. The initial pre-fix measurements are preserved in `baseline_before_integrated_fixes/`.

Reproduction scripts:

- `scripts/audits/audit_plates_glb_20261021.py`
- `scripts/audits/audit_chest_glb_followup_20261021.py`
- `scripts/audits/compare_plate_glb_blend_20261021.py`
- `scripts/audits/compare_qr_glb_fdm_20261021.py`
- `scripts/audits/save_plate_glb_review_previews_20261021.py`
