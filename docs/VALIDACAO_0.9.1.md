# Validação Splitter 0.9.1 — 2026-11-02

## Correções

O fechamento anterior tentava representar contatos unidos em direções diferentes por uma única projeção. A nova conclusão convexa é aceita somente após verificar superfície selecionada, contenção, topologia e conservação de volume. O caminho anterior continua atendendo regiões côncavas compatíveis. Uma seleção ambígua é recusada sem inventar um fechamento.

A folga resolve simultaneamente as restrições de todas as normais de contato, incluindo os cantos. Isso evita afastar somente o fundo e deixar a lateral encostada. Transições que exigem mudança de topologia usam uma faixa construída pelas mesmas restrições e uma auditoria de afastamento; resultados com dentes remanescentes são recusados. A entrada permanece intacta se não houver resultado válido.

Também foram corrigidas a preservação dos materiais em cortes sucessivos, a correspondência dos contatos entre peças com triangulações diferentes e a triangulação das superfícies poligonais para preparar pinos. A conclusão opera no espaço local do objeto, com testes de rotação, escala não uniforme e espelhamento.

## Evidências

- Nove novos testes automatizados: múltiplos contatos, três destinos da folga, cantos, recusa de faixa incompleta sem alterar a entrada, região côncava, transformações, seleção por faces, materiais e preparação de superfície poligonal para pinos.
- Placas simples e avançada: 24 combinações (quatro cores em cada placa, folga na peça, cavidade ou ambas). Todas produziram peças fechadas. Em 1.482 medições de folga nominal de 0,10 mm, o intervalo foi 0,09997345 a 0,10144488 mm.
- Fluxo completo: pinos e criação das peças nas duas placas; quatro cortes sucessivos na placa simples. Os três fluxos passaram.
- Gato real e superfícies para pinos: suíte de 16 testes aprovada, incluindo folgas de 0,10 e 0,20 mm e diferentes destinos da folga.
- A bateria inicial executou 87 arquivos de testes: 76 passaram e 11 falharam. Uma falha de consistência da versão foi corrigida. As outras dez foram reproduzidas na cópia original 0.8.35: não são resultados novos causados por esta alteração.

## Pendências históricas reproduzidas na 0.8.35

| Arquivo | Motivo observado |
| --- | --- |
| test_acceptance_0810_suite.py | Expectativa antiga dos nomes finais das peças |
| test_acceptance_etapa3.py | Expectativa antiga de conectores no modo sólido |
| test_commercial_audit.py | Expectativa de volume COM08 em profundidade escalonada |
| test_regressions.py | Duas expectativas antigas dos nomes das peças |
| test_regressions_0812.py | Guarda existente recusa cenário antigo de folga em profundidade |
| test_release_workflows.py | Cenários antigos de profundidade recusados pela guarda existente |
| test_smoke_phase1.py | Expectativa antiga para plano sem interseção |
| test_smoke_phase2.py | Nomes finais das peças |
| test_smoke_phase3.py | Nomes finais das peças |
| test_stress_phases0_3.py | Guarda existente para contato ambíguo no plano |

A suíte de região tem uma referência privada indisponível, explicitamente ignorada. Os registros detalhados e os modelos congelados de teste permanecem na pasta de desenvolvimento regiao-0.9.1, fora da pasta dos modelos do usuário.

## Limites

Não há garantia de tratar qualquer malha futura. Autointerseções, seleções ambíguas ou folgas geometricamente inviáveis devem continuar gerando erro explícito. A medição digital não substitui o teste de impressão e montagem. Nenhum arquivo de modelo original foi alterado nesta correção. A instalação não encerra a sessão aberta do Blender; ela precisa ser reaberta para carregar o código novo e as prévias antigas precisam ser regeneradas.
