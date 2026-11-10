Splitter 0.9.9 corrige a construção da folga em extrações com profundidade.

O fechamento da ferramenta preserva contornos anulares. Uma pequena sobreposição apenas no exterior do cortador evita que o Boolean conserve paredes coincidentes; a superfície interna continua definindo a folga nominal.

No olho da Spot, com profundidade de 5 mm e folga de 0,1 mm, 208 amostras laterais mediram 0,099993–0,100005 mm e 96 amostras de fundo ficaram próximas de 0,1 mm. O arquivo original foi preservado.

A auditoria inclui os cinco modos de corte, placas, pata do gato, Spot, encaixes, histórico e exportações. Consulte os relatórios em evidence/0.9.9 para cobertura e limitações. O modo de cortador sólido divide o modelo sem criar conectores. A tentativa de quadricular e a triangulação segura continuam disponíveis.

Validação final: 99 testes na bateria principal (uma referência privada ignorada), 53 na complementar (três referências ignoradas). A complementar ainda apresenta dez subcasos falhos em uma comparação de assinatura exata entre prévias; uma reprodução medida mostrou equivalência física, mas os demais nove não foram medidos individualmente. Por essa ressalva, esta publicação é uma prévia de validação, sem declaração de aprovação integral.

Após instalar, reinicie o Blender e gere novamente a prévia. Peças já confirmadas não são reescritas automaticamente.
