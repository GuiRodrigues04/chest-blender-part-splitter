# 0.9.11 Spot contact audit

## Source

The measured artifact is `Spot 2 pos cortesw.blend` (SHA-256 `BD06433C6A2271BC6016801CAF48D8048798F57AFC73134D88B5D3A9D88D3EBB`). Its committed objects are `Eye.001` (part A) and `Spot` (part B). `Spot.blend` (SHA-256 `85663C84D63EB28767581D8FE879908A4E34893847481E6D72D3CEFFB236624D`) was also supplied and hash-checked. Assembly transforms were used for both meshes; saved scene units give 100 mm per BU.

## Method

The JSON records distances from each contact-surface triangle's centroid and three strictly interior barycentric points (weights 0.6/0.2/0.2) to every marked contact triangle on the other part. Point-to-triangle closest points are computed with scalar double-precision geometry. Contact faces are categorized by their normal against the saved assembly axis. An `all four` contact requires every interior sample to be within 0.005 mm and every corresponding closest face to have opposed normals. This is a surface proximity measurement, not a solid intersection test; it covers only faces marked `splitter_contact_surface`.

## Finding

For `Eye.001` to `Spot`, the side-wall category has 144 triangulated faces meeting the four-interior-sample contact criterion, totaling 4.9214 mm², across axial coordinates -71.7654 to -71.6314 mm. Their corresponding closest faces are also side walls with opposed normals. In the reverse direction, `Spot` to `Eye.001`, side-wall distance median is 0.100000 mm and the 99th percentile is 0.100003 mm, with no zero-contact side-wall faces. This confirms a finite zero-clearance patch on the Eye.001 generated interface; it does not establish the whole eye profile's clearance against unmarked mesh.

The adjacent clearance regression removes the support-plane clipping from the generated band and constrains both boundary rings just beyond adjacent retained faces. It checks 0.1 mm at four walls below and above the prior support plane. The analytic fixture's removed volume is 43.980 mm³: 42.388 mm³ from the lower core plus 1.592 mm³ from the full relief-side strip (0.1 × 16 mm² minus 0.008 mm³ of corner overlap).

## Reconstructed contact after the full-band change

`reconstructed_5mm_gap_0.1.json` measures a fresh reconstruction from the supplied `Spot.blend` source and the saved output's unmarked faces. The cut boundary and 10-face region were inferred from provenance because the original operation settings were unavailable. The reconstructed base cut uses 5 mm and requests 0.1 mm PART clearance. On marked side walls, bidirectional point-to-triangle samples range from 0.0999968 to 0.101373 mm; neither direction has sustained zero-contact triangles. This verifies the inferred reconstruction only. It does not replace the saved scene's committed parts, reproduce its missing settings, prove clearance against unmarked geometry, or validate physical printing. Reopen the add-on and regenerate the preview before confirming a new cut.

## Explicit pin measurement

The reconstructed scene also tested one manually dimensioned CYLINDER pin on Part A (2 mm diameter × 2 mm insertion depth, 0.2 mm chamfer, 0.1 mm radial and end clearance). Across 64 marked cavity-wall triangles and 256 interior samples, measured radial clearance ranges from 0.099514 to 0.099521 mm (median 0.099518 mm), with zero opposed zero-contact samples. A separate outer-wall check reported a 0.1 mm median and zero zero-contact samples. The automatic sizer correctly rejected this case as lacking a safe 1 × 2 mm suggestion; these measurements use explicit test dimensions and do not establish an automatic suggestion or preserve unavailable historical operation settings.
