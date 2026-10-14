"""Catálogo de traduções e sistema de ajuda contextual para o Chest Part Splitter."""

import bpy
from typing import Tuple, List, Optional

HELP_TOPICS = {
    "target_model": {
        "title": {
            "pt_BR": "Objeto Alvo",
            "en_US": "Target Model",
        },
        "tooltip": {
            "pt_BR": "Selecione a malha que deseja dividir e clique em Usar selecionado.",
            "en_US": "Select the mesh you want to split, then click Use selected.",
        },
        "popup_lines": {
            "pt_BR": [
                "Selecione uma malha na cena e clique em 'Usar selecionado como alvo'.",
                "O add-on valida automaticamente se a malha é fechada (manifold),",
                "calcula suas dimensões físicas em milímetros e avisa caso haja",
                "escala não aplicada que possa distorcer os cortes ou as folgas.",
            ],
            "en_US": [
                "Select a mesh in the scene and click 'Use selected as target'.",
                "The add-on checks if the mesh is manifold (water-tight),",
                "computes its physical dimensions in millimeters, and warns if",
                "unapplied transforms might distort cuts or clearances.",
            ],
        },
    },
    "split_plane": {
        "title": {
            "pt_BR": "Corte por Plano",
            "en_US": "Planar Cut",
        },
        "tooltip": {
            "pt_BR": "Posicione o plano. Ele divide todo o modelo nos dois lados do plano.",
            "en_US": "Position the plane. It splits the entire model on either side of the plane.",
        },
        "popup_lines": {
            "pt_BR": [
                "O modo Plano divide o modelo inteiro em duas partes usando um plano 3D infinito.",
                "Clique em 'Focar Guia 3D' para visualizar o plano na viewport.",
                "Use os botões de alinhamento rápido para orientar o corte em relação à Vista,",
                "ao Cursor 3D, a uma Face selecionada ou aos eixos X, Y e Z.",
            ],
            "en_US": [
                "Planar mode splits the entire model into two parts across a 3D plane.",
                "Click 'Focus 3D Guide' to view the cutting plane in the viewport.",
                "Use the quick alignment buttons to align the cut to View, 3D Cursor,",
                "Active Face, or the global X, Y, and Z axes.",
            ],
        },
    },
    "split_material": {
        "title": {
            "pt_BR": "Divisão por Material",
            "en_US": "Split by Material",
        },
        "tooltip": {
            "pt_BR": "Divide o modelo isolando componentes ou regiões definidas por slots de materiais.",
            "en_US": "Splits the model by isolating components or regions defined by material slots.",
        },
        "popup_lines": {
            "pt_BR": [
                "O modo Material separa a malha de acordo com os materiais aplicados às faces.",
                "1. Se o material formar componentes 3D fechados (como olhos, botões ou acessórios),",
                "   ele os separa diretamente como sólidos 100% estanques para impressão 3D.",
                "2. Se o material for uma pintura na superfície, a extensão detecta a fronteira e",
                "   aplica a profundidade escolhida, criando um inserto sólido e a cavidade correspondente.",
            ],
            "en_US": [
                "Material mode separates the mesh based on materials assigned to its faces.",
                "1. If the material forms closed 3D shells (such as eyes, buttons, or accessories),",
                "   it separates them directly as 100% manifold solids ready for 3D printing.",
                "2. If the material is a painted surface patch, the boundary is extracted with",
                "   the chosen depth, producing a solid insert and matching socket cavity.",
            ],
        },
    },
    "split_loop": {
        "title": {
            "pt_BR": "Corte por Contorno (Loop)",
            "en_US": "Boundary Loop Cut",
        },
        "tooltip": {
            "pt_BR": "No Modo de Edição, selecione um contorno fechado de arestas e clique em Capturar contorno.",
            "en_US": "In Edit Mode, select a closed edge boundary and click Capture boundary.",
        },
        "popup_lines": {
            "pt_BR": [
                "O modo Contorno permite recortar detalhes específicos da superfície.",
                "Passo 1: No Modo de Edição, selecione um anel fechado de arestas contínuas",
                "e clique em 'Capturar Contorno'.",
                "Passo 2: Selecione apenas 1 face de referência da região e clique em 'Escolher Região'.",
                "O add-on inunda a malha e seleciona todo o resto da área delimitada automaticamente!",
            ],
            "en_US": [
                "Boundary mode allows cutting localized surface features or protrusions.",
                "Step 1: In Edit Mode, select a closed edge loop and click 'Capture Boundary'.",
                "Step 2: Select just 1 reference face in the desired area and click 'Choose Region'.",
                "The add-on automatically flood-fills and selects the entire bounded area!",
            ],
        },
    },
    "loop_region": {
        "title": {
            "pt_BR": "Escolher Região",
            "en_US": "Choose Region",
        },
        "tooltip": {
            "pt_BR": "Selecione uma face da região desejada e clique em Escolher região. O contorno limita essa seleção.",
            "en_US": "Select a face in the desired region and click Choose region. The boundary limits this selection.",
        },
        "popup_lines": {
            "pt_BR": [
                "Você NÃO precisa selecionar todas as faces de uma peça complexa!",
                "Basta selecionar apenas 1 face dentro da região desejada.",
                "O contorno capturado atua como uma barreira física; o add-on percorre",
                "todas as faces adjacentes e isola a região inteira automaticamente.",
            ],
            "en_US": [
                "You do NOT need to select all faces of a complex mesh!",
                "Simply select a single face inside the desired region.",
                "The captured loop acts as a barrier; the add-on traverses adjacent faces",
                "and captures the entire bounded region automatically.",
            ],
        },
    },
    "loop_extrude": {
        "title": {
            "pt_BR": "Extração com Profundidade",
            "en_US": "Depth Extrusion",
        },
        "tooltip": {
            "pt_BR": "Distância para dentro do modelo. A região extraída vira uma peça e deixa uma cavidade no restante.",
            "en_US": "Distance into the model. The extracted region becomes a part and leaves a recess in the remainder.",
        },
        "popup_lines": {
            "pt_BR": [
                "Extrai o perfil do contorno para dentro do sólido até a profundidade em milímetros.",
                "A porção extraída torna-se a Parte A e deixa uma cavidade perfeita na Parte B.",
                "Se a profundidade exceder a espessura da parede, ative 'Corte Passante'",
                "para furar o modelo de lado a lado.",
            ],
            "en_US": [
                "Extrudes the boundary profile into the solid down to the chosen depth in mm.",
                "The extracted volume becomes Part A and leaves a matching recess in Part B.",
                "If depth exceeds wall thickness, enable 'Through-cut' to pierce completely.",
            ],
        },
    },
    "connectors": {
        "title": {
            "pt_BR": "Encaixes e Pinos",
            "en_US": "Connectors & Pins",
        },
        "tooltip": {
            "pt_BR": "Escolhe qual peça recebe o pino saliente. A outra recebe a cavidade correspondente.",
            "en_US": "Chooses which part receives the protruding pin. The other receives the matching socket.",
        },
        "popup_lines": {
            "pt_BR": [
                "Gera automaticamente pinos macho em uma peça e cavidades fêmea na outra.",
                "Formatos disponíveis:",
                "  • Cilindro: Pino cilíndrico tradicional com chanfro na ponta.",
                "  • Cápsula: Pino oblongo ideal para travar rotação e dar maior área de contato.",
                "Os pinos respeitam margens mínimas das bordas e paredes de segurança contra perfuração.",
            ],
            "en_US": [
                "Automatically generates male pins on one part and matching female sockets on the other.",
                "Available shapes:",
                "  • Cylinder: Traditional round pin with chamfered tip.",
                "  • Capsule: Oblong stadium pin that prevents rotation and maximizes contact area.",
                "Pins respect safety edge margins and wall thickness limits.",
            ],
        },
    },
    "clearance": {
        "title": {
            "pt_BR": "Folgas Físicas de Montagem",
            "en_US": "Assembly Clearances",
        },
        "tooltip": {
            "pt_BR": "Espaço em cada lado do pino. Com pino de 6 mm e folga de 0,15 mm, a cavidade tem 6,30 mm.",
            "en_US": "Clearance on each side of the pin. A 6 mm pin with 0.15 mm clearance needs a 6.30 mm socket.",
        },
        "popup_lines": {
            "pt_BR": [
                "Folga por lado: folga radial aplicada uniformemente à cavidade receptora.",
                "Exemplo: Pino de 6,0 mm com folga 0,15 mm gera cavidade de 6,30 mm.",
                "Valores sugeridos para FDM (PLA / bico 0,4 mm):",
                "  • Justo (0,10 mm) - encaixe por pressão (press-fit).",
                "  • Normal (0,15 mm) - recomendado para montagem suave sem ferramentas.",
                "  • Fácil (0,20 mm) - recomendado para impressoras com calibração intermediária.",
                "  • Solto (0,25 mm) - folga ampla com espaço para cola.",
                "Folga de fundo: espaço livre no fundo da cavidade para evitar colisão na inserção.",
            ],
            "en_US": [
                "Clearance per side: radial offset applied uniformly to the receiving socket.",
                "Example: A 6.0 mm pin with 0.15 mm clearance creates a 6.30 mm socket.",
                "Suggested values for FDM (PLA / 0.4 mm nozzle):",
                "  • Tight (0.10 mm) - press-fit requiring light force.",
                "  • Normal (0.15 mm) - recommended for smooth, tool-free assembly.",
                "  • Easy (0.20 mm) - for machines with slight over-extrusion.",
                "  • Loose (0.25 mm) - extra loose fit with space for glue.",
                "End clearance: extra depth at socket bottom to prevent bottoming out.",
            ],
        },
    },
    "explosion": {
        "title": {
            "pt_BR": "Visualização Explodida",
            "en_US": "Exploded View",
        },
        "tooltip": {
            "pt_BR": "Afasta as peças no eixo de corte para inspecionar pinos, cavidades e interface.",
            "en_US": "Separates parts along the cut axis to inspect pins, cavities, and the cut interface.",
        },
        "popup_lines": {
            "pt_BR": [
                "Afasta as partes na direção normal da interface de corte.",
                "Quando encaixes estão ativados, a extensão ajusta automaticamente a distância",
                "para ser maior que a inserção do pino, garantindo que o pino e a cavidade",
                "fiquem totalmente visíveis e desencaixados logo ao clicar em 'Explodido'.",
                "Você pode ajustar livremente a distância pelo controle deslizante.",
            ],
            "en_US": [
                "Separates parts along the interface normal direction.",
                "When connectors are enabled, the extension automatically sets the distance",
                "larger than pin insertion length so both pin and socket are fully exposed.",
                "You can still freely adjust the slider to view further separation.",
            ],
        },
    },
}

TRANSLATIONS_DICT = {
    "pt_BR": {
        ("*", "Part Splitter"): "Part Splitter",
        ("*", "Part Splitter 0.8.11"): "Part Splitter 0.8.11",
        ("*", "Usar selecionado como alvo"): "Usar selecionado como alvo",
        ("*", "Posicionamento do Plano"): "Posicionamento do Plano",
        ("*", "Focar Guia 3D"): "Focar Guia 3D",
        ("*", "Alinhamentos Rápidos:"): "Alinhamentos Rápidos:",
        ("*", "Capturar Contorno"): "Capturar Contorno",
        ("*", "Escolher Região"): "Escolher Região",
        ("*", "Ativar Encaixes"): "Ativar Encaixes",
        ("*", "Enable Connectors"): "Ativar Encaixes",
        ("*", "Gerar / Atualizar Preview"): "Gerar / Atualizar Preview",
        ("*", "Confirmar Divisão"): "Confirmar Divisão",
        ("*", "Restaurar Original"): "Restaurar Original",
        ("*", "Remover Prévia"): "Remover Prévia",
        ("*", "Reverter este corte"): "Reverter este corte",
        ("*", "Confirmar Reversão do Corte?"): "Confirmar Reversão do Corte?",
        ("*", "Distância de Explosão (mm)"): "Distância de Explosão (mm)",
        ("*", "Explosion Distance"): "Distância de Explosão",
        ("*", "Explosion Distance (mm)"): "Distância de Explosão (mm)",
        ("*", "Inverter Sentido da Explosão"): "Inverter Sentido da Explosão",
        ("*", "Invert Explosion Direction"): "Inverter Sentido da Explosão",
        ("*", "Editar Posições dos Pinos"): "Editar Posições dos Pinos",
        ("*", "Editar Posições Novamente"): "Editar Posições Novamente",
        ("*", "Confirmar Posições e Gerar Prévia"): "Confirmar Posições e Gerar Prévia",
        ("*", "Ver Face de Encaixe"): "Ver Face de Encaixe",
        ("*", "Submodo do Editor"): "Submodo do Editor",
        ("*", "Adicionar"): "Adicionar",
        ("*", "Mover"): "Mover",
        ("*", "Nenhum pino posicionado. Clique em 'Editar Posições' para adicionar."): "Nenhum pino posicionado. Clique em 'Editar Posições' para adicionar.",
        ("*", "Corte por Contorno (Loop)"): "Corte por Contorno (Loop)",
        ("*", "Boundary Loop Cut"): "Corte por Contorno (Loop)",
        ("*", "Capturar das Faces"): "Capturar das Faces",
        ("*", "Destacar Contorno no Viewport"): "Destacar Contorno no Viewport",
        ("*", "Highlight Loop in Viewport"): "Destacar Contorno no Viewport",
        ("*", "Destacar Contorno"): "Destacar Contorno",
        ("*", "Highlight Loop"): "Destacar Contorno",
        ("*", "Resultados do Corte"): "Resultados do Corte",
        ("*", "Cut Results"): "Resultados do Corte",
        ("*", "Separar por Cores / Materiais"): "Separar por Cores / Materiais",
        ("*", "Folgas Físicas de Montagem (FDM):"): "Folgas Físicas de Montagem (FDM):",
        ("*", "Dimensões Nominais:"): "Dimensões Nominais:",
        ("*", "Distribuição no Corte:"): "Distribuição no Corte:",
        ("*", "Preview generation error"): "Erro na geração da prévia",
        ("*", "Adicionar base para encaixe"): "Adicionar base para encaixe",
        ("*", "Profundidade da base (mm)"): "Profundidade da base (mm)",
        ("*", "Folga lateral da base (mm)"): "Folga lateral da base (mm)",
        ("*", "Folga de fundo separada"): "Folga de fundo separada",
        ("*", "Folga de fundo (mm)"): "Folga de fundo (mm)",
        ("*", "Peça extraída selecionada. Use G para mover."): "Peça extraída selecionada. Use G para mover.",
        ("*", "Posicionamento Manual:"): "Posicionamento Manual:",
        ("*", "Posicionar no Viewport (Clique)"): "Posicionar no Viewport (Clique)",
        ("*", "Posicionar Encaixe no Viewport"): "Posicionar Encaixe no Viewport",
        ("*", "Converter Padrão para Manual"): "Converter Padrão para Manual",
        ("*", "Adicionar Conector Manual"): "Adicionar Conector Manual",
        ("*", "Remover Conector Manual"): "Remover Conector Manual",
        ("*", "Limpar Todos os Conectores"): "Limpar Todos os Conectores",
        ("*", "Total de Pinos:"): "Total de Pinos:",
        ("*", "Rotação Yaw (°)"): "Rotação Yaw (°)",
        ("*", "Posição Válida"): "Posição Válida",
        ("*", "Posição fora do domínio / margem violada"): "Posição fora do domínio / margem violada",
        ("*", "Nenhum conector adicionado. Clique na peça ou adicione."): "Nenhum conector adicionado. Clique na peça ou adicione.",
        ("*", "Os ajustes mudaram. Atualize a prévia antes de criar as peças."): "Os ajustes mudaram. Atualize a prévia antes de criar as peças.",
        ("*", "The visible preview is the previous valid one"): "A prévia visível é a anterior válida",
    },
    "en_US": {
        ("*", "Part Splitter"): "Part Splitter",
        ("*", "Part Splitter 0.8.11"): "Part Splitter 0.8.11",
        ("*", "Usar selecionado como alvo"): "Use selected as target",
        ("*", "Posicionamento do Plano"): "Plane Positioning",
        ("*", "Focar Guia 3D"): "Focus 3D Guide",
        ("*", "Alinhamentos Rápidos:"): "Quick Alignments:",
        ("*", "Capturar Contorno"): "Capture Boundary",
        ("*", "Capturar das Faces"): "Capture from Faces",
        ("*", "Destacar Contorno no Viewport"): "Highlight Loop in Viewport",
        ("*", "Highlight Loop in Viewport"): "Highlight Loop in Viewport",
        ("*", "Destacar Contorno"): "Highlight Loop",
        ("*", "Highlight Loop"): "Highlight Loop",
        ("*", "Escolher Região"): "Choose Region",
        ("*", "Ativar Encaixes"): "Enable Connectors",
        ("*", "Enable Connectors"): "Enable Connectors",
        ("*", "Gerar / Atualizar Preview"): "Generate / Update Preview",
        ("*", "Confirmar Divisão"): "Confirm Split",
        ("*", "Restaurar Original"): "Restore Original",
        ("*", "Remover Prévia"): "Discard Preview",
        ("*", "Reverter este corte"): "Revert this cut",
        ("*", "Confirmar Reversão do Corte?"): "Confirm Reversion of Cut?",
        ("*", "Distância de Explosão (mm)"): "Explosion Distance (mm)",
        ("*", "Explosion Distance"): "Explosion Distance",
        ("*", "Explosion Distance (mm)"): "Explosion Distance (mm)",
        ("*", "Inverter Sentido da Explosão"): "Invert Explosion Direction",
        ("*", "Invert Explosion Direction"): "Invert Explosion Direction",
        ("*", "Corte por Contorno (Loop)"): "Boundary Loop Cut",
        ("*", "Boundary Loop Cut"): "Boundary Loop Cut",
        ("*", "Resultados do Corte"): "Cut Results",
        ("*", "Cut Results"): "Cut Results",
        ("*", "Separar por Cores / Materiais"): "Separate by Colors / Materials",
        ("*", "Folgas Físicas de Montagem (FDM):"): "Assembly Clearances (FDM):",
        ("*", "Dimensões Nominais:"): "Nominal Dimensions:",
        ("*", "Distribuição no Corte:"): "Cut Distribution:",
        ("*", "Preview generation error"): "Preview generation error",
        ("*", "Adicionar base para encaixe"): "Add base for fitting",
        ("*", "Profundidade da base (mm)"): "Base depth (mm)",
        ("*", "Folga lateral da base (mm)"): "Base lateral clearance (mm)",
        ("*", "Folga de fundo separada"): "Separate bottom clearance",
        ("*", "Folga de fundo (mm)"): "Bottom clearance (mm)",
        ("*", "Peça extraída selecionada. Use G para mover."): "Extracted part selected. Use G to move.",
        ("*", "Posicionamento Manual:"): "Manual Positioning:",
        ("*", "Posicionar no Viewport (Clique)"): "Click to Position in Viewport",
        ("*", "Posicionar Encaixe no Viewport"): "Position Connector in Viewport",
        ("*", "Converter Padrão para Manual"): "Convert Pattern to Manual",
        ("*", "Adicionar Conector Manual"): "Add Manual Connector",
        ("*", "Remover Conector Manual"): "Remove Manual Connector",
        ("*", "Limpar Todos os Conectores"): "Clear All Connectors",
        ("*", "Total de Pinos:"): "Total Pins:",
        ("*", "Editar Posições dos Pinos"): "Edit Pin Positions",
        ("*", "Editar Posições Novamente"): "Edit Positions Again",
        ("*", "Confirmar Posições e Gerar Prévia"): "Confirm Positions & Generate Preview",
        ("*", "Ver Face de Encaixe"): "View Mating Face",
        ("*", "Submodo do Editor"): "Editor Submode",
        ("*", "Adicionar"): "Add",
        ("*", "Mover"): "Move",
        ("*", "Mover / Selecionar"): "Move / Select",
        ("*", "Nenhum pino posicionado. Clique em 'Editar Posições' para adicionar."): "No pins placed. Click 'Edit Pin Positions' to add.",
        ("*", "Rotação Yaw (°)"): "Yaw Rotation (°)",
        ("*", "Posição Válida"): "Valid Position",
        ("*", "Posição fora do domínio / margem violada"): "Position outside valid domain / margin violated",
        ("*", "Nenhum conector adicionado. Clique na peça ou adicione."): "No connectors added. Click on part or click Add.",
        ("*", "Os ajustes mudaram. Atualize a prévia antes de criar as peças."): "Settings changed. Update the preview before creating parts.",
        ("*", "The visible preview is the previous valid one"): "The visible preview is the previous valid one",
    },
}

MESSAGES = {
    "pt_BR": {
        "connectors.enable": "Ativar encaixes",
        "connectors.distribution": "Distribuição dos encaixes",
        "connectors.suggest_positions": "Sugerir posições",
        "connectors.suggest_count": "Sugerir quantidade",
        "connectors.outside_domain": "O encaixe {index} está fora da região útil ou viola a margem de {margin_mm} mm.",
        "preview.failed_preserved": "A atualização falhou: {reason}. A prévia anterior foi mantida.",
        "loop.recapture_target_changed": "O corpo mudou após o corte. Capture um novo contorno para continuar.",
        "target.edit": "Editar alvo",
        "target.continue_receiver": "Continuar no corpo remanescente",
        "explosion.reverse": "Inverter sentido da explosão",
        "cutter.focus": "Focar cortador",
        "cutter.from_selection": "Criar cortador desta seleção",
        "materials.receiver": "Material da cavidade",
        "materials.insert": "Material do inserto",
        "target.use_selected": "Usar selecionado como alvo",
        "target.model": "1. Objeto Alvo",
        "split.mode": "2. Método de Corte",
        "connectors.title": "3. Encaixes e Pinos (Opcional)",
        "preview.title": "4. Prévia do Corte",
        "commit.title": "5. Criar Peças",
        "commit.button": "Confirmar Divisão",
        "preview.generate": "Gerar / Atualizar Preview",
        "preview.discard": "Remover Prévia",
        "revert.button": "Reverter este corte",
        "cutter.create": "Criar Cortador",
        "cutter.reset": "Reiniciar Formato",
        "cutter.duplicate": "Duplicar Cortador",
        "cutter.copy_selected": "Copiar Selecionado como Cortador",
        "cutter.align": "Alinhar Cortador",
        "cutter.corner_box": "Caixa para Quina Regular",
        "view.assembled": "Montado",
        "view.exploded": "Explodido",
        "pin.count_1": "{count} pino gerado com sucesso.",
        "pin.count_2": "{count} pinos gerados com sucesso.",
        "pin.count_5": "{count} pinos gerados com sucesso.",
        "face.count_1": "{count} face na região.",
        "face.count_2": "{count} faces na região.",
        "face.count_5": "{count} faces na região.",
        "error.connector_space": "Falta de espaço: a interface ({width}x{length} mm) não comporta o encaixe com margem de {margin} mm.",
        "error.linear_space": "Falta de espaço: a distribuição {dist} requer vão de ao menos {min_len} mm (disponível: {avail_len} mm).",
        "error.grid_space": "Falta de espaço: a distribuição GRID_4 requer ao menos {min_w}x{min_h} mm (disponível: {avail_w}x{avail_h} mm).",
        "error.non_planar": "A seleção não é planar (desvio: {deviation} mm > 0.15 mm).",
        "error.irregular_corner": "Quina não ortogonal detectada. A geração de caixa requer 3 faces ortogonais.",
    },
    "en_US": {
        "connectors.enable": "Enable connectors",
        "connectors.distribution": "Connector distribution",
        "connectors.suggest_positions": "Suggest positions",
        "connectors.suggest_count": "Suggest count",
        "connectors.outside_domain": "Connector {index} is outside the usable region or violates the {margin_mm} mm margin.",
        "preview.failed_preserved": "Update failed: {reason}. The previous preview was preserved.",
        "loop.recapture_target_changed": "The body changed after the cut. Capture a new boundary to continue.",
        "target.edit": "Edit target",
        "target.continue_receiver": "Continue on the remaining body",
        "explosion.reverse": "Reverse explosion direction",
        "cutter.focus": "Focus cutter",
        "cutter.from_selection": "Create cutter from selection",
        "materials.receiver": "Cavity material",
        "materials.insert": "Insert material",
        "target.use_selected": "Use selected as target",
        "target.model": "1. Target Model",
        "split.mode": "2. Cutting Method",
        "connectors.title": "3. Connectors & Pins (Optional)",
        "preview.title": "4. Cut Preview",
        "commit.title": "5. Create Parts",
        "commit.button": "Confirm Split",
        "preview.generate": "Generate / Update Preview",
        "preview.discard": "Discard Preview",
        "revert.button": "Revert this cut",
        "cutter.create": "Create Cutter",
        "cutter.reset": "Reset Shape",
        "cutter.duplicate": "Duplicate Cutter",
        "cutter.copy_selected": "Copy Selected as Cutter",
        "cutter.align": "Align Cutter",
        "cutter.corner_box": "Box for Regular Corner",
        "view.assembled": "Assembled",
        "view.exploded": "Exploded",
        "pin.count_1": "{count} pin generated successfully.",
        "pin.count_2": "{count} pins generated successfully.",
        "pin.count_5": "{count} pins generated successfully.",
        "face.count_1": "{count} face in region.",
        "face.count_2": "{count} faces in region.",
        "face.count_5": "{count} faces in region.",
        "error.connector_space": "Lack of space: interface ({width}x{length} mm) does not fit connector with {margin} mm margin.",
        "error.linear_space": "Lack of space: distribution {dist} requires gap of at least {min_len} mm (available: {avail_len} mm).",
        "error.grid_space": "Lack of space: distribution GRID_4 requires at least {min_w}x{min_h} mm (available: {avail_w}x{avail_h} mm).",
        "error.non_planar": "Selection is non-planar (deviation: {deviation} mm > 0.15 mm).",
        "error.irregular_corner": "Non-orthogonal corner detected. Box generation requires 3 orthogonal faces.",
    },
}


def get_addon_preferences(context: Optional[bpy.types.Context] = None) -> Optional[bpy.types.AddonPreferences]:
    """Recupera preferências da extensão."""
    ctx = context or bpy.context
    if not ctx or not hasattr(ctx, "preferences") or not ctx.preferences:
        return None
    addons = getattr(ctx.preferences, "addons", None)
    if not addons:
        return None
    for k, addon in addons.items():
        if k == "chest_part_splitter" or k.endswith(".chest_part_splitter") or k == __package__ or k == "src":
            pref = getattr(addon, "preferences", None)
            if pref:
                return pref
    return None


def get_addon_locale(context: Optional[bpy.types.Context] = None) -> str:
    """Retorna o código de idioma atual respeitando as preferências do add-on (pt_BR ou en_US)."""
    pref = get_addon_preferences(context)
    if pref and hasattr(pref, "language"):
        lang = pref.language
        if lang == 'PT_BR':
            return "pt_BR"
        elif lang == 'EN_US':
            return "en_US"

    # AUTO: detecta idioma configurado no Blender
    try:
        loc = getattr(bpy.app.translations, "locale", None)
        if loc and loc.startswith("pt"):
            return "pt_BR"
    except Exception:
        pass
    return "en_US"


def _get_current_locale(forced_locale: Optional[str] = None) -> str:
    """Retorna o código de idioma atual (pt_BR ou en_US)."""
    if forced_locale is not None:
        return "pt_BR" if forced_locale.startswith("pt") else "en_US"
    return get_addon_locale()


def tr(key: str, **kwargs) -> str:
    """Resolve uma mensagem pelo catálogo de idiomas (LANG-01)."""
    loc = get_addon_locale()
    catalog = MESSAGES.get(loc, MESSAGES.get("en_US", {}))
    template = catalog.get(key)
    if template is None:
        template = MESSAGES.get("en_US", {}).get(key)
    if template is None:
        template = MESSAGES.get("pt_BR", {}).get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template


def get_help_tooltip(topic: str) -> str:
    """Retorna o texto de tooltip resumido para o tópico indicado."""
    loc = get_addon_locale()
    topic_data = HELP_TOPICS.get(topic)
    if not topic_data:
        return "Clique para ajuda sobre este recurso." if loc == "pt_BR" else "Click for help on this feature."
    tooltips = topic_data.get("tooltip", {})
    return tooltips.get(loc, tooltips.get("pt_BR", ""))


def get_help_popup_content(topic: str) -> Tuple[str, List[str]]:
    """Retorna título e linhas para exibição em popup dialog."""
    loc = get_addon_locale()
    topic_data = HELP_TOPICS.get(topic)
    default_title = "Ajuda" if loc == "pt_BR" else "Help"
    default_lines = ["Nenhum tópico explicativo disponível."] if loc == "pt_BR" else ["No help topic available."]
    if not topic_data:
        return (default_title, default_lines)

    title = topic_data.get("title", {}).get(loc, topic_data.get("title", {}).get("pt_BR", default_title))
    lines = topic_data.get("popup_lines", {}).get(loc, topic_data.get("popup_lines", {}).get("pt_BR", default_lines))
    return title, lines


_translations_registered = False


def register_translations():
    """Registra catálogo de traduções nativas do Blender."""
    global _translations_registered
    if not _translations_registered:
        try:
            bpy.app.translations.register(__name__, TRANSLATIONS_DICT)
            _translations_registered = True
        except ValueError:
            pass


def unregister_translations():
    """Remove catálogo de traduções nativas do Blender."""
    global _translations_registered
    if _translations_registered:
        try:
            bpy.app.translations.unregister(__name__)
            _translations_registered = False
        except ValueError:
            pass

