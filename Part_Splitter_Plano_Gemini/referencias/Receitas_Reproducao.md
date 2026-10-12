# Fixtures e reprodução no Blender

Criar em processo separado e salvar .blend por caso. Não substituir a cena real por aproximação sem registrar isso.

| Fixture | Construção | Variáveis | O que isola |
|---|---|---|---|
| F01 — Plano | Cubo 100 mm; plano Z=20 mm; adicionar relevo sólido no topo se necessário. | Normal ±Z, invert_sides, explosão 0/39,3/0. | Convenção dos lados e snapshot da prévia. |
| F02 — Patch plano | Cubo 100 mm subdividido; pintar retângulo de faces no topo. | Profundidade 10/20, materiais branco/amarelo, folga zero. | Prisma simples e materiais externos/interface. |
| F03 — Região côncava | Igual F02, pintar faces formando U, com área não pintada no centro. | Tesselação, pontos colineares, profundidade. | Não preencher concavidades com hull/n-gon. |
| F04 — Patch dobrado | Extrudar faces centrais do cubo em 20 mm; pintar topo e laterais da saliência. | Pintar também uma faixa plana ao redor; direção quase tangente. | Extrusão por vetor único, seleção mista e tampas. |
| F05 — Loop planar | Na saliência, selecionar perímetro exato da ligação com o corpo e seed na saliência. | Subdividir borda; inverter ordem de captura. | Interface compartilhada e incidência do perímetro. |
| F06 — Loop não planar | Duplicar F05; deslocar vértices alternados da borda em Z preservando a malha fechada. | Desvio pequeno e grande; documentar desvio medido. | Capacidade do fechamento, não reproduce 19 vértices automaticamente. |
| F07 — Cunha | Criar relevo inclinado com extremidade que afina; loop num plano que intersecta a inclinação. | DETACH e EXTRUDE; seção e limite de espessura escolhido. | Cunha fiel versus filme inválido. |
| F08 — Abertura antiga | Duplicar F05 e remover uma face distante do contorno. | Entrada inválida conhecida. | Não preencher aberturas alheias ao corte. |
| F09 — Componente isolado | Dois cubos fechados no mesmo objeto, cada componente com um material. | Um componente com abertura, escala refletida. | Separação direta e validação de ambos. |

Cada fixture deve ter: entrada sem preview, instruções de seleção, configuração serializada, saída montada A/B, screenshot, log e resultado de validação. Seleções por índices só são válidas no mesmo snapshot.

Para casos reais, salvar INV002_13faces.blend, INV003_10mm_positivo.blend, INV005_19vertices.blend e INV006_32vertices.blend quando as cenas estiverem disponíveis. Esses arquivos NÃO existem neste pacote.

## Uso do diagnóstico

Abra a cena, selecione os objetos alvo/resultado e execute scripts/diagnosticar_selecao_blender.py no Text Editor. O arquivo part_splitter_diagnostico.json sai ao lado do .blend, ou no temporário se a cena não estiver salva. Copie/renomeie após cada estágio para não substituir o relatório anterior.

O script não modifica a cena. Com Edit Mode, a leitura avaliada pode não refletir alterações ainda não sincronizadas; o JSON indica esse contexto. Compare também em Object Mode na cópia de teste.

As contagens de área abaixo de 1e-8 mm² são detector numérico de degeneração, não limiar de impressão. Duplicatas são detectadas somente por IDs dos vértices. Não há teste de espessura, auto-interseção ou cobertura nesse auxiliar; esses controles precisam de implementação própria ou ferramenta externa validada.

## Execução dos testes históricos

Adaptar imports/registro no checkout correto. Exemplo após copiar o teste para tests/ ao lado de src:

```text
blender --background --factory-startup --python tests/test_material_regions.py
```

Não executar testes que chamam read_homefile na sessão de trabalho do usuário. Não registrar PASSOU quando só houve verificação de sintaxe.
