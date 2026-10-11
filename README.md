# Chest Part Splitter

Extensão do Blender para dividir modelos em peças para impressão 3D. Inclui cortes por plano, sólido, loop e material, prévia, encaixes em interfaces compatíveis e exportação.

Versão desta base: 0.8.6. Próxima versão planejada: 0.8.7. Compatibilidade declarada: Blender 4.2 ou superior; a compatibilidade real deve ser confirmada nos testes.

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

## Limites

Encaixes automáticos estão disponíveis em Plano e Loop nesta base. Material e Sólido precisam de interface de contato adequada para a ampliação prevista na 0.8.7. Presets de folga são pontos de partida e precisam de calibração de impressão.

Esta cópia contém organização documental e ajustes nos scripts de desenvolvimento. Os algoritmos de corte continuam sendo os da 0.8.6 e possuem problemas descritos no plano da 0.8.7.

Licença: GPL-2.0-or-later. Veja LICENSE.
