# Estrutura do repositório

O código ativo da extensão fica em `src/`. O `__init__.py` da raiz é o ponto de entrada do pacote Blender; o manifesto, a licença, o README e o changelog também permanecem na raiz.

| Pasta | Conteúdo |
|---|---|
| `src/` | Implementação ativa da extensão |
| `tests/` | Suítes de regressão, executor e fixtures |
| `scripts/` | Construção e verificações de desenvolvimento |
| `scripts/audits/` | Auditorias de modelos reais, comparações e experimentos |
| `tools/` | Ferramentas de instalação e captura visual |
| `docs/` | Guias, planos, relatórios e imagens |
| `docs/archive/` | Pacotes, planos e instruções históricos; não são código ativo |
| `evidence/` | Resultados de testes e auditorias; consulte o índice local |
| `evidencias/` | Evidências históricas preservadas no caminho original |
| `dist/` | ZIPs instaláveis gerados; versões antigas em `dist/archive/` |
| `scratch/` | Arquivos temporários locais, ignorados pelo Git |

## Pontos de entrada

- Construir e validar instalador: `python scripts/build.py`.
- Executar regressões: `python tests/run_all_tests.py --report-dir evidence/regressions`.
- Selecionar uma suíte: acrescente `--suite test_release_geometry.py`.
- Auditoria de placas BLEND: `python scripts/audits/audit_plates_blend_20261021.py --help`.
- Auditoria planar/sólido: `python scripts/audits/audit_planar_solid_20261021.py -- --driver`.

Os scripts de auditoria operam sobre modelos privados e alguns ainda contêm caminhos locais. Leia o script antes de executar; os testes Blender devem usar processos separados com cena de fábrica. Suítes `test_*.py` continuam diretamente em `tests/`, preservando a descoberta do executor.

## Auditoria atual

O relatório de 21/10/2026 está em [RELATORIO_PT.md](../evidence/commercial_20261021/RELATORIO_PT.md). O índice [evidence/README.md](../evidence/README.md) distingue resultados finais de baselines e experimentos. Não somar repetições como casos novos.

Os arquivos históricos foram movidos por pasta completa, mantendo seus arquivos internos e links relativos. Referências absolutas e caminhos antigos registrados em logs, JSONs e documentos históricos refletem a execução original. O mapa dos movimentos e a verificação de integridade estão em [REORGANIZACAO_2026-10-21.json](REORGANIZACAO_2026-10-21.json).
