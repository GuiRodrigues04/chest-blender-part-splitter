# Arquitetura

O arquivo raiz __init__.py delega o registro para src. O manifesto declara versão, requisitos e identidade da extensão.

| Módulo | Responsabilidade |
|---|---|
| properties.py | Estado persistente e parâmetros |
| operators.py | Operadores, pipeline da prévia e handlers |
| lifecycle.py | Operações, backups e reversão |
| geometry_*.py | Corte, interfaces e encaixes |
| diagnostic.py | Unidades e análise das malhas |
| gpu_drawing.py | Sobreposições na viewport |
| io_export.py | Exportação |
| ui.py / translations.py | Painel e textos |

Manter src plano nesta revisão reduz alterações de imports durante a estabilização. Separar operadores em módulos menores somente quando os testes protegerem o fluxo completo. Documentos em archive são históricos; não substituem o código nem o plano atual.

Uma prévia nova deve ser construída como candidata, validada e promovida junto ao registro de operação e backup. Falha deve preservar toda a operação anterior. Remoção de objetos exige identidade inequívoca da operação, nunca apenas nome ou função.
