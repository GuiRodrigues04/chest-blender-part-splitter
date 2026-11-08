# Splitter 0.9.8 — resultado da verificação

## Alterações

- Domínio completo comum para pinos em fechamentos naturais compatíveis, conservando os triângulos físicos de cada peça. A grade e a folga do corte não são achatadas para acomodar o pino. Furos e margens continuam ativos; projeções dobradas/verticais conservam o caminho local anterior.
- CENTER usa o centroide de área desse domínio; o editor manual usa os mesmos contornos. No chifre pequeno, o deslocamento do centro caiu de 1,356 mm na baseline para cerca de 0,00423 mm após a folga.
- Sugerir dimensões mede os sólidos cortados, o contorno e a profundidade receptora por amostragem. Na seção de 13,86 × 11,17 mm, a sugestão foi 2 × 3 mm, aprovada com macho A e B.
- A ativação pelo painel lateral pode sugerir valores iniciais ainda não personalizados. Arquivos existentes, scripts, console e valores personalizados conservam suas dimensões. Edições feitas enquanto uma sugestão está agendada são preservadas.
- O restauro de UV faz uma cópia dos atributos de canto antes de alterar a topologia, evitando a coleção antiga invalidada no Blender 5.2. Teste de UV confere valores nos polígonos intactos, além da presença da camada.

## Bateria dirigida, menor que a anterior

| Comparação | Suítes | Métodos declarados | Falhas / erros | Pulados |
| --- | --- | --- | --- | --- |
| 0.9.7 congelada em dc49770 | 12/12 aprovadas | 93 | 0 / 0 | 1 |
| 0.9.8 | 13/13 aprovadas | 100 | 0 / 0 | 1 |

O teste pulado procura objetos privados antigos de referência de patas que não existem na cena disponível. A pata real do gato foi testada separadamente pelo fluxo público: Material / Região inteira, slot 4, contato 0, dois pinos de 8 × 12 mm e folga de 0,1 mm.

As suítes cobrem quads, os cinco modos de corte, folga física, fechamento natural, geometria de degraus/cantos existente, interfaces, quadros de pinos, editor manual, histórico, estado dos conectores, regiões e materiais. Os sete métodos novos verificam contato curvo completo, centralização e equivalência manual; furo preservado; dimensões sugeridas e parede insuficiente; unidades físicas; UV; valores personalizados e agendamento interativo.

Relatórios: `baseline.json`, `current.json`; runner `scripts/run_regression_098.py`. A baseline foi executada no checkout congelado `scratch/baseline098`, não no código atual. A última repetição isolada da suíte nova e a verificação instalada também cobrem o filtro para que o console não acione sugestões automáticas.

## Modelos reais

**Onze cenários finais aprovados na 0.9.8.** Placa por Região inteira e por Loop de faces/Destacar; pata do gato com pinos; chifre da Spot com centro, manual válido e sugestões para os dois lados; pé da Spot com folgas de 0,1 e 1 mm e pinos de 6 × 8 mm. Todos os resultados verificados têm duas peças, volume positivo, nenhuma aresta não manifold e uma componente por peça. Originais não foram salvos nem alterados no disco.

Na baseline, oito desses cenários passam, o critério novo de centralização acusa o bug do chifre e as duas sugestões são classificadas como recurso ausente. Não se contam como regressões de funcionalidades existentes. Detalhes em `REAL_MODELOS.md`, `baseline_final.json`, `current_final.json`, `summary_final.json`.

Uma tentativa adicional de Loop / Profundidade de 1 mm na região azul da placa foi recusada por dezesseis arestas nulas em ambas as versões (`known_blue_depth.json`). Essa limitação anterior foi registrada e não corrigida. A bateria reduzida também não reexecutou integralmente os 23 casos históricos de falha em `test_release_workflows.py` já documentados na 0.9.7; não há afirmação de que todos os problemas históricos tenham sido resolvidos.

## Pacote e instalação

- Pacote: `dist/chest_part_splitter-0.9.8.zip`, validado pelo comando oficial de extensões do Blender.
- SHA-256: `012d4374c4e4ea60c47b223598efffa78ffabee2b3b1f37f9e670fe7601a1788`.
- `test_release_package.py`: dois testes aprovados, com namespace isolado, bytes iguais aos fontes, versão, idiomas, exportação e reversão.
- Instalação local atualizada no Blender 5.2 após backup da 0.9.7; `verify_installed.py` confere bytes idênticos ao ZIP e versão real, exercita cinco modos de corte e os sete testes novos pelo código instalado.
- Nenhuma preferência do Blender foi salva. Uma sessão que já estava aberta precisa ser reiniciada e a prévia deve ser gerada novamente.

A publicação é uma candidata para validação, com ZIP instalável no GitHub. Os testes validam geometria e prévia, sem ensaio físico de impressão/montagem.
