# Chifre da Spot — pino central rejeitado — 2026-11-08

## Conclusão

O domínio usado para posicionar pinos está sendo reduzido a uma pequena região
coplanar do fechamento, em vez de representar a superfície de contato inteira.
O modo CENTER centraliza nessa região menor. O editor manual também usa essa
mesma região, de modo que um centro geometricamente viável é marcado como
fora da peça ou sem margem. A opção de ajuste busca pontos nessa região
incorreta; ela não consegue recuperar o contorno que já foi descartado.

Não é necessário estragar ou achatar o corte nem retirar a folga para resolver
essa questão. O erro comprovado está na representação da área de encaixe.

## Reprodução e medidas

Fonte local: `spot/spot/Vaquinha.blend`, objeto `spot_quadrangulated`.
Loop: `[424,1648,425,1641,423,1659,427,1653,426,1669,429,1663,428,1677,430,1672]`;
semente 958. A configuração salva do tutorial no outro computador não foi
fornecida; reproduziu-se a falha na mesma malha, com um loop de chifre conhecido,
e também em escala menor próxima às dimensões mostradas nas imagens.

| Medida | Escala original do arquivo local | Ensaio com fator 0,4 e folga 0,1 mm |
| --- | --- | --- |
| Seção projetada | 34,66 × 27,94 mm | 13,86 × 11,17 mm |
| Área do contorno projetado completo | 742,81 mm² | 118,85 mm² |
| Área que o posicionador considera disponível | 35,06 mm² | 10,16 mm² |
| Fração da área preservada pelo posicionador | 4,72% | 8,55% |
| Centro nominal no domínio atual | Rejeitado | Região disponível reduzida a uma faceta |
| Distância do centro ao contorno completo | 12,80 mm | 5,12 mm |

Na escala original, o pino CENTER saiu aproximadamente 6,49 mm para o lado em
relação ao centro nominal do loop. Um pino de diâmetro 1 mm, com folga lateral
0,1 mm e margem 0,4 mm, exige raio de segurança de 1 mm. O centro é recusado
por estar na borda da faceta escolhida, embora tenha espaço no corte completo.

## Caminho que produz a falha

1. `geometry_loop.slice_mesh_by_loop.complete`: para fechamento natural com
   desvio maior que 0,15 mm, chama `paired_contact_patches`.
2. `geometry_clearance_blade.paired_contact_patches`: agrupa as faces em
   regiões estritamente coplanares e conserva apenas o maior par compatível.
   Uma leve curvatura ou a tesselação de uma grade pode virar muitas facetas.
3. `connector_surface.cache_prepared_interface`: substitui os contornos e
   triângulos da interface pelos da faceta escolhida. Essa é a perda decisiva
   do domínio completo para layout e picking manual.
4. `geometry_connectors.compute_connector_layout`: CENTER é o centro da
   caixa 2D dos contornos recebidos. Portanto calcula corretamente o centro
   do domínio errado, e não o centro do corte.
5. `connector_surface.evaluate_connector_specs`: valida os pinos manuais
   contra os mesmos contornos reduzidos. A mensagem de margem não significa
   que o centro esteja perto da borda real do chifre.

Também existe o caminho anterior `geometry_clearance.final_contact_patch`, que
seleciona uma única região plana após a folga. Corrigir somente a seleção do
par novo não cobre todos os modos que compartilham esse comportamento.

## Prova geométrica isolada

`center_proof.py` mantém as peças realmente cortadas e testa o centro do
contorno completo, usando os triângulos reais para obter o apoio. Continua
checando a parede receptora e realizando os Booleans dos pinos e cavidades.
Não modifica `src`, não instala uma versão e não salva sobre o arquivo original.

Foram 18 combinações: três condições de escala/folga, macho A/B e três
dimensões. Dezesseis produziram duas peças válidas, fechadas, com uma componente
cada. Duas foram corretamente recusadas por falta de profundidade na peça
receptora. O pino central de 1 × 8 mm funcionou nas seis condições de lado,
escala e folga verificadas; não há fundamento para rejeitar seu centro por
margem no ensaio reproduzido.

Na seção menor, um pino de 2 × 3 mm funcionou com macho A ou B, sem folga e
com folga de 0,1 mm. Já o padrão de 6 × 8 mm, quando a cavidade entra no
chifre menor, exige 8,1 mm e encontra apenas cerca de 7,57 mm. Essa é uma
restrição real de profundidade, diferente da falsa rejeição do centro.

Limite da prova: o ensaio de Boolean usa uma cópia privada da malha sem UV,
para isolar a geometria. A varredura inicial encontrou uma exceção independente
no restauro de UV em uma tentativa com fator 0,25 e folga 0,1 mm
(`geometry_loop._restore_retained_source_faces`, `uv.data` com tamanho zero).
Isso está preservado em `probe_results.json` e precisa de verificação separada
na futura correção. A prova não valida o fluxo completo com texturas nem
constitui uma correção pronta para instalação.

## Correção recomendada

- Representar o domínio completo comum das duas superfícies de contato,
  preservando furos e contornos. Unir facetas vizinhas no domínio projetado
  adequado; não exigir que o encaixe inteiro caiba numa única face plana.
- Manter os triângulos físicos para localizar o apoio, a entrada na cavidade,
  o material disponível e a interseção efetiva do pé do pino. Não ampliar
  cegamente o domínio: projeções com sobreposição, dobras ou vazios precisam
  continuar verificadas na geometria real.
- Preferir um centro estável do domínio completo. Se ele couber, mantê-lo.
  Em contornos côncavos ou com furos, procurar outra posição válida somente
  quando necessário, com uma razão concreta para o deslocamento.
- Compartilhar contorno, margens, furos e colisões entre CENTER, ajuste,
  editor manual e geração. Um pino central pode atravessar arestas internas
  da grade; essas arestas não são bordas externas nem furos.
- Preservar um eixo comum de inserção para múltiplos pinos. Trocar a normal
  de cada pino independentemente numa superfície curva pode prejudicar a
  montagem, mesmo que cada Boolean isolado funcione.

## Sugestão inicial de dimensões

Os valores atuais são fixos: diâmetro 6 mm e profundidade 8 mm em
`properties.py`. O layout conhece margens e diâmetro, mas a verificação de
profundidade ocorre mais tarde, antes do Boolean da cavidade.

Uma proposta de partida, ainda a calibrar e validar em diferentes modelos:

1. Obter um centro viável no domínio correto. Medir sua distância real às
   bordas e aos furos e calcular `D_limite = 2 × (distância − margem − folga
   lateral)`. Não usar apenas o retângulo envolvente da seção.
2. Escolher um diâmetro inicial moderado, por exemplo 20% da dimensão menor
   da seção, limitado pelo valor acima e pelos limites de fabricação escolhidos.
   Um mínimo de 1 mm deve ser apresentado como limite do recurso, não como
   garantia universal de resistência de uma peça impressa.
3. Medir material disponível no centro e ao redor de toda a cavidade, no
   lado receptor, considerando também a fixação do pino no lado macho.
4. Começar com uma profundidade moderada, por exemplo 1,5 vezes o diâmetro,
   limitada pelo material disponível, pela parede residual e pela folga de
   fundo. Reavaliar a espessura ao mudar o diâmetro: uma cavidade mais larga
   pode atingir a parede inclinada antes da linha central.
5. Repetir a validação rápida e arredondar para valores fáceis de ajustar.
   Sem espaço para o mínimo, informar isso antes de gerar a prévia.

No ensaio de aproximadamente 14 × 11 mm, essa regra experimental sugeriu
diâmetro 2 mm e profundidade 3 mm, e os Booleans centrais passaram em ambos
os lados. Esse exemplo não é uma recomendação de resistência mecânica.

Na interface, aplicar a sugestão ao habilitar pinos ou por uma ação de
“Sugerir dimensões”. Depois que o usuário personalizar os números, preservar
essa escolha. Ao trocar o corte, atualizar sugestões/limites sem sobrescrever
silenciosamente valores manuais. Mostrar insuficiência de área ou profundidade
antes de um erro tardio na geração da prévia.

## Próximos testes da implementação

Chifre em escalas distintas, folga zero/0,1 mm, macho A/B; centro em superfície
plana, triangulada e quadriculada; pino sobre arestas internas da grade;
contorno com furo e contorno côncavo; comparação manual/CENTER; profundidade
insuficiente real; mudança de corte sem perder valores personalizados; UV;
regressão do pé da Spot e dos cinco modos de corte. A centralização precisa
ser verificada explicitamente, além de validar fechamento e volume.

A extensão instalada permanece na 0.9.7 durante este estudo.

## Referências consultadas

- [API oficial BVHTree do Blender](https://docs.blender.org/api/current/mathutils.bvhtree.html):
  oferece consultas de proximidade e raios sobre os triângulos físicos,
  adequadas para verificar apoio e parede sem reduzir a região a um plano.
- [Mapbox Polylabel](https://github.com/mapbox/polylabel): busca o ponto
  interior mais afastado do contorno dentro de uma precisão definida. É uma
  referência para a busca de margem quando o centro preferido não couber;
  não resolve sozinho o domínio físico 3D ou a profundidade do encaixe.
  Usá-lo como fallback geométrico é uma proposta deste estudo, não uma
  funcionalidade atualmente implementada no Splitter.
