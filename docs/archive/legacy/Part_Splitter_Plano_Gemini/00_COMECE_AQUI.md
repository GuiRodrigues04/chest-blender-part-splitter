# Part Splitter — pacote para Gemini Flash 3.8 / Antigravity

Preparado em 12/10/2026. Objetivo: investigar e corrigir INV-001 a INV-006, preservando o caso positivo e preparando um escopo comercial verificável.

## Prompt para colar no Antigravity

Você vai implementar as correções deste pacote na extensão Blender Part Splitter. Leia primeiro 01_PLANO_IMPLEMENTACAO.md, 02_MAPA_CODIGO.md e 03_TESTES_ACEITE.csv. Abra 04_GALERIA.html para comparar os seis casos com as imagens originais.

Confirme a versão e o caminho do módulo realmente instalado antes de editar. Este pacote contém originais 0.8.5 e 0.8.6, não contém código 0.8.7. O registro histórico cita uma 0.8.7 que não foi disponibilizada nesta análise. Se seu checkout for posterior, remapeie referências por função e registre o diff: não substitua arquivos novos pelos da 0.8.6.

Trabalhe em etapas pequenas, na ordem do plano. Para cada etapa: reproduza, registre causa com arquivo/função, aplique correção mínima e execute os testes relevantes no Blender. Não confunda análise estática com teste executado. Não declare o caso do usuário reproduzido a partir de uma cena sintética: os .blend originais não estão neste pacote.

Corrija o automático da explosão e acrescente inversão apenas visual. Crie tampas compartilhadas e preserve o contorno. Investigue materiais separadamente da geometria. Preserve a extração com profundidade de 10 mm do INV-003. Resultados sem volume são inválidos; pontas finas geometricamente corretas exigem diagnóstico, sem alteração automática.

Não esconda erros repintando a peça inteira, ignorando faces.new, desligando manifoldness, preenchendo todas as aberturas ou aumentando tolerâncias para aceitar o loop de 14,76 mm. Falhas devem preservar original e prévia válida anterior.

Entregue: extensão ZIP instalável; changelog; relatório por INV com causas confirmadas versus pendentes; resultados dos testes com versão Blender; cenas sintéticas; imagens antes/depois; limitações conhecidas. Se um recurso não puder ser validado, mantenha-o experimental com explicação clara. Não declare a versão comercial pronta enquanto houver bloqueadores geométricos pendentes.

## Conteúdo e leitura econômica

1. 01_PLANO_IMPLEMENTACAO.md: decisões, etapas, invariantes e correções propostas.
2. 02_MAPA_CODIGO.md: referências de funções e linhas verificadas na 0.8.6.
3. 03_TESTES_ACEITE.csv: testes novos, registro de execução e condições de aceite.
4. 04_GALERIA.html: 15 capturas com contexto; basta abrir no navegador.
5. referencias/: registro histórico, diff 0.8.5→0.8.6, código numerado, testes históricos selecionados, receitas sintéticas e links oficiais.
6. scripts/: diagnóstico somente de leitura e verificação de identidade dos arquivos.
7. originais/: os dois ZIPs recebidos, intactos.

O plano é uma análise estática acompanhada de evidências visuais. Blender não está instalado neste ambiente; scripts com bpy não foram executados. Nenhuma correção da extensão foi implementada aqui. A verificação de sintaxe dos auxiliares não comprova sua execução no Blender.
