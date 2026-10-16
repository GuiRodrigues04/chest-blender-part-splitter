# Casos relatados e cobertura 0.8.13

Os números preservam a coleta desta conversa. As imagens anexadas não estavam disponíveis nos caminhos locais informados, e não foi recebido um .blend com cada reprodução. Portanto, os testes abaixo representam classes de falhas e não comprovam a reprodução exata de todos os exemplos visuais do usuário.

| Item | Relato / pedido | Alteração e teste correspondente |
| --- | --- | --- |
| 01 | Marcas longe da peça após cancelar prévia e editar | Deslocamento só existe quando há prévia visível desta sessão; testes de cancelar/reabrir em Plano e Sólido. |
| 02 | Pinos tortos em relação à peça | Atualização de normais em espaço global, normal de apoio orientada pela região e rotações por lado macho; testes com rotação e escala não uniforme. |
| 03 | Espessura criada no Loop com cor do cubo | Proveniência explícita das faces novas da região extraída e da cavidade; testes de profundidade e destaque com base. |
| 04 | Marcas antigas depois de mudar o loop | Cache invalidado pelos parâmetros e seleção; posições vinculadas à região. Trocar de domínio não reaproveita a lista antiga. |
| 05 | Dois pinos falham, Auto consegue dois | Busca de candidatos por toda a área, perfil exato e separação física; teste de dois pinos em região em U. Auto preservado. O exemplo visual exato ainda precisa de reprodução. |
| 06 | Profundidade falha em uma forma específica | Apoio abaixo do contorno projetado e raios interiores de espessura; testes com relevo, contorno não plano e transformações. |
| 07 | Pinos separados / aparentemente aleatórios | UV estável, levantamento sobre tampas trianguladas e cache vinculado à interface; testes de posição e frame. Não se presume uma causa única para todos os exemplos. |
| 08 | Profundidade também falha em Material | Mesma direção de apoio e profundidade abaixo da base; testes separados de Material plano, relevo, contorno não plano e peça transformada. |
| 09 | Pino correto, sinalização verde flutuando | Marcadores usam a interface física e o deslocamento real da prévia, sem inventar explosão quando ela não existe. |
| 10 | Folga desabilitada em Sólido | Controle habilitado e aplicado por offsets físicos A/B; testes Peça/Cavidade/Ambos, lados invertidos e escala não uniforme. |
| 11 | Pinos manuais em Sólido | Face de contato escolhida automaticamente ou capturada; grade e UV acompanham o cortador; testes de prévia com pinos e com folga. |
| 12 | Cubo apagado continua azul e ainda corta | Validação pela presença na cena, não só em bpy.data; removida recuperação silenciosa de outro cortador pelo nome. Testes conservam propositalmente o datablock sem a presença na cena e verificam rejeição. |
| 13 | Alinhar um vértice do sólido com um do alvo | Operador interativo de dois cliques e função de translação em espaço global; testes com pai, escala e rotação. A interação visual exige validação no Blender gráfico. |
| 14 | Manual falha em Plano | Interface única, atualização quando o corte muda e frame estável; teste completo de editar, confirmar, gerar, remover e reabrir. Cliques e arraste reais ainda precisam de confirmação no Windows. |

Validação complementar: quatro distribuições automáticas, cápsula e giro individual, furos internos, corte passante, material pela base, confirmar/reverter, limpeza de temporários, preservação da prévia anterior após erro e chamadas dos controles de interface registrados.
