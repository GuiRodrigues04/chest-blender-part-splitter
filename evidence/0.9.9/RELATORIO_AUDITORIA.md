# Auditoria complementar 0.9.9

## Escopo e resultado

Auditoria executada em Blender 5.2.0 LTS, sobre a árvore scratch 0.9.9. Após a correção de folga epsilon de 0,001 mm, a regressão contou **99 testes**, com **1 skip** e nenhum teste falho. O complemento executou mais **53 testes**: seis suítes passaram; `test_release_workflows.py` teve **10 subcasos falhos** dentro de um método, `test_loop_auto_uses_selected_depth`, todos para folga 0,15 mm (dois corpos x cinco profundidades). O complemento teve **3 skips** por fixtures privadas indisponíveis.

Total contado: **152 testes**, **4 skips**, **10 falhas de assertion** concentradas nesse método. O número 152 soma os contadores unittest das duas baterias; os dez subcasos não são dez novos métodos. As verificações do pacote (2 testes) e da instalação real (7 testes) foram executadas à parte e passaram.

## Diagnóstico das falhas do workflow

A assertion compara listas cruas de coordenadas/índices de vértices e faces em previews repetidos; essa igualdade depende da ordem interna das malhas. Uma reprodução física isolada no primeiro corpo, profundidade 1 mm e folga 0,15 mm encontrou vértices não ordenados iguais nos dois lados (113 e 585 vértices), variação de volume de 0,000015 mm³ e 0 mm³, caixas delimitadoras idênticas e distância máxima vértice-superfície bidirecional de 0,0000075 mm e 0 mm. Isso mostra que, nesse caso medido, a divergência da assertion é reordenação sem mudança geométrica mensurável. **A medição detalhada cobre um caso, não os dez subcasos.**

Na comparação isolada com `scratch/baseline099` (manifesto 0.9.8), o mesmo método falhou em dez subcasos com `geometry.clearance_excessive` no mesmo fixture/folga, em vez da assertion de lista observada no código atual. A condição de folga problemática é anterior, mas os mecanismos de falha não são idênticos; não se conclui que todas as dez diferenças atuais foram provadas apenas reordenação.

### Atualização da etapa 1 — comparação física dos dez subcasos

A etapa 1 substituiu a igualdade de assinatura crua de malha por correspondência bijetiva de vértices e comparação de faces por ciclos orientados, `material_index` e UVs após reindexação, mantendo limites físicos de 0,001 mm. Em Blender 5.2.0 LTS, os dez subcasos passaram: distância bidirecional máxima de superfície 0,0005192 mm, diferença máxima de volume por peça 0,0002968 mm³, caixas delimitadoras idênticas, profundidade medida dentro de 0,0000086 mm, materiais e fonte preservados. A soma dos volumes repetidos foi idêntica.

Assinaturas exatas ainda diferiram em 6/20 comparações de vértices/faces e 7/20 de triangulações visíveis, mas todas passaram a bijeção semântica e as tolerâncias físicas. O fixture não possui UVs de origem; a preservação de UV não foi exercitada. Portanto, as dez falhas brutas de assinatura descritas acima ficam supersedidas para o workflow atual; o método revisado passou na suíte completa `test_release_workflows.py` (11 testes incluindo dois helpers). A condição de folga e a comparação separada com o baseline 0.9.8 permanecem conforme o histórico desta auditoria.

Relatório e dados por caso: [resumo da etapa 1](replay_validation/stage1_summary.md) e [JSON de validação](replay_validation/replay_validation_099.json).

## Matriz de pinos

Foram avaliados **20 cenários**: cinco rotas (`LOOP`, `WHOLE`, `SOLID`, `MATERIAL`, `PLANE`) x macho A/B x folga 0/0,2 mm. Os vinte previews de geometria passaram: duas peças, manifoldas, volume positivo e fonte imutável.

- **16 cenários com conectores ativados** nas quatro rotas suportadas passaram. `WHOLE` usa o fluxo de duas etapas: prévia sem pinos, escolha do contato, depois geração com pinos.
- **4 cenários `SOLID`** passaram como cortes sem conectores; o produto informa explicitamente que o cutter sólido apenas divide o modelo e não cria encaixes. Esses quatro casos são compatibilidade esperada, não testes de pino.

Medição física adicional, fora da contagem unittest e fora da matriz: raycasts BVH na malha gerada para um caso `LOOP`, macho A, folga entre peças zero. Vinte e quatro raios por malha mediram raio do pino de 0,9999999–1,0000002 mm e raio do soquete de 1,0999998–1,1000001 mm. A folga radial ficou entre 0,0999996–0,1000002 mm; o tip do pino mediu 3,0000000 mm e o fundo do soquete 3,1999999 mm, para folga axial de 0,1999999 mm. Ambos passaram tolerância de 0,02 mm.

## Suítes complementares

Passaram: `test_release_state.py` (10), `test_clearance_profiles.py` (6), `test_connector_clearance_slivers.py` (4), `test_material_manual_connectors_bugfix.py` (4), `test_plane_limited.py` (9) e `test_plane_contact_contours.py` (11; 3 skips). `test_release_workflows.py` contou 9 métodos; um método acumulou os dez subcasos falhos descritos acima.

## Evidências

- [Resumo estruturado da bateria complementar](audit_complement.json)
- [Logs das sete suítes complementares](complement_logs/)
- [Comparação da reprodução com baseline 0.9.8](baseline099_workflow_repro.log)
- [Matriz de 20 cenários e reprodução física de preview](current_replay_and_pin_matrix.json)
- [Medição física radial/axial do pino e soquete](pin_socket_physical_measurement.json)
- [Log da medição física](pin_socket_physical_measurement.log)

Hash SHA-256 final do código-fonte sob auditoria (módulos `src/*.py`, `__init__.py` e manifesto), registrado no JSON: `c9275a32af710d58bcc6e7981262aeb969af1282f57ac1813d2fc36b7a25efb5`.

## Verificação final do pacote

`test_release_package.py`: **2/2 passaram**. Verificador da instalação real: **7/7 passaram**, incluindo confirmação de bytes idênticos ao ZIP final, namespace instalado e cinco rotas de preview. O ZIP `dist/chest_part_splitter-0.9.9.zip` tem SHA-256 `EDA12F104A8B575A4FBA073DB5287F3C0EE8F72FA0BF6D59357D922D1FD0032B`.

Logs finais: [regressão de 13 suítes](current.json), [testes complementares](audit_complement.json), [pacote](final_release_package.log) e [instalação](final_installed_verify.log).
