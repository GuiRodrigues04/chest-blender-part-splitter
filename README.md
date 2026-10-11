# Chest Part Splitter

Extensão do Blender para dividir modelos em peças para impressão 3D. Inclui cortes por plano, sólido, loop e material, prévia, encaixes em interfaces compatíveis e exportação.

Versão desta base: 0.8.7. Homologada no Blender 5.2.0 LTS (compatibilidade declarada: Blender 4.2 ou superior).

## Instalação e uso

Instale o ZIP de distribuição em Preferences > Extensions > Install from Disk. Na Viewport 3D, abra N > Chest > Part Splitter.

1. Defina o objeto alvo e escolha o método de corte.
2. Configure corte, encaixes e folgas disponíveis.
3. Gere a prévia e confira as duas peças.
4. Confirme ou exporte o resultado.

Use Remover Prévia para voltar ao alvo. A reversão de um corte confirmado utiliza o backup da operação; cortes posteriores dependentes precisam ser tratados primeiro.

## Desenvolvimento

Python 3.11+ para os scripts externos. O Blender é necessário para testes geométricos e empacotamento oficial.

```bash
python tests/run_all_tests.py --blender /caminho/para/blender
python scripts/build.py --blender /caminho/para/blender
```

Também é possível definir BLENDER_BIN ou disponibilizar blender no PATH. O pacote é gerado em dist/. O build não copia arquivos para Downloads.

| Pasta | Conteúdo |
|---|---|
| src/ | Código da extensão |
| tests/ | Suítes e reproduções de bugs |
| scripts/ | Empacotamento e ferramentas de desenvolvimento |
| docs/ | Arquitetura e documentação atual |
| docs/archive/ | Planos antigos para consulta |
| dist/ | Pacotes gerados, fora do controle de versão |

## Limites e Recursos

Encaixes automáticos com suporte a ajuste determinístico à área sólida útil (polo de inacessibilidade em regiões côncavas U/L) disponíveis em interfaces compatíveis. A versão 0.8.7 implementa Ear Clipping 2D em loops côncavos, eliminação de lâminas coplanares no alinhamento por face, calibração física de folga entre peças (E01), extração avançada por material e ciclo de vida transacional com proteção de snapshots. Presets de folga de encaixes continuam sendo pontos de partida e podem requerer calibração conforme a tolerância da impressora 3D e filamento.

Licença: GPL-2.0-or-later. Veja LICENSE.
