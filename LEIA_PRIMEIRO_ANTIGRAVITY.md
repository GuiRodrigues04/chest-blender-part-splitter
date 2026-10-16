# Part Splitter 0.8.12 — instruções para o Antigravity

Este é o pacote completo de integração. Leia este arquivo antes de alterar o repositório.

## Objetivo autorizado

Integrar a versão 0.8.12 no repositório local da extensão, organizar os arquivos e instalar o ZIP correspondente no Blender local. Preserve todas as funções existentes e eventuais alterações locais posteriores à base fornecida. Não adicione recursos nem novos controles nesta tarefa.

## Conteúdo

- `repositorio/`: árvore pronta para a raiz do projeto da extensão, com `src/`, `tests/`, `scripts/`, `tools/`, `docs/`, `evidence/`, manifesto, licença e arquivos principais.
- `repositorio/dist/chest_part_splitter-0.8.12.zip`: ZIP instalável. Este é o arquivo a instalar no Blender.
- `repositorio/docs/RELATORIO_0.8.12.md`: correções, testes, referências e limites.
- `repositorio/docs/ALTERACOES_0.8.12.patch`: diferenças do código de execução em relação à base 0.8.11.
- `integracao/manifesto_arquivos.json`: caminhos relativos, ações e hashes da base e desta entrega.
- `integracao/MAPA_DE_INTEGRACAO.md`: lista organizada de arquivos alterados/adicionados.

**O ZIP externo não é uma extensão instalável. Extraia-o para integração; instale somente o ZIP em `repositorio/dist/`.**

## Base exata

A implementação foi feita sobre `chest-blender-part-splitter(3).zip`, identificado internamente como 0.8.11. Não use os anexos antigos 0.8.5/0.8.6 como base. O código desta entrega já contém as correções; não reimplemente o relatório como se fosse um plano.

## Integração no repositório local

1. Localize a raiz real da extensão pelo `blender_manifest.toml` com `id = "chest_part_splitter"`, junto de `__init__.py` e `src/`. A pasta pode ser um subdiretório de um repositório maior.
2. Leia as instruções locais do repositório, examine `git status` e preserve as alterações existentes. Use uma branch dedicada para a integração e registre o estado anterior sem descartar trabalho local.
3. Integre o **conteúdo** de `repositorio/` nessa raiz. Não crie uma pasta `repositorio/` dentro do projeto. O resultado esperado é `<raiz>/src/operators.py`, por exemplo.
4. Use o manifesto de arquivos para distinguir atualização e adição. Os hashes da base ajudam a detectar arquivos locais modificados desde 0.8.11. Diferenças apenas de CRLF/LF não são mudanças funcionais. Se houver trabalho posterior nos mesmos arquivos, faça a mesclagem preservando essas mudanças e as correções da 0.8.12; não faça substituição cega.
5. Não remova arquivos que não estejam no pacote. **Não há exclusões obrigatórias nesta entrega.** Preserve `.git`, arquivos de configuração locais, modelos `.blend`, assets, documentos antigos e código não relacionado.
6. Mantenha `evidence/` e os relatórios no repositório de desenvolvimento. Eles não devem entrar no instalador. Guarde o instalador em `dist/`, conforme a organização fornecida. Respeite a política local de versionamento de artefatos gerados.
7. Confira a versão 0.8.12 no manifesto, `__init__.py` e `src/constants.py`. Preserve o ID da extensão e a licença.

## Verificação local

Localize o executável real do Blender instalado no Windows, com preferência pela versão 5.2 usada pelo usuário. Os caminhos abaixo são exemplos de sintaxe, não caminhos a assumir:

```text
python tests/run_all_tests.py --blender "CAMINHO_REAL_DO_BLENDER.exe"
python scripts/build.py --blender "CAMINHO_REAL_DO_BLENDER.exe"
```

Execute a partir da raiz da extensão. O build oficial valida e gera `dist/chest_part_splitter-0.8.12.zip`. Se a integração incorporar mudanças locais adicionais, gere novamente o instalador; não instale o binário fornecido como se contivesse essas mudanças.

As 44 suítes foram aprovadas nas APIs oficiais bpy 4.2.23, 4.5.3 e 5.0.1 em Linux. Os registros estão em `evidence/`. Esta evidência não substitui os testes locais no Blender 5.2/Windows. Não declare testes executados se não houver execução real.

## Instalação

Instale o ZIP de `dist/` usando o mecanismo oficial de instalação de extensões do Blender. Pela interface: Preferences > Get Extensions > menu > Install from Disk. Atualize a extensão existente de mesmo ID e confira o painel Part Splitter 0.8.12 em N > Chest. Se for necessário reiniciar/recarregar o Blender para descarregar a versão anterior, faça isso preservando a cena em uso.

Os scripts antigos `tools/install_to_blender.py` e `tools/build_and_install.py` têm caminhos específicos do ambiente original. Não os execute automaticamente nem assuma que esses caminhos correspondem ao computador atual. Prefira o build oficial e a instalação oficial; adapte um utilitário local apenas se necessário e de forma explícita.

## Teste visual obrigatório antes de considerar a instalação validada

- Capturar contorno/perímetro, iniciar Manual e colocar quatro pinos fora de uma única linha.
- Mover pinos livremente e soltar um arraste fora do viewport; conferir que o arraste terminou.
- Cancelar uma edição iniciada sem pinos e conferir que a lista volta a ficar vazia.
- Gerar prévia, reabrir o editor e gerar novamente sem perder o loop. Repetir em Plano e Material.
- Conferir a grade de 5 mm apenas durante a edição, sem snap ou controles extras.
- Trocar macho A/B e conferir direção dos pinos/cavidades.
- Mover/rotacionar o guia e conferir linha de corte e explosão; testar também cortador sólido lateral.
- Confirmar, reverter, salvar/reabrir e exportar uma peça de teste.

Não altere silenciosamente validações para fazer um teste passar. Limitações conhecidas, incluindo pinos em superfícies não planas e textos dinâmicos antigos ainda não integralmente revisados em PT/EN, estão no relatório.

## Resposta de conclusão ao usuário

Informe a raiz atualizada, os arquivos mesclados, o ZIP instalado, a versão de Blender efetivamente usada, os testes executados e qualquer pendência. Não faça commit, push ou publicação externa sem autorização correspondente.
