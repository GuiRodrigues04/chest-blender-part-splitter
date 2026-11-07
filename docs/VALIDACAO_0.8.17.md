# Validação 0.8.17 — molduras e aberturas

Data: 20/10/2026. Ambiente: Blender 5.2.0 LTS, Windows. Plano: [PLANO_MOLDURAS_E_ABERTURAS.md](PLANO_MOLDURAS_E_ABERTURAS.md).

## Diagnóstico

A borda da placa Arco é uma região conectada com dois contornos, externo e interno. O algoritmo antigo classificava toda região com mais de um contorno como corpo/base e recusava a seleção. A abertura central não é uma ilha selecionada: ela deve permanecer no receptor.

A malha original `.blend` do Arco tem 1.054 vértices, 2.104 faces e nenhuma aresta aberta. O antigo reparo usava uma distância física de 0,1 mm e podia destruir pequenos detalhes, reproduzindo as 1.851 faces e 21 arestas inválidas da captura do usuário. A nova soldagem usa no máximo 0,0001 mm e só publica um candidato fechado e válido. Arquivos já danificados não são reconstruídos automaticamente; reabrir o original preservado é o caminho recomendado.

## Implementação

- Motor compartilhado em `src/geometry_regions.py`: um contorno externo, uma ou várias aberturas, extração pela base ou profundidade e booleanas com validação estrita. Não preenche o centro.
- Material reconhece essa região como extraível. Loop registra a região e todos os contornos ao capturar pelas faces; visualização e assinaturas de atualização incluem esses dados.
- A folga lateral atua nas paredes externas e internas. Fundo independente e aplicações na peça, cavidade ou ambas. O contrato de interface contém a superfície real de contato e seus vazios.
- Pinos respeitam as aberturas. Em interfaces com aberturas, usa o solver MANIFOLD quando disponível para evitar fragmentação de costuras coplanares. Outros casos mantêm EXACT. A validação final continua obrigatória.
- Reparo em cópia, validação em coordenadas físicas, retorno ao modo de edição e recusa de buracos que soldagem não resolve.

O Arco possui bordas de apoio em alturas diferentes, porém paralelas. O apoio usa a altura mais profunda para preservar o relevo. O contorno exposto também é considerado para não truncar detalhes. Um deslocamento numérico externo de 0,00002 mm no cortador do receptor de relevos elimina películas quase coincidentes; o volume sem folga precisa continuar dentro de uma parte por milhão ou 0,05 mm³, o maior. Isso não substitui nem reduz as folgas configuradas pelo usuário. Nenhuma película foi disfarçada por troca de cor.

## Evidências

- Suíte completa: **59/59 suítes aprovadas**, em processos Blender isolados. Logs em `evidence/molduras_0817/final/`.
- Após os ajustes finais de assinatura e pinos, **13/13 suítes afetadas aprovadas** em `final_connectors/`; conferências adicionais de geometria, estado e identidade do pacote em `final_followup/` e `final_hash/`, todas aprovadas.
- `test_frame_regions.py`: Arco real pela base e por profundidade, folgas 0 e 0,1 mm, corpo central preservado, ausência de películas brancas no receptor, fontes intactas, uma e duas aberturas, folgas PART/CAVITY/BOTH, fundo independente, escalas/rotações/espelhamento, cena em milímetros, exportação STL, confirmação e reversão. Pinos automáticos reais no Arco: diâmetro 1,5 mm, inserção 1 mm, margem 0,3 mm e folga de 0,1 mm.
- `test_safe_mesh_repair.py`: malha válida e Arco real sem alterações, costura coincidente reparada, buraco real recusado, escala não uniforme e restauração do contexto de edição.
- Conferência visual: `evidence/molduras_0817/Arco_moldura_e_corpo.png`, gerada a partir do `.blend` original em uma sessão isolada.
- Pacote 0.8.17 validado pelo empacotador do Blender e conferido byte a byte contra o código-fonte. Instalação atualizada com **32 arquivos conferidos**. A instalação anterior foi preservada integralmente em `evidence/molduras_0817/installed_before/`.
- Teste da instalação real aprovado: registro no namespace da extensão, Arco pela base com folga de 0,1 mm, confirmação/reversão, reparo sem alteração e geração com pinos automáticos. Registro em `evidence/molduras_0817/installed_smoke.log`. A cena aberta e os modelos originais do usuário permaneceram intactos; reiniciar o Blender carrega a versão nova na sessão de trabalho.

## Uso e limites

No Arco original, selecione a cor clara em Material e use Pela Base. Para extrair também uma camada abaixo dela, use Profundidade. Em Loop, selecione as faces da moldura e capture o contorno pelas faces: ambos os anéis serão registrados. Use pinos menores que a largura útil da borda.

Suporte atual: uma região selecionada conectada, com aberturas não aninhadas e projeção desimpedida sobre apoio planar/paralelo. Contornos cruzados, regiões selecionadas realmente desconectadas, apoio inválido, espessura insuficiente e folgas excessivas continuam sendo recusados. Se uma operação falha, a fonte e a prévia válida anterior são preservadas.

O manifesto mantém Blender 4.2 como mínimo do projeto, mas esta entrega foi validada no Blender 5.2. O solver MANIFOLD depende de disponibilidade nessa versão do Blender; versões anteriores usam EXACT e podem recusar casos que ele não resolve. A impressão física e a calibração de folgas ainda dependem dos testes do usuário.
