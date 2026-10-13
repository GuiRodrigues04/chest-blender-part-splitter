# Part Splitter — revisão da 0.8.9 baseada no código recebido

Este pacote SUBSTITUI o plano anterior “Part_Splitter_0_8_9_Plano_Antigravity_Flash_3_8.zip”.

A distribuição recebida “chest-blender-part-splitter(2).zip” declara 0.8.9 no manifesto. Seu changelog descreve correções INV-001 a INV-006; o escopo pedido agora é completar INV-008 a INV-014, idiomas e ferramentas de sólido. Não confundir versão declarada com aprovação de todos esses requisitos.

## Prompt para Antigravity / Gemini Flash 3.8

Trabalhe sobre a base atual deste pacote, não sobre 0.8.5/0.8.6. Confirme que seu checkout coincide com SHA256_Fontes_Atuais.json. Leia 01_PLANO_DIRECIONADO.md e 04_MAPA_CODIGO_ATUAL.md. Depois leia especificações 02/03 e execute 05_TESTES_ACEITE.csv.

Finalize a revisão 0.8.9 corrigindo INV-008 a INV-014 e implementando SOL-01 a SOL-06 e LANG-01. Se a 0.8.9 já foi publicada/distribuída fora deste ambiente, combine numeração de release antes de sobrescrever; este pedido mantém o alvo 0.8.9.

Não duplicar recursos que já existem: invert_explosion e snapshots, lifecycle.py com operações pai/filho e reversão, triangulação compartilhada do Loop, helpers de domínio/espessura em geometry_connectors. Preserve essas proteções e amplie os contratos existentes.

Pontos concretos ainda pendentes:
- Folga Material altera apenas depth_a_bu/depth_b_bu.
- EXTRACTED é passado aos dois prismas e contamina material da cavidade.
- validate_printable_mesh e validação do cortador não checam área zero.
- set_target não invalida loop; overlay não verifica assinatura e ainda filtra índices fora de faixa silenciosamente.
- commit seleciona A/B e ativa A, sem próxima sessão no receptor.
- Ajustar à Área Válida existe, defaultFalse, mas não é desenhado no painel; busca só CENTER, LINEAR_2/3 continuam fixos.
- Criar/Focar Sólido ainda recria malha existente.
- Catálogo parcial e decisões de locale coexistem com textos PT fixos.

Implemente em etapas testáveis. Registre causa, arquivos e evidências; não declarar testes PASSOU sem executá-los. Os dois .blend estão intactos. Não executar scripts internos ao abrir cenas. Reproduza cinco polígonos colineares em Testes1 e loop antigo em receptor novo em Testes2.

Entregue ZIP instalável, changelog corrigido, relatório por INV/SOL/LANG, matriz de testes, antes/depois PT/EN e limites de suporte. Não tratar changelog que afirma28/28 como prova independente de novos requisitos: os testes têm lacunas descritas neste plano.

## Conteúdo

- 01_PLANO_DIRECIONADO.md: achados atuais, funções e ordem de correção.
- 02_FERRAMENTAS_SOLIDO.md: contratos das novas ferramentas.
- 03_IDIOMAS.md: política PT/EN e detalhes de migração.
- 04_MAPA_CODIGO_ATUAL.md: linhas exatas da base recebida.
- 05_TESTES_ACEITE.csv: 73 testes de aceite planejados, inicialmente NÃO EXECUTADO.
- 06_GALERIA.html:17 imagens dos casos.
- 07_RELATORIO_ENTREGA_MODELO.md: modelo de entrega.
- fontes/base_atual_0.8.9/: fonte e 33 arquivos de testes recebidos; sem histórico git.
- referencias/: fontes oficiais, hashes, código numerado e auditoria de strings.
- evidencias/: registros históricos INV-008 em diante e dois .blend.

Os registros históricos citam versões anteriores; prevalece a análise do código atual neste pacote. Não há implementação de correções aqui nem execução Blender.
