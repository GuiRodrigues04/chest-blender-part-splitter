# Relatório técnico — Part Splitter 0.8.13

## Base e escopo

Base: o ZIP `chest_part_splitter-0.8.12.zip` enviado pelo usuário nesta conversa. Não foram usadas as versões 0.8.5 ou 0.8.6 como base. O pacote mantém o identificador `chest_part_splitter`, as APIs públicas anteriores e a licença GPL-2.0-or-later informada no manifesto. A atualização é 0.8.13 para distinguir este trabalho do instalador 0.8.12 já distribuído.

O escopo cobre os 14 itens da coleta, incluindo as propostas de pinos no Sólido e alinhamento por vértices. Consulte CASOS_REPORTADOS.md para a relação entre cada relato, alteração e teste.

## Alterações principais

- Marcadores não usam mais a origem antiga salva em settings quando falta uma interface válida. Cache de geometria é invalidado por alterações do corte, da região ou dos operandos; desenho não executa booleanas. Layouts automáticos são armazenados por parâmetros para não refazer a busca completa em cada redraw.
- A vista explodida usa a translação do objeto de prévia real da sessão. Sem prévia, o deslocamento é zero. A edição manual trabalha no alvo montado, e reabrir a edição não herda a explosão antiga.
- BMesh.normal_update() é chamado após transformar coordenadas para o espaço global. Normais locais deixaram de ser combinadas com coordenadas mundiais. A normal de apoio orienta os pinos; não se usa a inclinação arbitrária da face-semente como eixo de extração.
- Frames simétricos têm escolha determinística de eixos. Uma tampa não plana usa seus triângulos reais para elevar o ponto UV até o contato, em vez de posicionar o pino e o marcador em um plano fictício.
- A extração com profundidade admite contornos não planos cuja projeção simples permita um prisma de apoio. A profundidade começa abaixo do apoio inferior de todo o contorno; a extensão externa cobre o relevo. A espessura é amostrada no interior dos triângulos da pegada, evitando raios exatamente nas arestas.
- Novas faces de Loop recebem material da região extraída em A e do receptor em B; os operandos de extração são separados para manter essa proveniência. Os controles existentes de material no modo Material foram preservados.
- A busca de dois pinos não fica limitada aos 25 candidatos próximos à melhor margem. Ela considera toda a distribuição amostrada, testa o perfil real e respeita distância entre pinos. É uma busca amostrada, não uma prova matemática de empacotamento ótimo para qualquer forma.
- Um objeto excluído pode continuar em bpy.data por estar referenciado. Agora o corte e a sobreposição exigem que o cortador esteja na cena ativa. Não há recuperação silenciosa de um cortador antigo pelo nome durante Gerar Prévia.
- Sólido usa cópias temporárias avaliadas do cortador para offsets físicos em espaço global. Os deslocamentos dos vértices resolvem as equações dos planos das faces; valores incompatíveis com os detalhes são recusados. O cortador original não é redimensionado para fabricar folga.
- Uma face plana de contato do Sólido fornece a interface dos encaixes. A face escolhida é mantida e os eixos seguem uma aresta geométrica persistente do cortador. Operadores permitem capturar outra face ou solicitar nova escolha automática.
- Alinhamento por vértices soma uma translação em matrix_world, preservando a parte linear da matriz e funcionando com parentesco e transformações não aplicadas.
- A verificação de parede receptora distingue a entrada no corpo da parede de saída. Isso corrige a falsa espessura de 0,2 mm quando há uma folga de 0,2 mm entre as peças.

## Evidência automatizada

49 métodos de regressão em cada runtime oficial `bpy`:

| Runtime | Resultado |
| --- | --- |
| Blender 4.2.23 | 49 aprovados |
| Blender 4.5.3 | 49 aprovados |
| Blender 5.0.1 | 49 aprovados |

Total: 147 execuções aprovadas. Os testes criam cenas sintéticas, validam fechamento, volume, material, direção dos pinos, presença dos controles e o ciclo de prévia/confirmar/reverter. Os logs completos estão em evidencias. Algumas mensagens ao encerrar o módulo bpy mencionam liberação de memória após o detector de leaks do runtime; os processos terminaram com sucesso. Esses avisos não equivalem a teste de interação gráfica nem demonstram ausência de qualquer leak no Blender gráfico.

O instalador foi validado pelo CLI oficial blender_ext. Um smoke test carregou o namespace real `bl_ext.user_default.chest_part_splitter`, verificou PT/EN, folga e pinos manuais em Sólido, prévia, confirmação, reversão e unregister.

Verificação estática: compileall e Ruff nas regras F821, F823 e E9. O teste de painel confere propriedades e operadores com um layout de teste; não é renderização da interface.

O registro `baseline_0812.json` mostra exemplos confirmados na base antiga: explosão de marcadores sem prévia, aceitação de cortador removido da cena e rejeição preventiva de profundidade nos dois modos para contorno não plano. O mesmo registro conserva os casos sintéticos que já passavam na base antiga; não se afirma que todo exemplo criado reproduza o screenshot do usuário.

## Preservação de funções e limites

Foram mantidos Plano, Loop, Material e Sólido, pinos cilíndricos/cápsula, Auto e quantidades fixas, modo manual, folgas, vistas montada/explodida, confirmar, remover prévia, reverter, idiomas e exportadores existentes. Não houve migração destrutiva de cena, remoção obrigatória de arquivos do repositório nem mudança de licença.

Ainda não foi possível testar os arquivos .blend dos relatos, ler os screenshots indisponíveis, executar Blender 5.2 com interface gráfica no Windows ou imprimir as peças. Portanto, isto não é uma garantia de inexistência de bugs ou uma certificação de prontidão comercial. A validação visual final deve cobrir os 14 relatos nas peças originais.

Extrações por apoio não resolvem universalmente projeções que se cruzam ou geometrias com sobreposição ao longo da direção de extração. Folgas podem colapsar detalhes. O modo Sólido oferece encaixes em uma face plana de contato de cada vez, não um editor contínuo para toda uma superfície curva. A escolha de vértices usa a malha original. A versão continua bloqueando resultados inválidos em vez de relaxar checagens de manifold para forçar sucesso.

## Referências técnicas consultadas

Implementação própria sobre a API do Blender, sem importar código de extensões de terceiros:

- BooleanModifier / EXACT / material_mode: https://docs.blender.org/api/4.5/bpy.types.BooleanModifier.html
- Normais e atualização de BMesh: https://docs.blender.org/api/current/bmesh.types.html#bmesh.types.BMesh.normal_update
- Matrizes e translações em espaço global: https://docs.blender.org/api/current/mathutils.html
- Conversão entre região da viewport e espaço 3D: https://docs.blender.org/api/current/bpy_extras.view3d_utils.html
- Exemplos oficiais de operadores modais: https://docs.blender.org/api/current/bpy.types.Operator.html#modal-execution
- Código nativo do modificador booleano: https://projects.blender.org/blender/blender/src/branch/main/source/blender/modifiers/intern/MOD_boolean.cc

A consulta web retornou documentação primária indexada; a abertura direta de algumas páginas não estava disponível. Os comportamentos empregados foram verificados também nas APIs bpy instaladas e nos testes executáveis incluídos.
