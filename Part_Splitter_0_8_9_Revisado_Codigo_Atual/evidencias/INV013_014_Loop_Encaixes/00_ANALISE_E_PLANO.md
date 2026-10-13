# INV-013 / INV-014 — Loop, encaixes e mudança de alvo

12/10/2026, horário de São Paulo. Capturas da extensão 0.8.8. Códigos disponíveis 0.8.5/0.8.6; não houve execução Blender.

## INV-013 — distribuição de dois encaixes falha no domínio

Imagem 01: dois pinos selecionados, diâmetro nominal 6 mm, inserção 8 mm, chanfro 0,8 mm, folga por lado 0,15 mm, folga de fundo 0,50 mm, margem da borda 4 mm. Mensagem: “O encaixe #1 ultrapassa a margem de segurança ... ou cai fora do domínio sólido da peça.”

Há três pinos visíveis porque o painel afirma “The visible preview is the previous valid one”. Não é evidência de que LINEAR_2 gerou três pinos: a tentativa falhou e conservou a prévia anterior.

O erro é de inclusão/margem do perfil do encaixe; não confirma falha no fechamento do Loop. Não remover a margem ou a validação para aceitar o corte.

### Hipótese de posicionamento a verificar

Na 0.8.6, geometry_connectors.compute_connector_layout obtém um bounding box em UV e escolhe LINEAR_2 em ±60% da meia-extensão disponível; LINEAR_3 usa centro e ±70%. Testa o domínio real depois de escolher posições.

Em contorno estreito, dobrado em planta ou côncavo, a caixa inclui áreas vazias. Duas posições pré-fixadas podem falhar embora exista outro par viável; três posições diferentes podem funcionar sem contradição. A cena/código 0.8.8 precisam confirmar qual perfil e posição realmente falharam.

Para diâmetro 6, folga 0,15 e margem 4, o raio de verificação circular do código antigo é 3+0,15+4=7,15 mm. Isso é distância de centro para proteção lateral do perfil, não regra para apagar detalhes.

### Correção proposta

1. Registrar UV dos candidatos, interface real, perfil escolhido, raio/comprimento, margem, e o segmento/ponto que viola a inclusão.
2. Desenhar candidatos rejeitados e explicar o motivo: fora do exterior, furo, falta de margem ou espessura/profundidade insuficiente.
3. Posicionar no domínio admissível da interface, considerando perfil fêmea completo mais margem. Para círculo, domínio de centros é erosão da região pelo raio protegido; para cápsula, incluir comprimento e orientação.
4. Para “2 Pinos (Linha)”, buscar intervalos viáveis na linha escolhida, com separação mínima. Se nenhuma solução colinear existir, oferecer ajuste manual ou outra distribuição explicitamente; não mudar silenciosamente a definição de Linha.
5. Se a linha atravessa vazios, não considerar todo bounding box como área utilizável. Pode haver intervalos separados válidos; verificar distância entre encaixes e domínio de ambos.
6. Distinguir “posição automática atual inválida” de “não existe solução suportada”. Uma busca amostrada sem sucesso não prova impossibilidade absoluta; informar resolução/método.
7. Validar implantação 3D: união do pino à peça macho, cavidade e fundo no receptor, espessura remanescente e ausência de colisões. Perfil 2D válido não garante inserção 8 mm segura.
8. Não reduzir automaticamente diâmetro, margem ou quantidade; sugestões devem ser explícitas e gerar nova prévia.
9. Falha preserva geometria E metadados da prévia anterior. Não usar parâmetros de LINEAR_2 para descrever objetos de LINEAR_3 como se fossem novos.

### Aceites

- Cena antes do commit: reproduzir CENTER/LINEAR_2/LINEAR_3 com mesmas dimensões e registrar posições.
- Contorno côncavo: par viável encontrado quando suportado, ou rejeição específica.
- Perfil sem espaço: erro justificado; nunca aceitar perfil fora da parede para “resolver”.
- Layout/manual: exatamente dois encaixes após geração bem-sucedida.
- Falha: três pinos antigos continuam corretamente identificados como prévia anterior.

## INV-014 — índices do Loop antigo desenhados no novo alvo

### Causa confirmada no estado salvo

O .blend contém Cube, Cube__A e Cube__B. Alvo principal salvo: Cube__B. Loop capturado: 62 índices, seed 1380, assinatura salva:

```text
V1463E2880F1423Ha1d551b9
```

A assinatura corresponde exatamente ao Cube original, calculada pelo algoritmo get_topology_signature da 0.8.6. Assinatura calculada do receptor novo:

```text
V1557E2994F1443Hfa7372e0
```

Todos os índices antigos estão dentro do intervalo de vértices de Cube__B; porém 59 de 62 segmentos não são arestas da nova malha. No Cube original, os 62 segmentos existem.

Isso explica as linhas atravessando faces: os mesmos números agora identificam outros vértices. O painel ainda exibe planaridade e seed antigos, que não são diagnósticos válidos do novo contorno.

Dados completos em Evidencias_Loop.json. Leitura binária SDNA, sem execução de scripts/Blender; incluir conferência nativa.

### Relação com código 0.8.6

- gpu_drawing._draw_loop_overlay_callback usa target.data com os índices salvos. Só verifica faixa superior dos índices, não origem/assinatura nem adjacência.
- CHEST_OT_splitter_set_target troca target_object e reinicia status de sessão, mas não limpa loop_is_captured, índices, seed, assinatura e metadados associados.
- Captura salva loop_topology_signature. O dado existe, mas precisa ser usado na troca de alvo, desenho e geração.

O estado da 0.8.8 confirma o reaproveitamento indevido; localizar a implementação atual antes de portar mudanças.

### Correção proposta

1. Associar captura ao objeto fonte E ao mesh/snapshot, assinatura topológica e versão geométrica. Mesmo mesh compartilhado por objetos com transformações diferentes requer origem explícita.
2. Ao trocar alvo para receptor confirmado ou outro objeto, invalidar loop/seed e razão AUTO antigos. Não manter flag Capturado/Planar só porque os índices ainda cabem.
3. Separar seleção do próximo corte de evidência histórica: a interface de um corte confirmado pode ser mantida como snapshot de coordenadas mundiais, vinculada à operação anterior, sem ser usada como loop do alvo atual.
4. Overlay desenha apenas captura validada: objeto e mesh corretos, assinatura compatível, ciclo simples e arestas existentes.
5. Se só a posição dos vértices mudou sem mudar conectividade, recalcular coordenadas/planicidade/capacidade antes de usar; assinatura apenas topológica não detecta deformação.
6. Em geração, revalidar antes de flood fill e encaixes. Seed em faixa não prova que aponta à mesma região.
7. Limpar cache GPU e solicitar redraw após invalidação. Não consertar linhas reordenando vértices arbitrariamente nem removendo pontos que “parecem longe”.
8. Para preservar loop no corpo pós-corte, somente com remapeamento de proveniência/adjacência validado. Padrão seguro nesta versão: exigir nova captura.
9. Undo/redo/restaurar/trocar mesh: mesmo contrato de validade. Evitar calcular hash completo a cada frame; invalidar/cachear por evento e verificar de modo consistente antes da geração.

### Mensagem proposta

“O corpo mudou após o corte. Capture um novo contorno para continuar.”

O painel deve limpar contagem, seed e resultado AUTO antigos ou identificá-los como inválidos; não exibir “Planar 0,00 mm” sobre linhas embaralhadas.

### Aceites

- Confirmar corte → escolher Cube__B: overlay antigo some, captura invalidada e nova captura solicitada.
- Arquivo salvo deste pacote: 59 segmentos ausentes detectados; geração bloqueada antes de encaixes.
- Trocar alvo sem mudar contagem de vértices: origem/mesh diferente detectados.
- Deformar mesma topologia: geometria/planicidade recalculadas.
- Capturar novo loop no receptor: overlay segue arestas corretas e seed válida.
- Undo/redo e restaurar: sem retorno de cache/índices de outro alvo.

## Ordem de trabalho para Gemini

Corrigir INV-014 primeiro, pois uma captura antiga pode contaminar corte e posicionamento de encaixes. Depois reproduzir INV-013 na malha original com captura válida, separando falta de espaço de algoritmo de layout.

Preservar original cena/Testes_2.blend. Executar scripts/verificar_loop_blender.py em cópia. Entregar causas, antes/depois e testes realmente executados; análise deste pacote não incluiu tentativa de booleano nem montagem física.
