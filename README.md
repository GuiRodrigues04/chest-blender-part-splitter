# Chest Part Splitter (Blender Extension)

Extensão interna para **Blender 5.2+** (compatível com Blender 4.2+) projetada para dividir modelos 3D em peças para impressão 3D (multicolor ou peças menores) com geração de encaixes e controle de folgas de montagem em milímetros.

---

## 🎯 Status Atual: v0.4.0 (Fase 3 Concluída)

A extensão está na versão **`v0.4.0`**, com as seguintes capacidades ativas e validadas:
- **Fase 0 (Fundação)**: Diagnóstico físico em mm, integridade manifold, volume, escala e coleções dedicadas.
- **Fase 1 (Corte Planar)**: Bisect 2D, capping manifold automático, guia visual, visualização montada/explodida e inversão de lados.
- **Fase 2 (Encaixes FDM)**: Pinos cilíndricos e chaves tipo cápsula com folga física calibrada (presets de 0,10 a 0,25 mm), chanfro de entrada e distribuições simétricas.
- **Fase 3 (Cortador Sólido)**: Corte 3D volumétrico via primitivas paramétricas (Caixa, Cilindro, Esfera, Cápsula) ou malhas existentes da cena, com solver booleano EXACT e conservação de volume.
- **Próxima: Fase 3A (Loop Fechado de Arestas / Corte de Pata)**: Separação direta por anel de arestas selecionado na malha (ex.: pata de gato/animal) com tampas internas compartilhadas.

> Para detalhes completos da arquitetura, roadmap de fases e critérios de aceite, consulte [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## 📂 Estrutura do Repositório

```text
chest-blender-part-splitter/
├── .gitignore
├── README.md
├── ARCHITECTURE.md
├── CHANGELOG.md
├── LICENSE
├── blender_manifest.toml
├── __init__.py
├── src/
│   ├── __init__.py
│   ├── constants.py
│   ├── properties.py
│   ├── diagnostic.py
│   ├── geometry_plane.py
│   ├── geometry_connectors.py
│   ├── geometry_solid.py
│   ├── operators.py
│   └── ui.py
└── tests/
    ├── test_smoke_phase0.py
    ├── test_smoke_phase1.py
    ├── test_smoke_phase2.py
    └── test_smoke_phase3.py
```

---

## 🚀 Como Usar no Blender

1. Selecione o objeto malha desejado na Viewport 3D.
2. Pressione **N** para abrir a barra lateral e vá na aba **Chest**.
3. Localize o subpainel **Part Splitter** e clique em **Usar objeto selecionado como alvo**.
4. Verifique as dimensões físicas em mm, triângulos e diagnósticos de malha.
5. Se houver aviso de escala não aplicada, utilize o botão **Criar cópia de trabalho com transformações aplicadas** para trabalhar em uma cópia segura sem modificar o modelo original.

---

## 🛠️ Build e Instalação

### Validação do Manifesto
```bash
blender --command extension validate .
```

### Empacotamento em ZIP
```bash
blender --command extension build
```

### Instalação no Blender
```bash
blender --command extension install-file chest_part_splitter-0.1.0.zip
```
