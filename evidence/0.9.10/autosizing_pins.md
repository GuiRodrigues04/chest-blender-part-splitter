# Dimensionamento automático de pinos — evidência 0.9.10

Data: 2026-11-11
Runtime: Blender 5.2.0 LTS (Windows)
Base inicial: commit `ed994ab935033191d43f2a5b8786fd9045a5cbba`

## Spot do Desktop

Arquivo: `C:\Users\guiro\OneDrive\Desktop\Spot corte bugado.blend`. A cena foi aberta somente para leitura; as alterações do teste ficaram em memória e o arquivo não foi salvo. A cena carregada já apontava para `spot_quadrangulated — Restante 001`, modo LOOP/EXTRUDE, profundidade de 5 mm, sem objetos de prévia e estado `PREVIEW_INVALID`. A interface preparada pelo corte salvo mede 19,90 × 9,10 mm. Portanto, a cena local não reproduz a medida de contato 10,1 × 4,2 mm relatada para o olho.

Com o estado legado Ø6 × 8 mm restabelecido em memória e sem prévia ativa, **Sugerir dimensões** retornou Ø7,75 × 4,25 mm. As prévias com macho A e macho B terminaram em `PREVIEW_VALID`; ambas as partes foram classificadas como manifold. O limitador de profundidade foi definido pelo lado receptor mais raso.

## Contato estreito reproduzível

Um bloco de 10,1 × 4,2 × 12 mm, cortado para deixar 5,5 mm de receptor, reproduz o tamanho de contato informado. Com Ø6 × 8 mm, o preview foi recusado: a seção de 4,2 mm não comporta o requisito transversal de 7,1 mm. Antes de qualquer prévia válida, **Sugerir dimensões** ajustou para Ø3 × 4,5 mm. A margem de 0,4 mm e a folga radial de 0,15 mm dão limite geométrico de 3,1 mm; o arredondamento conservador em passos de 0,25 mm escolhe 3,0 mm. Prévia com macho A: `FINISHED`, `PREVIEW_VALID`, manifold. Prévia com macho B: `FINISHED`, `PREVIEW_VALID`, manifold.

## Casos adicionais

- Corpo de 500 mm com contato quadrado de 10 × 10 mm (100 mm²): sugestão Ø8,75 × 13 mm; receptor medido em aproximadamente 249,9 mm.
- Distribuição Manual vazia: recomendação usa centro como referência, preserva `MANUAL` e mantém zero pinos na lista.
- Pino Manual existente em contato curvo: dimensões calculadas sem alterar posição ou rotação.
- Região capturada com um contato: contato escolhido e dimensões sugeridas antes da prévia; a sugestão não altera o estado ativado/desativado dos encaixes.
- Região capturada com múltiplos contatos: escolhas divulgadas, sem seleção automática arbitrária.
- Dimensões salvas Ø6 × 8 mm com marca de personalização ausente são elegíveis como defaults históricos; valores não padrão e edições explícitas permanecem protegidos. Edição feita enquanto o timer aguarda não é sobrescrita.
- Alteração da forma do conector invalida a assinatura da sugestão para recalcular dimensões compatíveis.

## Verificação executada

`tests/test_connector_domain_sizing.py`: 14/14 aprovados no Blender 5.2.0 LTS. A suíte cobre contato 10,1 × 4,2 mm, os dois lados macho, preparo sem prévia, amostras de profundidade, contatos múltiplos, valor Manual vazio e preenchido, preservação de personalização, alteração atrasada durante o timer, escala de cena e corpo grande.

A checagem de profundidade usa amostras geométricas determinísticas do interior do perfil e do receptor; não é uma prova contínua em todo ponto da malha. Não foi feito teste físico de impressão.

