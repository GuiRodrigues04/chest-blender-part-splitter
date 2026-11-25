# Spot and real-model clearance validation

## Scope and provenance

Blender 5.2 background runs against the 0.9.15 source after the tapered-rim validation change. No source `.blend` files were saved. The older initial eye output used a different 26-vertex captured cut and is not the Spot 53-vertex target; the relevant eye matrix is `base_eye_results.json` from a reconstruction using the saved Spot output provenance (53 boundary vertices, seed face 2236, inferred 5 mm detach base). The historical saved operation/settings were unavailable, so this remains a reconstruction.

## Results

- **Reconstructed Spot eye, no connectors:** requested 0, 0.1, 0.2, and 0.5 mm cuts succeeded with valid manifold parts. At 1 mm, the inferred 5 mm detach-base cut returns `geometry.clearance_unresolved`. Reducing the detach base to 2 mm also returns that error. A direct non-detached 1 mm cut returns `geometry.clearance_excessive`, protecting the removed-volume limit. These are observed limits of these configurations; they do not prove 1 mm is impossible with another cut setup.
- **Eye, 0.1 mm connector scenario:** the reconstructed run created its pin and measured the cylindrical sidewall at 0.099514–0.099521 mm, with no zero-clearance samples. The lengthy follow-up all-mesh overlap audit was stopped before it wrote a final JSON, so this is partial pin evidence rather than a fully audited completion.
- **Horn, no connectors:** 0.1, 0.2, 0.5, and 1 mm succeeded after the validation fix. The 1 mm test confirms requested interior closest distances and normal distances within tolerance, records waived exterior ray misses only where the expected moved endpoint is outside the original solid, and verifies manifold parts. Regression: `test_real_spot_horn_clearance.py`.
- **Horn, connectors:** the fixed Ø1 × 8 mm pin preview passed at 0.1, 0.2, 0.5, and 1 mm with connectors explicitly enabled. Automatic suggested connector previews pass at 0.1 mm for either male side (A: Ø9.5 × 2.75 mm, B: Ø9.5 × 3 mm).
- **Paw, connectors:** 0.1, 0.2, 0.5, and 1 mm passed with pin on A and B. At 1 mm, sampled contact clearance was 0.985–1.035 mm (rim-inclusive 0.985–1.056 mm).
- **Plate and cat controls:** the standard real-model driver passed four plate cases (`plate_region_green`, `plate_region_blue`, loop detach, loop whole) and `cat_material_slot4_paw`. The source meshes remained unchanged and outputs were single-component/manifold.

## Regression status

The broad post-fix battery completed **20/20 suites, 137 checks, with 2 skips**, including `test_release_workflows`, `test_release_package`, and the horn regression. A final call-site wiring change connected the original source mesh and clearance destination to the natural-cut measurement path while that battery was running. The affected suite subset then passed **9/9** against the frozen final source; the detailed runner log was retained locally. The coordinating agent rebuilt the package after that wiring change and checked package correspondence.

Pre-existing dirty files under `evidence/0.9.11` were not modified by this work.



The earlier eye matrix used the historical failure-scene 26-vertex loop, not the reconstructed 53-vertex base eye. Its positive-gap median measurements were 0.100003 mm (.1 requested), 0.200004 mm (.2), 0.500018 mm (.5), and 1.000002 mm (1.0). Keep those results distinct from the 53-vertex reconstruction, which has no measured gap summary for the detached-base path.

Detailed reproduction scripts, raw JSON and logs are retained locally in the temporary spot_clearance_matrix_20261125 directory. The public summary contains no personal paths or original model files. The older directory name reflects the version under initial validation.
