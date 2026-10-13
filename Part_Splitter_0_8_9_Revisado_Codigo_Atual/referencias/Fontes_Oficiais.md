# Referências oficiais

Consultadas por busca em 12/10/2026. A abertura integral de algumas páginas foi bloqueada pelo serviço; os links abaixo são para consulta direta no Antigravity. A análise principal é baseada no código local e nos anexos, não em trechos de busca como substituto de implementação.

| Fonte | Uso no plano |
|---|---|
| [Blender — Application Translations](https://docs.blender.org/api/current/bpy.app.translations.html) | Catálogo, contexto, locale e tradução de templates. |
| [API4.2 — Application Translations](https://docs.blender.org/api/4.2/bpy.app.translations.html) | Conferir comportamento na versão mínima. |
| [Blender — UILayout](https://docs.blender.org/api/current/bpy.types.UILayout.html) | Labels/props, contextos e controle translate. |
| [Blender — BMesh Types](https://docs.blender.org/api/current/bmesh.types.html) | Faces, calc_area, incidência, índices e vida útil. |
| [Blender — BMesh Operators](https://docs.blender.org/api/current/bmesh.ops.html) | Triangulação, preenchimento, bisect e operações locais. |
| [Blender — BMesh API](https://docs.blender.org/api/current/bmesh.html) | Mesh de edição, ownership e atualização. |
| [Blender — Boolean Modifier](https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/booleans.html) | Operações, solver e comportamento de materiais. |
| [API — BooleanModifier](https://docs.blender.org/api/current/bpy.types.BooleanModifier.html) | Propriedades disponíveis e material_mode. |
| [API — Object](https://docs.blender.org/api/current/bpy.types.Object.html) | matrix_world, dimensions, mesh avaliada e cópia. |
| [API — ID](https://docs.blender.org/api/current/bpy.types.ID.html) | Independência/usuários de datablocks copiados. |
| [API — BVHTree](https://docs.blender.org/api/current/mathutils.bvhtree.html) | Raios/overlap e limitações de diagnósticos. |
| [API — Mathutils](https://docs.blender.org/api/current/mathutils.html) | Bases, matrizes e vetores para alinhamento. |
| [Blender — Transform Orientation](https://docs.blender.org/manual/en/latest/editors/3dview/controls/orientation.html) | Coerência de eixos locais e globais para o usuário. |
| [Blender — Extension Manifest](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html) | Empacotamento e versões mínimas declaradas. |

Antes de usar APIs current/latest, conferir mesmas propriedades no Blender mínimo anunciado e no5.2 das cenas. Não usar biblioteca externa instalada no ambiente de desenvolvimento como dependência implícita do cliente.

## Dependências geométricas

O projeto existente usa bpy/bmesh/mathutils. Reutilizar o que já é validado. Se offset poligonal exigir nova biblioteca, registrar licença, compatibilidade com Python/OS do Blender, empacotamento e teste offline. Não instalar pip automaticamente na máquina do usuário.

Não inventar uma implementação curta de offset geral para atender formas arbitrárias sem testes de furos/concavidades/interseções. Para caixa e interfaces simples, métodos geométricos restritos podem ser implementados diretamente; para a faixa côncava do INV-008, suporte e testes reais continuam obrigatórios.
