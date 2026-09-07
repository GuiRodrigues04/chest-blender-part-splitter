# Chest Part Splitter (Blender Extension)

Extensão interna para **Blender 5.2+** (compatível com Blender 4.2+) projetada para dividir modelos 3D em peças para impressão 3D (multicolor ou peças menores) com geração de encaixes e controle de folgas de montagem em milímetros.

---

## 🎯 Status Atual: Fase 0 (Fundação)

A **Fase 0** estabelece a infraestrutura essencial da extensão:
- Seleção e diagnóstico completo de geometria do objeto alvo;
- Verificação de dimensões físicas reais em mm, contagem de triângulos e volume;
- Detecção preventiva de escala não aplicada, arestas abertas (não-manifold) e faces degeneradas;
- Fluxo não destrutivo com geração de cópias de trabalho e coleções organizadas (`CHEST_SPLITTER_GUIDES` e `CHEST_SPLITTER_PREVIEWS`);
- Persistência no arquivo `.blend`.

> Para detalhes das fases futuras (Corte por plano, Encaixes, Cortador sólido e Materiais), consulte [`ARCHITECTURE.md`](./ARCHITECTURE.md).

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
│   ├── operators.py
│   └── ui.py
└── tests/
    └── test_smoke_phase0.py
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
