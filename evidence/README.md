# Evidências de validação

## Auditoria de 21/10/2026 — candidata 0.8.18

Comece por [commercial_20261021/RELATORIO_PT.md](commercial_20261021/RELATORIO_PT.md).

| Diretório | Resultados relevantes |
|---|---|
| `commercial_20261021/` | Relatório consolidado, snapshots e regressões |
| `commercial_20261021/final_regressions/` | Regressões repetidas após os ajustes finais |
| `commercial_20261021/package_verification/` | ZIP exato e regressão de conectores Chest |
| `commercial_planar_solid_20261021/final/` | 114 casos de plano/sólido; originais antes/depois |
| `commercial_planar_solid_20261021/final_connectors/` | Repetição final de pinos nos 19 arquivos |
| `commercial_plates_blend_20261021/isolated/` | Varredura BLEND em processos de fábrica |
| `commercial_plates_blend_20261021/isolated/Placa_Chest_Inteira_retry.json` | Chest após as correções de Loop/conectores |
| `commercial_plates_blend_20261021/isolated/connector_solver_probe.json` | Recuperação validada dos conectores Chest |
| `commercial_plates_glb_20261021/` | Nove importações, reparo, Material/Loop e comparações |
| `commercial_plates_glb_20261021/chest_glb_followup.json` | Repetição direcionada Chest após a correção |
| `commercial_cube_20261021/` | Regiões verdes, medições de folga e experimentos Arco |

Baselines, logs e experimentos recusados são mantidos para rastreabilidade. Um processo terminar com código zero não significa que todo corte tentado passou: consultar os estados de cada caso nos JSONs. O defeito Arco/Base permanece aberto.

## Outras campanhas

As pastas de captura de Loop, folgas, reparo, molduras e compatibilidade Blender mantêm seus nomes originais para preservar referências. Cenas `.blend`, backups de instalação, caches e logs locais não integram o instalador da extensão.
