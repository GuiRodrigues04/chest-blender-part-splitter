# Validação da candidata 0.8.15

Data: 19/10/2026. Ambiente: Windows, Blender 5.2.0 LTS (`fbe6228777e7`).

## Escopo e estado

Candidata para testes de lançamento. Implementação coordenada com três agentes GPT-6 Luna em esforço high: geometria, encaixes e validação independente. A integração e as verificações finais foram feitas no repositório principal.

A base inicial era o commit `06c0084`, com alterações locais anteriores em seis arquivos. Foi preservada uma cópia dessa base, inclusive das alterações locais. O diff contra HEAD também inclui trabalho anterior; não representa somente esta implementação. Nenhum commit, publicação ou instalação no perfil ativo do Blender foi realizado.

## Problemas relatados e resultado

| Problema | Tratamento | Evidência |
|---|---|---|
| Folga por Loop inclina as faces vizinhas ao canto | Restrições dos planos externos, reconstrução local de cantos convexos e criação de vértices quando necessário | Caso original reproduzido; quadro de medidas abaixo |
| Região vermelha falha no Loop | AUTO detecta fechamento que cruza a superfície e usa a profundidade configurada; EXTRUDE usa tesselação consistente nas booleanas | Dois corpos reais, profundidades de 1, 2, 5, 10 e 15 mm |
| Região irregular por Material | Extração por profundidade com apoio planar; tesselação consistente; remoção limitada de degenerações numéricas conectadas | Raios contra A/B, dois corpos, cinco profundidades e folga de 0,15 mm em 5/10 mm |
| Erros em português com interface em inglês | Códigos e parâmetros de diagnóstico localizados ao apresentar, preservados ao trocar idioma | Testes PT/EN e instalação isolada do ZIP |

A região vermelha não possui um fechamento direto seguro: a tampa nominal atravessa a superfície existente. Esse fechamento é recusado. Para o resultado solicitado, use **Profundidade**; o Loop automático usa o valor configurado. Material **Na Base** continua exigindo base planar.

Na extração irregular com apoio planar, a profundidade parte do apoio até o fundo plano. A espessura até cada depressão ou saliência da superfície pode variar. Não houve limitação silenciosa do valor escolhido nos casos medidos.

### Medidas do canto original

Região de três faces do Cube.001, contorno de seis vértices, folga aplicada à cavidade. Foram comparadas as faces externas com seus planos e normais originais, independentemente do indicador manifold.

| Folga | Desvio externo anterior | Inclinação anterior | Desvio na candidata | Inclinação na candidata |
|---|---:|---:|---:|---:|
| 3 mm | 1,732051 mm | 5,254863 graus | 0 mm | 0 graus |
| 5 mm | 2,886750 mm | 9,274533 graus | 0 mm | 0 graus |

Ambas as peças passaram na validação de sólido fechado. O corpo preservou as 381 faces externas identificadas pela origem. A matriz de regressão inclui variações de canto/degrau, malhas trianguladas, rotação, escala não uniforme, Peça/Cavidade/Ambos e folgas até 5 mm.

### Medidas de profundidade

Loop AUTO: 20 combinações dos dois corpos, profundidades 1/2/5/10/15 mm e folgas 0/0,15 mm; fundo verificado com tolerância de 0,01 mm.

Material EXTRUDE: cinco profundidades nos dois corpos, com folga adicional de 0,15 mm em 5/10 mm. Medição por raios em 28 amostras da tesselação visível, em coordenadas montadas. Maior erro observado: **0,00000875 mm**, abaixo da tolerância de 0,01 mm. Para 5 mm com folga na peça de 0,15 mm, o fundo de A ficou a 4,8499913–4,8500034 mm do apoio, conforme o valor esperado de 4,85 mm.

O caminho genérico de extração pela superfície também recebeu regressão: as tampas do cortador seguem os triângulos visíveis da fonte, inclusive em quads não planares, nas profundidades 1/2/5/10/15 mm.

## Outras correções verificadas

- Pinos usam as superfícies finais de contato e mantêm a referência de posicionamento ao trocar lado macho ou alterar folga; furos permanecem fora do domínio válido.
- Exportação bloqueia prévias incompletas, inválidas ou desatualizadas; a execução faz verificação completa novamente.
- Falhas tardias de prévia recuperam os objetos e malhas anteriores, métricas e visibilidade. A prévia recuperada fica inválida até atualização.
- Modificadores entram na assinatura avaliada da geometria. Ocultar visualmente o alvo mantém a avaliação ativa.
- Caches de interface acompanham revisões da malha; análise em Edit Mode não escreve nos datablocks durante desenho.
- Testes de falha, confirmação, continuação, reversão e exportação conferem preservação da fonte.
- Validação de confirmação/exportação libera BMesh e malhas avaliadas mesmo quando ocorre exceção.

## Execução automatizada e pacote

**53/53 suítes concluídas sem falhas** na rodada completa. Após o ajuste final de liberação de malhas temporárias, as oito suítes afetadas foram repetidas e passaram, incluindo os 10 testes de estado e o carregamento isolado do ZIP final. Há suítes unittest e scripts com verificações próprias; o número de suítes não corresponde ao número total de asserções.

Também passaram a análise sintática dos arquivos Python, `git diff --check` e a validação oficial do manifesto/pacote pelo Blender. Logs completos: `release_frozen_tests` e `final_cleanup_tests` na pasta de evidências.

O teste do pacote compara cada arquivo do ZIP com a fonte, verifica conteúdo permitido, carrega a extensão em namespace isolado, alterna PT/EN e realiza corte, confirmação, reversão e exportações STL/3MF/OBJ com releitura das dimensões em coordenadas montadas.

O ZIP inclui código, manifesto, licença, README, changelog e guia rápido PT/EN. Não inclui cenas privadas, fixtures, logs, testes ou documentos internos.

Artefato: `dist/chest_part_splitter-0.8.15.zip` (264767 bytes). SHA256: `bc10157e36eb33507c5bcb7ac370e7d945b05ce46e26b7404f7d09a304906905`.

Reprodução no repositório: execute `python scripts/build.py` e depois `python tests/run_all_tests.py --report-dir CAMINHO_DO_RELATORIO`. O runner usa Blender separado para cada suíte e retorna erro se qualquer suíte falhar.

## Verificações antes da venda

1. Repetir os casos das imagens pela interface com a candidata instalada, incluindo pinos manuais, atualização de prévia e cortes sucessivos.
2. Testar personagens e modelos com depressões, paredes finas, concavidades e malhas densas. Registrar resultado esperado e parâmetros junto ao `.blend` anterior ao corte.
3. Abrir os arquivos exportados nos fatiadores que serão anunciados e conferir escala, posição montada, materiais e ausência de reparos inesperados.
4. Imprimir uma amostra representativa de encaixe e folga com o processo pretendido.
5. Testar cada versão de Blender anunciada como compatível. O manifesto mantém mínimo 4.2, mas esta execução valida somente **5.2.0 LTS**.

A validação automatizada cobre os casos descritos e suas variações; não demonstra funcionamento em toda topologia arbitrária. A candidata está preparada para a próxima rodada de testes comerciais, com as verificações manuais acima ainda pendentes.

## Preservação e rastreabilidade

O arquivo original `Padrão Testes.blend` permaneceu sem alterações. SHA256 verificado: `c9d3a6986599f1e6d8cd1ddd835aae3939cb322b0df2b53d846001d63871bf2c`.

Os logs, a base inicial, as medições antes/depois e os manifestos de hashes estão na pasta de evidências `implementation_0815` associada a esta conversa. O manifesto final identifica os arquivos alterados em relação à base capturada no início.
