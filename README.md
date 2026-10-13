# Chest Part Splitter

Extensão do Blender para dividir modelos em peças para impressão 3D. Inclui cortes por plano, sólido, loop e material, prévia, encaixes em interfaces compatíveis e exportação.

Versão desta base: 0.8.10. Homologada no Blender 5.2.0 LTS (compatibilidade declarada: Blender 4.2 ou superior).

## Instalação e uso

Instale o ZIP de distribuição em Preferences > Extensions > Install from Disk. Na Viewport 3D, abra N > Chest > Part Splitter.

1. Defina o objeto alvo e escolha o método de corte (Plano, Sólido, Loop ou Material).
2. Configure corte, encaixes, base de saliência e folgas disponíveis.
3. Gere a prévia e confira as duas peças com o overlay GPU destacado.
4. Confirme ou exporte o resultado. A confirmação seleciona exclusivamente a peça extraída (alerta na UI caso a edição proporcional 'O' esteja ativa).

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
| tests/ | Suítes de teste de regressão e aceitação |
| scripts/ | Empacotamento e ferramentas de desenvolvimento |
| docs/ | Arquitetura e documentação atual |
| docs/archive/ | Planos antigos para consulta |
| dist/ | Pacotes gerados, fora do controle de versão |

## Recursos e Limites (0.8.10)

- **Triangulação Construtiva de Delaunay (CDT 2D)**: Eliminação de triângulos degenerados e arestas nulas em extrusões planas e contornos côncavos (`output_type = CDT_INSIDE`).
- **Cortador de Caixa de Quina Ortogonal**: Ancoragem determinística em 3 faces ortogonais com 1 vértice compartilhado e extensão exterior para proteção contra coplanaridade degenerada no solver EXACT.
- **Alinhamento Robusto de Cortador Sólido**: Posicionamento livre de deriva cumulativa ($t = ref\_pos - R \cdot S \cdot a_{local}$) preservando rotação e escala física.
- **DETACH com Base e Cavidade Receptora**: Destaque de saliências com prolongamento de base e cavidade complementar usinada no corpo receptor, com verificação de espessura de parede e folgas físicas.
- **Overlay GPU em Ciano Vibrante**: Destaque visual nítido das arestas do cortador e vetor de penetração no viewport.
- **Seleção Semântica e Proteção**: Confirmação seleciona unicamente a peça extraída com alerta sobre Edição Proporcional (`use_proportional_edit_objects`).
- **Localização**: Suporte completo a Português do Brasil e Inglês em todas as tooltips, diagnósticos e painéis.

Licença: GPL-2.0-or-later. Veja LICENSE.
