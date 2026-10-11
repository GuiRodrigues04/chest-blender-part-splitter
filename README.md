# Chest Part Splitter (Blender Extension)

Extensão profissional para **Blender 5.2+** (compatível com Blender 4.2+) projetada para dividir modelos 3D em peças para impressão 3D (multicolor ou peças menores que a mesa) com geração automática de encaixes, controle físico de folgas em milímetros e integridade estrita de malhas fechadas (manifold).

---

## 🎯 Versão Atual: v0.8.5

A versão **`0.8.5`** consolida o fluxo de trabalho com isolamento transacional, conformidade dimensional e validação geométrica estrita:

1. **Quatro Modos de Corte Determinísticos**:
   - **Plano (Bisect Planar)**: Corte direto 2D através de plano guia interativo com fechamento estanque (*manifold capping*), inversão de lados e cálculo exato de volumes.
   - **Sólido (Cortador Volumétrico)**: Separação 3D através de primitivas geométricas paramétricas (Caixa, Cilindro, Esfera, Cápsula) ou objetos de malha já existentes na cena, com solver booleano `EXACT` e conservação de volume.
   - **Contorno de Arestas (Loop Fechado / Pata)**: Corte por anel contínuo de arestas selecionado em *Edit Mode* (ideal para patas, caudas, cabeças e membros de personagens), com fechamento automático de tampas ou projeção com profundidade física.
   - **Material / Cor**: Separação de peças por material. Suporta componentes fechados desconexos ou extração volumétrica de superfícies/decalques contínuos com profundidade configurável (`material_extrude_depth_mm`) gerando a cavidade receptora no corpo principal.

2. **Encaixes FDM & Folga Radial por Lado**:
   - **Pinos Cilíndricos**: Pinos macho com chanfro de inserção e cavidades fêmea dimensionadas com folga física por lado.
   - **Chaves Tipo Cápsula (Anti-Rotação)**: Conectores oblongos/estádio que impedem rotação e torção da peça montada, com auto-ajuste inteligente de comprimento para interfaces com restrição de espaço.
   - **Presets FDM Calibrados**:
     - *Justo (0,10 mm)*: Impressoras muito bem calibradas e eixos rígidos.
     - *Normal (0,15 mm)*: Padrão recomendado para PLA (bico 0,4 mm).
     - *Fácil (0,20 mm)*: Montagem manual suave sem esforço mecânico.
     - *Solto (0,25 mm)*: Peças volumosas, PETG ou impressoras com vibração.
     - *Personalizado*: Ajuste livre em milímetros.
   - **Distribuições Inteligentes**: Centro (1 pino), Linha (2 ou 3 pinos) e Grade 2x2 (4 pinos) com margem de segurança configurável até as paredes externas.
   - **Verificação de Parede Receptora**: Amostragem perimétrica para evitar que a cavidade fêmea perfure paredes finas ou inclinadas do modelo.

3. **Sistema de Exportação e Convenção Física em Milímetros**:
   - **Contrato Físico Único**: Coordenadas numéricas exportadas rigidamente em milímetros, independentemente da escala de unidades da cena (`scale_length = 1.0`, `0.01` ou `0.001`).
   - **3MF Multimaterial (.3mf)**: Arquivo padrão de alta fidelidade para Bambu Studio, OrcaSlicer e PrusaSlicer, com preservação de todas as cores e nomes de peças limpos com escaping XML atômico.
   - **STL por Material / Cor (.stl)**: Conjunto de arquivos STL compartilhando a mesma origem de coordenadas global em mm. Ao carregar todos no fatiador simultaneamente, são montados como um único modelo multipartes para impressão com AMS / MMU.
   - **STL por Peça (.stl)**: Exporta cada peça individualmente em arquivos STL sólidos e estanques.
   - **Wavefront OBJ (.obj + .mtl)**: Geometria e biblioteca de materiais exportada com fator de escala padronizado em milímetros (1 unidade = 1 mm).
   - **Alinhamento Canônico na Exportação**: Exportar com a visualização explodida ativada gera os arquivos na posição montada original (`(0, 0, 0)`), sem incorporar o afastamento visual temporário da viewport.

4. **Isolamento de Sessão & Proteção do Original**:
   - **Cópia de Trabalho Segura**: Criada em coleção dedicada (`CHEST_SPLITTER_WORK`), permitindo aplicar escalas e rotações sem alterar ou apagar o modelo original do usuário.
   - **Tolerância Zero a Remoção Acidental**: Limpezas de prévia nunca apagam objetos do usuário, alvos de corte ou cópias de trabalho ativas.
   - **Invalidação Transacional (`PREVIEW_STALE`)**: Caso o modelo alvo, cortador ou parâmetros de corte sejam movidos ou alterados na cena, a prévia é marcada imediatamente como desatualizada, bloqueando a confirmação ou exportação inadvertida de geometria obsoleta.

---

## 📂 Estrutura do Repositório

```text
chest-blender-part-splitter/
├── .gitignore
├── README.md
├── CHANGELOG.md
├── LICENSE
├── blender_manifest.toml
├── __init__.py
├── build_package.py
├── src/
│   ├── __init__.py
│   ├── constants.py
│   ├── properties.py
│   ├── translations.py
│   ├── diagnostic.py
│   ├── geometry_contract.py
│   ├── geometry_plane.py
│   ├── geometry_solid.py
│   ├── geometry_loop.py
│   ├── geometry_material.py
│   ├── geometry_connectors.py
│   ├── io_export.py
│   ├── operators.py
│   └── ui.py
└── tests/
    ├── run_all_tests.py
    ├── test_smoke_phase0.py
    ├── test_smoke_phase1.py
    ├── test_smoke_phase2.py
    ├── test_smoke_phase3.py
    ├── test_stress_phases0_3.py
    ├── test_phase3a_loop.py
    ├── test_multicolor_support.py
    ├── test_capsule_lateral_size.py
    ├── test_acceptance_etapa2.py
    ├── test_acceptance_etapa3.py
    ├── test_acceptance_etapa4.py
    ├── test_verify_bug_and_fix.py
    ├── test_acceptance_etapa5_ui.py
    ├── test_acceptance_etapa6_material.py
    ├── test_material_regions.py
    ├── test_acceptance_etapa7_delivery.py
    └── test_final_plan_corrections.py
```

---

## 🚀 Como Usar no Blender

1. **Definir Alvo**:
   - Selecione o objeto malha na Viewport 3D.
   - Pressione **N** para abrir a barra lateral e navegue até a aba **Chest** > **Part Splitter**.
   - Clique em **Usar objeto selecionado como alvo**.
   - Se houver avisos de rotação/escala, clique em **Criar cópia de trabalho com transformações aplicadas** para trabalhar em uma cópia segura.

2. **Escolher o Método de Corte**:
   - Selecione entre **Plano**, **Sólido**, **Contorno (Loop)** ou **Material**.
   - Ajuste o plano guia na viewport ou configure os parâmetros específicos do modo.

3. **Configurar Encaixes e Folgas (Opcional)**:
   - Marque **Ativar Encaixes**.
   - Escolha o tipo de encaixe (**Pino Cilíndrico** ou **Chave Cápsula**).
   - Defina o preset de folga FDM desejado (ex.: *Normal 0,15 mm*).

4. **Gerar e Conferir a Prévia**:
   - Clique em **Gerar / Atualizar Preview**.
   - Inspecione as partes geradas alternando para a visualização **Explodido** com o slider de afastamento.

5. **Criar Peças Finais ou Exportar**:
   - Clique em **Confirmar Divisão e Criar Peças** para consolidar os objetos na coleção `CHEST_SPLITTER_PARTS`.
   - Na seção de Exportação, escolha o formato (**3MF**, **STL por Material**, **STL por Peça** ou **OBJ**) e clique em **Exportar Peças para Impressão 3D**.

---

## 🛠️ Build e Testes Automatizados

### Executar Toda a Bateria de Testes
```bash
blender --background --python tests/run_all_tests.py
```

### Empacotamento Comercial (.zip)
```bash
python build_package.py
```
Gera o pacote limpo e sanitizado `chest_part_splitter-0.8.5.zip` pronto para distribuição, sem arquivos temporários, pastas de teste ou artefatos de desenvolvimento.

---

## ⚠️ Limitações e Orientações Técnicas

- **Encaixes em Superfícies Curvas Livres**: Os encaixes automáticos com folga paramétrica são gerados em interfaces de corte planas. Nos modos Sólido e Material com interfaces não-planares complexas, os encaixes devem ser modelados ou aplicados em etapas planares complementares.
- **Tolerâncias de Impressão**: As folgas nominais em milímetros geradas pela extensão são geometricamente precisas. Pequenas variações físicas podem ocorrer dependendo da calibração de fluxo de filamento (E-steps/Flow rate), dilatação térmica do filamento e resolução da impressora 3D. Recomenda-se realizar um teste prévio com uma peça menor usando o preset *Normal (0,15 mm)*.
