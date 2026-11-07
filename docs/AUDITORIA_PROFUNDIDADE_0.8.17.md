# Auditoria da profundidade — 20/10/2026

## Escopo e método

Investigação do relato de informar 0,1 mm e obter uma peça de 2,1 mm. Código atual 0.8.17, Blender 5.2.0 LTS. Nenhum arquivo da extensão ou da instalação foi alterado nesta auditoria. Os testes ocorreram em cena de fábrica, sem modificar a cena aberta ou os modelos originais.

Foram medidas as coordenadas reais das malhas e o plano de contato. Não foram usadas distância da vista explodida, perspectiva ou dimensões globais de um objeto inclinado como substituto da profundidade. A reprodução sintética usa corpo de 10 mm e relevo de 2 mm. A reprodução real usa a geometria original do Arco preservada em `tests/fixtures/arco_frame.json`.

Resultados completos: `evidence/depth_audit_20261020/results.json` e `audit.log`. Foram executados 29 cenários: funções geométricas, captura pelas faces e operadores reais de prévia.

## 1. Relato exato reproduzido em Material e Loop

| Região escolhida | Profundidade informada | Espessura extraída medida | Base acrescentada abaixo do apoio |
| --- | ---: | ---: | ---: |
| Relevo inteiro de 2 mm — Material | 0,1 mm | 2,1000 mm | 0,1000 mm |
| Relevo inteiro de 2 mm — Loop | 0,1 mm | 2,1000 mm | 0,1000 mm |
| Relevo inteiro — ambos os modos | 0,5 mm | 2,5000 mm | 0,5000 mm |
| Relevo inteiro — ambos os modos | 1,0 mm | 3,0000 mm | 1,0000 mm |
| Somente face superior plana — ambos os modos | 0,1 mm | 0,1000 mm | 0,1000 mm abaixo dessa face |
| Moldura real do Arco — Material | 0,1 mm | 2,1000 mm | plano de corte em Y = -1,9000 mm |
| Moldura real do Arco — Material | 0,5 mm | 2,5000 mm | plano de corte em Y = -1,5000 mm |

Os resultados geométricos publicados nesses casos foram fechados e válidos. O valor de entrada não foi substituído por 2 mm. A operação preserva a superfície selecionada inteira e mede a profundidade abaixo do seu apoio. Assim, relevo de 2 mm + base de 0,1 mm = peça de 2,1 mm. Na seleção apenas do topo, o apoio é o próprio topo, e o resultado é uma lâmina de 0,1 mm.

Caminhos no código:

- `geometry_material.py:857`: regiões com relevo usam a extração por profundidade do Loop.
- `geometry_loop.py:2419`: determina o apoio a partir do limite inferior do contorno.
- `geometry_loop.py:2448`: identifica relevo e encaminha para destaque com base, passando a profundidade informada em `detach_base_depth_mm`.
- `geometry_loop.py:813`: calcula a profundidade dessa base, descontando a folga de fundo quando aplicável.
- `geometry_regions.py:162` e `:166`: nas molduras, profundidade abaixo do apoio é distinta da altura do relevo; a espessura disponível é a soma.

O problema de uso é real: o painel chama esse parâmetro genericamente de “Profundidade”, e a propriedade Material usa o nome “Profundidade da Peça”. Isso sugere espessura total, embora, numa seleção volumétrica, ele represente a profundidade adicional abaixo da base. Não é possível reduzir o relevo inteiro de 2 mm a uma espessura total de 0,1 mm preservando todas as suas superfícies.

## 2. Outros caminhos em que a profundidade tem efeito diferente

- Material / Pela Base destaca o relevo existente; a profundidade de extração não controla esse caminho. O caso sintético retornou exatamente 2 mm mesmo com `depth_mm=0.1` na chamada.
- Loop / Automático pode decidir Pela Base. Nesse caso, a profundidade usada para acrescentar material é `loop_detach_base_depth_mm`, se “Adicionar Base para Encaixe” estiver ativado. Esse parâmetro tem padrão de 2 mm (`properties.py:559`); é separado da profundidade de extração. O caso de relevo de 2 mm com base padrão de 2 mm resultou em 4 mm, não 2,1 mm.
- Material / Componente 3D fechado separa o componente já existente e não o recorta à profundidade informada (`geometry_material.py:797`). O painel ainda permite exibir Profundidade nesse caso. Isso pode parecer um parâmetro ignorado, embora a separação direta seja explícita no código.

## 3. Inconsistência real na validação de profundidades pequenas

Há condições legadas que comparam a folga de fundo com `profundidade - 0.1`:

- `geometry_material.py:1109`;
- `geometry_loop.py:2491`;
- `geometry_loop.py:808`, no destaque com base.

Isso reserva implicitamente 0,1 mm abaixo da profundidade nominal. A regra não está expressa no controle e não é uniforme: o motor de molduras considera a altura completa disponível da região e uma tolerância geométrica diferente. Além disso, a comparação na extração plana não trata folga zero antes de comparar.

Reprodução inequívoca da inconsistência numérica:

1. Região plana, profundidade exata `0.1`, folga lateral zero e fundo explícito `0.0`: funções Material e Loop recusam por “folga excessiva”. A condição vira `0 >= 0`.
2. Os mesmos valores pelos controles reais passam: o Blender armazena a profundidade como `0.10000000149011612`, e a condição passa a ser `0 >= 0.00000000149`, que é falsa.
3. Pelos controles reais, mudar apenas o fundo para `0.01` mm recusa tanto a região plana quanto o relevo de 2 mm, em ambos os modos. Não ocorre um aumento silencioso da espessura: ocorre uma recusa.

A diferença entre a função e o operador depender de arredondamento é um bug. A adequação da reserva física de 0,1 mm é uma decisão de produto; deve ser explícita e aplicada de modo coerente. Esse problema é separado da soma 2 + 0,1.

## Recomendações

1. Explicitar a referência da profundidade na interface. Para relevo inteiro: “Profundidade abaixo da base”; mostrar altura preservada e espessura final estimada na direção do corte.
2. Se for desejável controlar espessura total, oferecer uma referência diferente, como corte a partir da superfície. Não mudar silenciosamente a semântica atual, pois isso poderia truncar o relevo e quebrar os fluxos existentes.
3. Ocultar ou desabilitar profundidade quando Material estiver apenas separando um componente já fechado. No Loop AUTO, mostrar qual profundidade está efetivamente em uso.
4. Unificar as verificações de fundo por espessura restante real, lado de aplicação e tolerância física; tratar zero explicitamente. Manter a exigência de sólidos fechados e mensagens de erro quando não houver espessura suficiente.
5. Transformar os casos desta auditoria em regressões permanentes quando a correção for implementada, incluindo a equivalência função/operador em 0,1 mm.

Conclusão: o relato de 2,1 mm foi confirmado e explicado pela referência de apoio. Há ambiguidade na interface e uma inconsistência numérica de validação confirmada, mas não foi encontrado um piso fixo de 2 mm responsável pelo caso reproduzido. Nenhuma mudança no comportamento do corte foi feita nesta etapa.
