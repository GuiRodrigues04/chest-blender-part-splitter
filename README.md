# Part Splitter 0.8.13

Extensão para dividir modelos em peças para impressão 3D por Plano, Material, Loop ou Sólido. Inclui pinos cilíndricos/cápsula, distribuições automáticas e manuais, folgas, prévia montada/explodida, reversão e exportações STL, 3MF e OBJ.

## Instalação

No Blender: Preferences > Get Extensions > menu > Install from Disk. Selecione `dist/chest_part_splitter-0.8.13.zip`. Abra N > Chest > Part Splitter 0.8.13 na Viewport 3D. O ZIP instalável contém o manifesto na raiz; o pacote externo para Antigravity não é instalável.

## Uso

1. Selecione a malha e defina o alvo.
2. Escolha o corte. Em Loop, capture um contorno fechado ou o perímetro das faces selecionadas e defina a região.
3. Ative os encaixes se necessário. Em Manual, abra o editor, clique para adicionar e arraste os marcadores. R gira cápsulas; X/Delete remove.
4. A grade de 5 mm é uma referência visual durante a edição, sem snap. Uma superfície não plana não recebe uma grade plana fictícia.
5. Confirme as posições e gere a prévia. Inspecione peças, cavidades e folgas antes de confirmar a divisão ou exportar.
6. Remover Prévia volta ao alvo; Reverter este corte desfaz uma divisão confirmada.

Em Loop e Material, a extração com profundidade constrói uma base de apoio abaixo do contorno projetável e acrescenta profundidade abaixo dele. Saliências continuam podendo ser destacadas pela base. A extensão bloqueia resultados vazios, degenerados ou não fechados.

O modo Sólido recebe folga física, encaixes sobre uma face de contato e alinhamento por dois vértices. Veja [docs/USO_SOLIDO.md](docs/USO_SOLIDO.md). As faces do cortador precisam oferecer área suficiente para os pinos.

## Verificação

49 testes em cada runtime oficial bpy 4.2.23, 4.5.3 e 5.0.1: 147 execuções aprovadas. O manifesto mantém Blender 4.2 como mínimo. Isso não equivale a homologação da interface no Windows nem no Blender 5.2. As peças .blend originais dos últimos relatos não estavam disponíveis. Veja [docs/RELATORIO_0.8.13.md](docs/RELATORIO_0.8.13.md) e [docs/CASOS_REPORTADOS.md](docs/CASOS_REPORTADOS.md).

## Desenvolvimento

Em um Python com o módulo oficial bpy instalado:

```bash
python tests/test_regressions.py
python scripts/build_installer.py
python tests/smoke_installer.py
```

Com um executável Blender:

```bash
blender --background --factory-startup --python tests/test_regressions.py -- /caminho/absoluto/do/repositorio
```

Os testes criam e removem objetos: execute em um processo separado com cena de fábrica. Não execute a suíte sobre uma cena de trabalho. Os scripts desta entrega não instalam a extensão automaticamente nem alteram a pasta local de extensões.

## English

Install `dist/chest_part_splitter-0.8.13.zip` using Blender's Install from Disk. Choose a target and cutting method, configure connectors, generate and inspect the preview, then commit or export. In Manual mode, click to place and drag markers; R rotates a capsule. The fixed 5 mm dot grid is a visual reference, without snapping. Solid mode supports physical clearance, pins on a selected planar contact face, and two-click vertex alignment. Depth extraction uses a support plane beneath the projected boundary. Complex self-overlapping projections and offsets collapsing small details may be rejected. Automated tests passed in official bpy 4.2.23, 4.5.3 and 5.0.1. Windows viewport interactions, the original reported meshes, and Blender 5.2 still require manual validation.

License: GPL-2.0-or-later. See LICENSE.
