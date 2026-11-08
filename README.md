# Splitter 0.9.8

**Candidata para validação.** Consulte o [guia rápido PT/EN](docs/GUIA_RAPIDO_PT_EN.md) e o relatório de validação desta versão antes do lançamento comercial.

Extensão para Blender para dividir modelos 3D em peças para impressão (FDM/SLA) com encaixes macho/fêmea (pinos cilíndricos e chaves cápsula), folgas físicas de montagem, pré-visualização montada/explodida, histórico de reversão e exportação das peças pelos recursos do Blender.

## Instalação

No Blender:
1. Acesse **Edit > Preferences > Get Extensions** (ou **Add-ons**).
2. Clique no menu superior direito (ícone de engrenagem ou seta) e selecione **Install from Disk...**
3. Escolha o arquivo instalável `chest_part_splitter-0.9.8.zip`.
4. O painel estará disponível na Sidebar da Viewport 3D (pressione tecla `N` > aba **Splitter**).

## Modos de Corte

1. **Plano**: Corte planar direto com posicionamento interativo do plano de corte, indicação translúcida da lâmina e linha de interseção exata (sem artefatos em n-gons côncavos).
2. **Cortador Sólido**: Divisão booleana volumétrica por cortador sólido paramétrico ou objeto existente. Inclui criação rápida de cubos para quinas (`Corner Box`), geração de cortador prismático a partir de faces selecionadas (`Create Cutter from Faces`), alinhamento por 2 cliques de vértices e folga de montagem.
3. **Loop de Arestas**: Extração ou separação de peças por contorno de arestas com cálculo de profundidade e fechamento manifold automático.
4. **Corte por Material**: Separação de regiões ou componentes fechados por índice de material/cor com diagnóstico estrutural e separação em sub-peças individuais.

## Reparo de microfaces

No Modelo Alvo, use **Mostrar faces** para selecionar somente as faces consideradas degeneradas pelo motor. **Tentar reparo seguro** trabalha em uma cópia e a aplica somente se estiver fechada e preservar forma, volume e materiais dentro dos limites físicos; pode ser desfeito com Undo. Faces pequenas bem formadas não são descartadas. Buracos reais e reparos que excedam os limites são recusados. O arquivo .blend em disco não é salvo automaticamente. Após um reparo, capture novamente os contornos de Loop.

O reparo da malha não torna qualquer folga possível: microaberturas podem colapsar com uma folga maior que seus detalhes. Nesse caso, o corte continua bloqueado com indicação do parâmetro; a extensão não altera medidas nem apaga detalhes para forçar a operação.

## Encaixes e Tolerâncias

**Centro e dimensões dos pinos (0.9.8):** cortes curvos compatíveis usam a área de contato completa entre as duas peças; as arestas internas da grade não são bordas do encaixe. **Sugerir dimensões** calcula valores iniciais pelo contorno e pela profundidade disponível na peça receptora. Ao ativar os pinos pela interface, a sugestão é aplicada a valores iniciais ainda não personalizados. Parâmetros salvos e ajustes manuais são preservados; use o botão para solicitar uma nova sugestão. Atualize a prévia após instalar a versão nova.

**Padrão de Folgas:** Impressão FDM aplica 0,10 mm entre peças (lateral e fundo), 0,15 mm radial nos pinos e 0,20 mm no fundo dos furos. Sem folgas zera esses valores. Personalizado preserva os valores e permite ajustá-los; editar uma folga ativa esse modo automaticamente. Os perfis não alteram diâmetro, comprimento, quantidade ou posição dos pinos, nem o lado de aplicação da folga. São valores iniciais que precisam de calibração na impressora. Arquivos existentes preservam suas medidas.

### Molduras e regiões com aberturas (0.8.17)

No modo **Material**, escolha a cor da moldura e use **Pela Base** para um relevo, ou **Profundidade** para extrair uma base sob a região. A área central permanece no corpo receptor. No modo **Loop**, selecione as faces da moldura e use **Capturar Contorno das Faces**: os contornos externo e internos são registrados juntos. A folga considera tanto a parede externa quanto as internas; a folga de fundo pode ser configurada separadamente. Pinos precisam caber na largura útil da borda e não podem atravessar as aberturas. Contornos cruzados e folgas que colapsem detalhes continuam sendo recusados. O reparo de malha é conservador e não preenche buracos reais automaticamente.

- **Formatos de Pinos**: Cilindro e Chave Cápsula (com rotação orientável no plano de contato).
- **Distribuições**: Sem Pinos, Centralizado, Dois Pinos Automáticos e Posicionamento Manual Interativo na Viewport.
- **Folgas Físicas**: Folga radial por lado (`clearance_per_side_mm`), folga de fundo (`end_clearance_mm`) e folga de interface (`part_clearance_mm`).

## Exportação e Fatiadores

A seção integrada Slicer Export está oculta nesta etapa comercial. Exporte as peças pelos recursos do Blender. Os recursos internos abaixo estão preservados para validação futura e não são oferecidos no painel.

- **Resolução de Operações (COM-01)**: Confirmar a divisão mantém a operação ativa plenamente exportável, permitindo encadear cortes em sequência no corpo remanescente (`RECEIVER`), na peça extraída (`EXTRACTED`) ou finalizar (`NONE`).
- **3MF Multimaterial (COM-04)**: Exporta peças como modelos separados em coordenadas globais com materiais e cores originais. Corrige automaticamente a ordem dos triângulos (winding) em objetos espelhados ou com escala negativa, garantindo volumes positivos e consistentes.
- **Validação Física Global**: Rejeita matrizes singulares ou peças com escala zero antes da publicação.

## Verificação e Testes

Consulte [a estrutura do repositório](docs/ESTRUTURA_REPOSITORIO.md) e [o índice de evidências](evidence/README.md). Scripts de auditoria de modelos reais estão em `scripts/audits/`; regressões automatizadas permanecem em `tests/`.

- **Testes Automatizados**: `tests/run_all_tests.py` executa cada suíte em um processo Blender isolado e permite salvar logs com `--report-dir`. Execute `scripts/build.py` antes das suítes que verificam o ZIP instalado. O relatório da candidata registra resultados e limitações.
- **Versões**: o manifesto declara Blender 4.2 como mínimo. A validação atual da candidata usa Blender 5.2.0 LTS; outras versões precisam ser verificadas antes de anunciar suporte à candidata.
- **Aceitação final**: conferir visualmente os casos reais, abrir as exportações no fatiador e imprimir amostras de encaixe faz parte da preparação comercial.

## Licença

GPL-2.0-or-later. Consulte `LICENSE` para mais detalhes.
