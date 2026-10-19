# Part Splitter 0.8.14

Extensão para Blender para dividir modelos 3D em peças para impressão (FDM/SLA) com encaixes macho/fêmea (pinos cilíndricos e chaves cápsula), folgas físicas de montagem, pré-visualização montada/explodida, histórico de reversão e exportação multipartes para fatiadores (Bambu Studio, OrcaSlicer, PrusaSlicer) em STL, 3MF Multimaterial e OBJ.

## Instalação

No Blender:
1. Acesse **Edit > Preferences > Get Extensions** (ou **Add-ons**).
2. Clique no menu superior direito (ícone de engrenagem ou seta) e selecione **Install from Disk...**
3. Escolha o arquivo instalável `chest_part_splitter-0.8.14.zip`.
4. O painel estará disponível na Sidebar da Viewport 3D (pressione tecla `N` > aba **Chest** > painel **Part Splitter**).

## Modos de Corte

1. **Plano**: Corte planar direto com posicionamento interativo do plano de corte, indicação translúcida da lâmina e linha de interseção exata (sem artefatos em n-gons côncavos).
2. **Cortador Sólido**: Divisão booleana volumétrica por cortador sólido paramétrico ou objeto existente. Inclui criação rápida de cubos para quinas (`Corner Box`), geração de cortador prismático a partir de faces selecionadas (`Create Cutter from Faces`), alinhamento por 2 cliques de vértices e folga de montagem.
3. **Loop de Arestas**: Extração ou separação de peças por contorno de arestas com cálculo de profundidade e fechamento manifold automático.
4. **Corte por Material**: Separação de regiões ou componentes fechados por índice de material/cor com diagnóstico estrutural e separação em sub-peças individuais.

## Encaixes e Tolerâncias

- **Formatos de Pinos**: Cilindro e Chave Cápsula (com rotação orientável no plano de contato).
- **Distribuições**: Sem Pinos, Centralizado, Dois Pinos Automáticos e Posicionamento Manual Interativo na Viewport.
- **Folgas Físicas**: Folga radial por lado (`clearance_per_side_mm`), folga de fundo (`end_clearance_mm`) e folga de interface (`part_clearance_mm`).

## Exportação e Fatiadores

- **Resolução de Operações (COM-01)**: Confirmar a divisão mantém a operação ativa plenamente exportável, permitindo encadear cortes em sequência no corpo remanescente (`RECEIVER`), na peça extraída (`EXTRACTED`) ou finalizar (`NONE`).
- **3MF Multimaterial (COM-04)**: Exporta peças como modelos separados em coordenadas globais com materiais e cores originais. Corrige automaticamente a ordem dos triângulos (winding) em objetos espelhados ou com escala negativa, garantindo volumes positivos e consistentes.
- **Validação Física Global**: Rejeita matrizes singulares ou peças com escala zero antes da publicação.

## Verificação e Testes

- **Testes Automatizados**: Suíte com 62 testes de regressão automatizados executados e aprovados no Blender 5.2.0 LTS (`tests/test_regressions.py` e `tests/test_commercial_audit.py`).
- **Suporte de Versões**: Compatível com Blender 4.2 LTS até Blender 5.2+.

## Licença

GPL-2.0-or-later. Consulte `LICENSE` para mais detalhes.
