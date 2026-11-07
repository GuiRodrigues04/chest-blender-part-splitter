# Part Splitter 0.8.13 — instruções para Antigravity

Este pacote contém código implementado e testado, não apenas um plano. A base foi o ZIP 0.8.12 enviado pelo usuário. Leia `repositorio/docs/RELATORIO_0.8.13.md`, `repositorio/docs/CASOS_REPORTADOS.md` e `repositorio/docs/USO_SOLIDO.md`.

## Integração no repositório local

1. Localize a raiz do repositório pelo `blender_manifest.toml` com id `chest_part_splitter`. Preserve alterações locais, arquivos .blend, assets, documentação própria e histórico git. Não substitua a pasta inteira nem crie uma pasta `repositorio` dentro do código existente.
2. Compare os arquivos com `integracao/manifesto_arquivos.json`. Os hashes da base 0.8.12 permitem identificar divergências. Aplique o conteúdo de `repositorio/` à raiz real; se houver mudanças locais diferentes da base, faça merge cuidadoso usando `integracao/alteracoes_0.8.12_para_0.8.13.diff`. Não reverta correções locais nem remova arquivos que não aparecem neste pacote.
3. Arquivos `manter` são cópias idênticas da base. Arquivos `atualizar` e `adicionar` devem ser revisados/integrados. Não há remoções obrigatórias. Verifique também que todos os locais de versão indiquem 0.8.13. O manifesto conserva o mesmo identificador da extensão.
4. Execute os testes em processo separado e cena de fábrica. Com módulo bpy: `python tests/test_regressions.py`. Com Blender: `blender --background --factory-startup --python tests/test_regressions.py -- "/caminho/da/raiz"`. A suíte cria e remove objetos de teste, portanto não deve ser executada na cena de trabalho. São 49 testes, já aprovados em cada um dos runtimes 4.2.23, 4.5.3 e 5.0.1.
5. Se integrar qualquer alteração adicional no código, reconstrua com `python scripts/build_installer.py`. O instalador pronto está em `repositorio/dist/chest_part_splitter-0.8.13.zip`. `python tests/smoke_installer.py`, em Python com bpy, testa o ZIP sob o namespace de extensão do Blender.
6. Instale o ZIP interno pelo Install from Disk do Blender. O ZIP externo que você está lendo não é instalável. Não use scripts antigos de instalação que contenham caminhos específicos de outro PC.

## Conferência final no Windows / Blender 5.2

Abra cópias das peças originais e confira os 14 casos relatados. Teste cliques/arraste, Enter/Esc, mudança de região, cancelar e reabrir prévia, giro de cápsula, mudança de macho, exclusão do cortador, folga de Sólido e alinhamento de vértices. Confirme que a grade acompanha a face selecionada e que o resultado no fatiador continua correto.

Esses testes visuais ainda não foram executados neste ambiente. As imagens anteriores estavam indisponíveis e não havia .blend dos últimos relatos. Não anuncie ausência total de bugs ou homologação comercial apenas pelos testes automatizados. Preserve as checagens que recusam sólidos abertos, paredes insuficientes, projeções sobrepostas e offsets que colapsam detalhes.
