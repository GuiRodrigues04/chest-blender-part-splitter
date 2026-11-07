# Correção de profundidade — Part Splitter 0.8.16

Data: 20/10/2026. Ambiente verificado: Windows e Blender 5.2.0 LTS.

## Causa reproduzida

No arquivo recebido, `Cubo Teste 2`, material 1 (`Material.001`), região 0 de 112 faces e contorno de 30 vértices, a extração por Material ainda intersectava o objeto inteiro com uma coluna projetada do contorno. As paredes dessa coluna atravessavam a estrutura inclinada. As pontas fora da projeção permaneciam no corpo, formando fragmentos, embora a prévia indicasse sucesso.

O código atual de Loop já preservava essa estrutura nos cortes rasos. A correção anterior do Loop não era usada pelo caminho de Material. Os dois precisavam compartilhar a mesma interpretação da região volumétrica e da profundidade.

## Alterações

- Material com relevo usa o motor de região/profundidade do Loop: conserva a superfície escolhida inteira e adiciona a base dentro do corpo. Pinturas planas continuam com sua extração superficial.
- O motor recebe o contorno topológico original, sem transformar a seleção inteira em uma coluna que corta as pontas.
- O fallback projetado do Loop verifica vértices e arestas da tesselação visível da região. Recusa a projeção quando ela cortaria a estrutura, incluindo passagens por concavidades estreitas.
- No corte passante profundo, as faces retidas são divididas pelas diagonais visíveis originais antes da união da base. Isso impede que a união escolha outra triangulação de polígonos não planares e altere a superfície. A divisão nativa preserva dados de face e UV.
- Mantém materiais das faces originais. A interface de A respeita Corpo/Peça Extraída; a interface de B usa o material do corpo.
- Atualiza a explicação de Profundidade em PT/EN e identifica o pacote como 0.8.16.

Não foram relaxadas as validações de sólido, área ou espessura. As alterações anteriores do repositório foram preservadas; há uma cópia da base no diretório de evidências desta correção.

## Evidência no caso recebido

| Medida | Antes, Material 5 mm | Depois, Material/Loop 5 mm |
|---|---:|---:|
| Maior distância entre superfície escolhida e A | 43,330 mm sem folga; 43,624 mm com folga de 0,15 mm | 0,004301 mm ou menos nas amostras |
| Faces originais escolhidas preservadas em A | Região truncada | 112/112 |
| Vértices da região preservados em A | Resultado parcial | 138/138 |
| Componentes no corpo restante B | 3 | 1 |
| Altura máxima da estrutura em A | Pontas cortadas | 222,0136 mm, igual à fonte |
| Amostras da região encontradas em B | Sim | 0/976 |

Foram testados Material e Loop a 5 mm, com folgas 0 e 0,15 mm. O Loop foi testado também com a permissão de corte passante ligada e desligada. A folga na peça reduz seu fundo a 4,85 mm quando o valor nominal é 5 mm; B permanece a 5 mm. O maior erro medido de profundidade foi inferior a 0,000009 mm.

**Corte passante de 200 mm:** a união anterior alterava a superfície original em até 1,99144 mm, mesmo mantendo seus vértices. Depois da correção, as 976/976 amostras da superfície original permanecem em A, nenhuma em B, e ambas as partes são conectadas. O valor configurado continua em 200 mm; a geometria alcança a parede oposta real a 164,488626 mm. O teste compara a superfície inteira, não apenas a altura das pontas.

O teste de dados de malha confere UV por canto e atributos de face int/string em um polígono não planar. Os testes de proteção simulam a falha do caminho topológico e comprovam que a extensão não publica o corte por projeção inadequado nem deixa objetos temporários.

## Verificação final

**55/55 suítes passaram**, incluindo as duas novas suítes de região/proteção de profundidade. A verificação inclui os operadores reais da extensão, preservação de superfície e atributos, cortes sucessivos, folgas, encaixes, estado da prévia, exportação e reversão. A análise sintática dos arquivos Python e `git diff --check` também passaram. Os logs completos estão em `final_tests/summary.json` e nos arquivos individuais dessa pasta.

O pacote foi validado pelo comando oficial de extensões do Blender. O teste de pacote compara seus arquivos com a fonte, carrega a extensão em namespace isolado e exercita corte, exportação e reversão. As fixtures privadas e os arquivos de teste não entram no ZIP.

Pacote: `dist/chest_part_splitter-0.8.16.zip`.
SHA256: `1530541059455fdf73e0425ee9e4277cf7baa3bd2c26714f050e6040ebbc377c`.

## Arquivo de comparação

`COMPARACAO_PROFUNDIDADE_0.8.16.blend` no diretório de evidências mostra a fonte e a extração de Material a 5 mm em coleções nomeadas. É um arquivo derivado separado para inspeção; não substitui o arquivo de origem.

Instale o ZIP 0.8.16 e reinicie o Blender para testar a versão nova. Confira o número no painel. Refaça a seleção da região no arquivo anterior ao corte e gere uma prévia nova.

## Rastreabilidade

O arquivo recebido `Padrão Testes.blend` não foi salvo nem alterado. SHA256 preservado: `2bd8745ceb0ce855ded43097ff79ad8f2092823bfe0754a340a5ce6ba28c5410`.

Os logs, a reprodução anterior à correção, a comparação, a base e o manifesto de alterações estão em `C:/Users/guiro/.codex/visualizations/2026/10/19/01a15571-239e-7332-b9fe-22acb2b150db/depth_fix_2026_10_20`. A versão foi verificada no Blender 5.2.0; o manifesto continua com mínimo 4.2, que não foi revalidado nesta correção.
