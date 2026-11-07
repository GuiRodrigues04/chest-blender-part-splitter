# Ferramentas novas — contratos exatos para 0.8.9

## SOL-01 — Criar, focar e reiniciar são operações diferentes

Na base atual 0.8.9, ensure_solid_cutter recria a malha e reposiciona ao centro mesmo se o objeto existe; Criar/Focar chama essa função. Separar:

- Criar cortador: cria somente quando não existe; se existe, seleciona e orienta para Focar/Reiniciar.
- Focar/Selecionar: somente seleção/enquadramento; nenhuma alteração de malha, dimensões, posição, rotação ou parent.
- Reiniciar formato: ação explícita, com undo, gera nova malha no cortador pertencente à sessão. Não alterar objeto externo usado como cortador.
- Trocar tipo: definir se preserva dimensões e transformações; padrão preservar dimensões físicas e pose quando possível, mostrando limitações.

Separar factory(create) de resolver/get e focus(context). Não esconder recriação dentro de função ensure chamada em UI, depsgraph ou atualização de preview.

Aceite: ajustar cortador, focar repetidamente, atualizar painel/preview e reabrir cena: mesh e matrizes idênticos.

## SOL-02 — Alinhamento previsível

Comandos mínimos:

1. Alinhar à face ativa: origem no ponto de referência da face; um eixo local explicitamente rotulado como Profundidade acompanha sua normal mundial.
2. Alinhar aos eixos do alvo: usar orientação ortonormal do alvo, sem herdar escala não uniforme como fator físico do cortador.
3. Alinhar ao cursor3D: pose do cursor, com opção posição somente ou posição+orientação.
4. Eixos globais X/Y/Z: normal de profundidade e rotação em torno dela explícitas.
5. Ajustar posição à seleção: centro/âncora da seleção, sem inferir automaticamente volume do recorte.

Preservar tamanho ao alinhar. Normais com inversa-transposta ou geometria já transformada; usar mesmo espaço das posições. Matriz singular deve recusar; reflexão tratada explicitamente.

Construir base ortonormal determinística: normal validada, eixo tangente de aresta de referência ou projeção de eixo do alvo; fallback quando quase paralelo. Evitar giro180° inesperado em faces vizinhas. Não substituir usuário por câmera como convenção principal.

Para alinhar pela face, âncora do cortador pode ser Centro ou Face de apoio. Com Face de apoio, essa face toca o plano selecionado; profundidade positiva entra no alvo. Botão Inverter direção altera o cortador proposto e invalida preview, diferente da inversão só visual da explosão.

Aceite: face inclinada, objeto rotacionado/escalado/refletido, cursor e origem distante: contato/pose corretos sem mudança de dimensões.

## SOL-03 — Dimensões e deslocamentos físicos

Mostrar largura, altura e profundidade em mm na base local ortonormal do cortador, não misturar com bounding box global que muda ao girar.

Deslocamentos em eixos locais, rotação em torno da profundidade e face de apoio. Native gizmos/G/R continuam úteis; painel acompanha suas mudanças sem reconstituir a malha.

Fonte única de geometria/transformação: escolher malha canônica + transformação ou rebuild explícito para edição dimensional; nunca aplicar novo tamanho em callbacks que disparam entre si e acumulam escala.

scale_length altera conversão física: dimensions_mm=BU×scale_to_mm. Sem alvo, default50 mm equivale50/scale_to_mm BU, não50 BU. Auditar default do código atual.

Aceite: girar cortador preserva dimensões locais; editar largura não altera altura/profundidade; repetir ajustes sem drift; callbacks têm proteção contra recursão.

## SOL-04 — Duplicar e copiar como cortador

- Duplicar cortador: objeto e mesh independentes, mesma matriz mundial inicial e parâmetros aplicáveis; selecionar cópia como novo cortador de sessão.
- Copiar selecionado como cortador: não editar/ocultar/reparentear fonte; criar objeto e mesh próprios na coleção de guias, com proveniência.
- Se fonte tem modificadores, oferecer copiar malha base ou malha avaliada; explicar diferença e copiar materiais quando necessário. Liberação de to_mesh obrigatória.
- Usar selecionado como cortador continua disponível como referência externa: ajustes só por ação do usuário, limpeza da sessão nunca apaga esse objeto.
- Garantir propriedades/IDs de sessão próprios; não herdar role de peça final/backup incorretamente.

Aceite: mover/editar cópia não altera fonte; removê-la não elimina objeto do usuário; exportação não inclui guias.

## SOL-05 — Prisma de Material/Loop planar

Comando Criar cortador desta seleção aceita:

- Loop capturado válido e planar.
- Região de material que é patch planar com contorno(s) suportado(s).

Pré-validar conectividade, vazio/furos, concavidade, segmentos e planicidade em mm. Loop planar não determina qual lado/extrusão o usuário deseja; mostrar Profundidade, Direção e extensão para fora como parâmetros.

Prisma preserve domínio exato, incluindo vazios quando suportados. Tampas trianguladas com contorno restrito; triângulos internos não invadem concavidades. Não convex hull. Extensão exterior pequena em mm evita coplanaridade, mas não deve englobar outra área externa: verificar visual e geometricamente.

Gerar objeto cortador editável primeiro; não executar o corte simultaneamente. O usuário vê volume de interseção, pode ajustar e depois gerar preview. Transferir seleção/material como proveniência, não definir cor final automaticamente por todo cortador.

Seleção não planar: oferecer alinhar/propor primitiva com base nela; não chamar extrusão arbitrária de prisma validado. Base com furos não suportados: explicar, nunca fechar buraco silenciosamente.

Aceite: retângulo, U/C, contorno com buraco suportado, segmentos colineares e valores pequenos/grandes; malha fechada e exterior selecionado respeitado.

## SOL-06 — Caixa para quina regular

Identificar pequeno conjunto de planos dominantes aproximadamente ortogonais e região regular. Estimar orientação com geometria de mundo; não assumir eixos globais do cubo.

Propor caixa delimitada pelos planos/contorno, mostrar volume retirado e campos de dimensão/profundidade internos. Validar interseção com exterior:

- Faces pintadas pretendidas incluídas.
- Faces externas não selecionadas não invadidas, salvo ajuste explícito mostrado.
- Superfícies livres externas preservadas.

Três patches quadrados compatíveis podem sugerir bloco. Patch irregular/côncavo não recebe bounding box indiscriminado: requer edição manual ou diagnóstico.

Uma capa de20 mm, extrusão diagonal20 mm e bloco interno são resultados diferentes. A proposta não deve ocultar essa mudança no volume retirado.

Caixa editável permite evitar abas triangulares internas; não garante automaticamente montagem. Indicar direção candidata (diagonal no caso regular) e limitações de teste.

Aceite: quina ortogonal rotacionada, quina com escala não uniforme, seleção irregular recusada corretamente, core retirado mostrado e material/folga por superfície de contato corretos.

## Interface e integração

Fluxo: selecionar referência → criar proposta → alinhar/dimensionar → inspecionar volume → gerar corte → validar → confirmar → continuar no receptor.

Gerar nova ferramenta não deve desfazer automaticamente prévia válida. Mudanças tornam preview desatualizado e exigem regeneração. Não confundir focar com regenerar.

Todos os botões e mensagens em PT/EN. Ajuda explica corpo, inserto, profundidade local, face de apoio e diferença entre direção do cortador e explosão visual.

Limite explícito da 0.8.9: sólidos gerais podem ser usados manualmente, mas geração automática de sólido para toda região curva/não planar está fora da garantia. Esse limite não elimina SOL-05/06 nos casos suportados.
