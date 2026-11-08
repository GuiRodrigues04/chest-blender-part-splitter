Splitter 0.9.8 — candidata para validação

- Corrige o domínio dos pinos em fechamentos curvos compatíveis: usa a área
  comum completa, preservando furos e o apoio físico. Centro e Manual deixam
  de se limitar a uma única faceta da grade.
- Adiciona Sugerir dimensões, calculando diâmetro e profundidade pelos sólidos
  cortados. Parâmetros salvos, scripts e ajustes personalizados são preservados.
- Corrige acesso a UV invalidado em cortes com folga e escala reduzida.
- Mantém a tentativa de quads, a triangulação segura e as verificações de
  margem, folga, parede receptora e fechamento.

Validação dirigida: 13 suítes, 100 métodos declarados, nenhuma falha e um
skip por referência privada ausente. Onze cenários reais aprovados nas
placas, pata do gato, chifre e pé da Spot; pacote e instalação verificados.
O cenário real da pata foi executado independentemente do teste pulado.

Limite anterior registrado: extração de 1 mm por Loop na região azul da
placa ainda é recusada por dezesseis arestas nulas, igualmente à 0.9.7.
Outras limitações históricas registradas na 0.9.7 não foram objeto de uma
bateria completa nesta atualização.

Baixe chest_part_splitter-0.9.8.zip. No Blender, use Preferences > Get
Extensions > Install from Disk. Reabra o Blender e gere novamente a prévia.
