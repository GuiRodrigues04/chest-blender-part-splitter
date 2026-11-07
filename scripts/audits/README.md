# Auditorias e experimentos

Estes scripts verificam modelos reais e complementam as regressões em `tests/`. Não são executados automaticamente por `tests/run_all_tests.py`.

- `audit_plates_blend_20261021.py`: cortes por material/Loop em placas BLEND, com workers isolados.
- `audit_plates_glb_20261021.py`: importação, reparo e cortes GLB.
- `audit_planar_solid_20261021.py`: plano/sólido, folga e pinos nos modelos; suporta `SPLITTER_AUDIT_OUTPUT` e `SPLITTER_AUDIT_CASE`.
- `audit_cube_20261021.py` e `audit_green_followup_20261021.py`: regiões verdes, medidas e configurações com saliências.
- `audit_chest_glb_followup_20261021.py`: repetição direcionada Chest.
- `compare_*.py`: comparação entre fontes BLEND e GLB.
- `audit_base_open_edge_20261021.py`, `experiment_arco_base_intersect_20261021.py` e `probe_chest_connector_solver_20261021.py`: diagnóstico reproduzível; alguns experimentos instrumentam validações apenas no processo de teste e não devem ser usados como ferramentas de produção.
- `save_plate_glb_review_previews_20261021.py`: gera cópias de revisão.

Alguns scripts exigem os arquivos privados e caminhos locais registrados no código. Executar os workers dentro do Blender com `--background --factory-startup --python-exit-code 1 --python caminho_do_script`. Não executar sobre a cena de trabalho do usuário. As saídas ficam em `evidence/`.
