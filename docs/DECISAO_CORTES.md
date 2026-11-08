# Decisão de corte — 0.9.7

Todos os métodos passam pela mesma tentativa conservadora de organizar as
superfícies novas em quads **depois da folga e antes dos encaixes**. Essa etapa
preserva a superfície física e só aceita grades compatíveis. Caso contrário,
mantém a triangulação e informa isso sem apresentar o sucesso como erro.

| Método | Decisão de geometria |
| --- | --- |
| Loop, destacar membro | Contornos ortogonais em três direções usam o solver de degraus já validado. Demais contornos tentam fechamento natural com grade, depois triangulação. O fechamento deve caber na origem e coincidir entre as peças na tesselação visível. |
| Loop, extrair superfície | Mantém a profundidade ou passagem completa escolhida e o tratamento de relevos. O modo automático encaminha fechamentos que cruzam ou saem da origem para extração com profundidade. |
| Material, destacar pela base | Bases planas mantêm a extração anterior. Uma base não plana com contorno único tenta o mesmo fechamento natural do Loop; se cruza ou sai do sólido, mantém a orientação para escolher profundidade. |
| Material, extrair com profundidade | Mantém o motor de profundidade e encaminha relevos ao motor de Loop. Regiões com furos conservam seu tratamento conjunto dos contornos. |
| Região inteira | Mantém a separação e os contatos físicos já validados, incluindo múltiplos contatos. A organização de quads atua nas superfícies novas compatíveis. |
| Plano | Mantém a divisão pelo plano e o domínio escolhido. Contornos internos são fechados conjuntamente para preservar os furos. |
| Sólido | Mantém a divisão pelo cortador fechado e sua folga. Continua sem criar conectores diretamente nesse modo. |

## Folga no fechamento natural

1. Tenta o deslocamento existente, preservando o contorno e suas restrições.
   O caminho convexo por planos mantém suas verificações específicas por
   face: em uma quina, a distância mínima não é a mesma medida que o
   afastamento normal de cada plano. Os demais deslocamentos naturais com
   folga escalar também passam pela medição da tesselação visível descrita
   abaixo; uma grade que apenas parecia ter a espessura correta é repetida.
2. Se a folga escalar falhar, obtém um fechamento natural válido sem folga.
3. Estende localmente a superfície e cria uma lâmina fechada com Solidify
   Complex/Constraints. A espessura é convertida de milímetros para o espaço
   de mundo, incluindo a escala da cena. Boolean Exact remove a faixa da
   peça, da cavidade ou metade em cada lado, conforme a escolha.
4. Verifica fechamento, volume positivo, redução de volume e distâncias
   amostradas entre as superfícies. Não altera a malha original. A nova
   lâmina se restringe a contornos únicos com projeção radial válida; furos,
   folgas lateral/fundo distintas e bases adicionais mantêm seus motores.
5. Na área comum de contato, verifica distâncias nos dois sentidos e raios
   normais ao fechamento original. A tolerância é max(0,005 mm, 5% da folga).
   Amostras cuja projeção está na borda do contorno original (até 0,001 mm)
   são reportadas separadamente: além desse limite finito de contato pode
   não existir superfície oposta. A faixa sem esse filtro também é exibida.
   Isso é validação amostrada, sem garantia matemática de espessura exata.
6. Uma superfície natural válida não é trocada por degraus apenas para
   aceitar uma folga que falhou. A operação preserva a prévia anterior e
   informa a recusa quando a geometria não passa pelas verificações.

## Encaixes

No fechamento natural curvo, identifica áreas planas opostas e calcula sua
interseção projetada. Usa a maior área comum compatível como apoio local
dos encaixes. O motor de encaixes mantém suas verificações de margem,
profundidade e colisão, e usa a normal real desse apoio. Não remodela toda
a área cortada para acomodar um pino.

## Limites preservados

Uma fronteira curva pode ter distâncias diferentes nas bordas externas,
mesmo com espessura normal correta no interior. A interface informa os
valores medidos em vez de prometer uniformidade global. Contornos que não
admitem grade ficam triangulados. Regiões com espaço insuficiente para um
encaixe continuam podendo ser recusadas. A 0.9.7 não remove esses limites
relaxando as verificações dos algoritmos anteriores.
