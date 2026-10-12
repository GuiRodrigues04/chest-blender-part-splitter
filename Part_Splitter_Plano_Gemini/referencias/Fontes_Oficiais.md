# Referências externas e uso

Consulta feita em 12/10/2026. A busca retornou documentação oficial, mas a abertura integral das páginas foi bloqueada pelo serviço de consulta. Usar os links para verificar assinaturas e comportamento na versão Blender instalada; não tratar versões latest/current como contrato fixo de 4.2.

1. [BMesh Operators](https://docs.blender.org/api/current/bmesh.ops.html): bisect_plane, holes_fill, edgenet_fill e triangulate. Retornos de operadores não demonstram sozinhos cobertura ou imprimibilidade.
2. [Boolean Modifier — Manual](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/booleans.html): seção Materials / Exact Solver; relevante para rastrear slots e faces geradas.
3. [API 4.2 — BMesh Operators](https://docs.blender.org/api/4.2/bmesh.ops.html): confirmar parâmetros na versão mínima declarada pelo manifesto.
4. [API 4.2 — BMesh Types](https://docs.blender.org/api/4.2/bmesh.types.html): BMFaceSeq.new, incidência e operações sobre BMesh.
5. [API 4.2 — BooleanModifier](https://docs.blender.org/api/4.2/bpy.types.BooleanModifier.html): verificar material_mode e solver disponíveis por RNA antes de atribuir propriedades.
6. [API — BVHTree](https://docs.blender.org/api/current/mathutils.bvhtree.html): ray_cast/overlap. Um raio isolado não prova espessura mínima global.

O diagnóstico de sinal do Plano vem do código local verificado, não de conjectura sobre normais mostradas nas imagens. As capturas e o registro anterior são fontes do comportamento relatado; o código anexado é a fonte da análise estática.
