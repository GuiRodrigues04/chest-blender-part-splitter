# Part Splitter 0.8.12

Extensão para dividir modelos em peças para impressão 3D: plano, cortador sólido, contorno de arestas/faces e regiões de material. Mantém pinos cilíndricos/cápsula, posicionamento manual, folgas, prévia montada/explodida, reversão e exportações STL, 3MF e OBJ.

## Instalação

No Blender: Preferences > Get Extensions > menu > Install from Disk. Selecione `chest_part_splitter-0.8.12.zip`. Abra N > Chest > Part Splitter 0.8.12 na Viewport 3D.

O ZIP instalável tem o manifesto na raiz. O pacote `-dev.zip` é para desenvolvimento; não o instale como extensão.

## Uso

1. Selecione a malha e defina o alvo.
2. Escolha o método de corte. No modo Loop, capture um contorno fechado e defina a face da região, ou capture o perímetro das faces selecionadas.
3. Ative os encaixes se necessário. Em Manual, abra o editor, clique para adicionar e arraste os marcadores para mover.
4. Durante a edição manual, pontos a cada 5 mm servem de referência. O movimento é livre, sem snap ou controles adicionais. A grade não altera a malha e é omitida em superfícies não planas.
5. Confirme as posições para gerar a prévia. Confira peças, cavidades e folgas antes de confirmar a divisão ou exportar.
6. Use Remover Prévia para voltar ao alvo e Reverter este corte para desfazer uma divisão confirmada.

Extração com profundidade exige um contorno de apoio plano. Regiões planas usam profundidade; saliências podem ser destacadas pela base ou com base adicional. A validação continua bloqueando resultados vazios, degenerados ou não fechados.

## Verificação desta entrega

Testes automatizados executados com os módulos oficiais `bpy` 4.2.23, 4.5.3 LTS e 5.0.1 em Linux. O manifesto mantém Blender 4.2 como mínimo. Isso não equivale a homologação da interface no Windows nem no Blender 5.2.

O pacote de desenvolvimento inclui testes de regressão e uma malha neutra extraída de `Padrão 1.blend`. Consulte `docs/RELATORIO_0.8.12.md` para resultados, referências e limites. Alguns diagnósticos antigos ainda precisam de revisão de tradução PT/EN. O posicionamento em superfícies não planas precisa de validação visual adicional.

## Desenvolvimento

Com o Blender no PATH, ou informando seu executável:

```bash
python tests/run_all_tests.py --blender /caminho/para/blender
python scripts/build.py --blender /caminho/para/blender
```

O build oficial valida e gera o instalador em `dist/`. Não instala nem altera a pasta de extensões automaticamente. Os utilitários antigos de instalação em `tools/` são específicos do ambiente original e opcionais.

## English

Install the release ZIP with Blender's **Install from Disk**. Open **N > Chest > Part Splitter 0.8.12**. Choose a target and cutting method, configure optional connectors, generate the preview, inspect the result, then commit or export. In Manual mode, place and drag markers; the fixed 5 mm dot grid appears only while editing. It is a visual reference, with no snapping or extra controls. Captured loops survive re-editing a preview. Depth extraction requires a planar support boundary. Automated geometry checks ran against official bpy 4.2.23, 4.5.3 and 5.0.1; Windows viewport interactions and Blender 5.2 still require manual validation.

License: GPL-2.0-or-later. See LICENSE.
