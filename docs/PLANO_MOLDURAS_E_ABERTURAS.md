# Plano — extração de molduras e regiões com aberturas

## Objetivo

Extrair a borda clara da placa Arco como sólido separado, preservando a área central no corpo receptor. Reutilizar esse suporte em Material e captura pelas faces do Loop. Manter folgas nas paredes internas/externas e impedir pinos nas aberturas. Corrigir o reparo destrutivo que dificulta o diagnóstico.

## Etapas

1. **Domínio e identificação:** distinguir uma região conexa com contorno externo e aberturas internas de ilhas desconectadas e contornos inválidos. Preservar o formato selecionado, sem preencher o centro. Manter compatibilidade com a extração de uma região simples.
2. **Extração:** acrescentar um caminho compartilhado para molduras com apoio planar. Gerar sólidos fechados para extração pela base e por profundidade; preservar cores, centro receptor, fonte original e conservação de volume quando não há folga.
3. **Interface, folgas e pinos:** publicar os contornos externos e internos no contrato de corte. Aplicar o deslocamento de ajuste nos dois lados da moldura, mantendo o fundo independente. Reutilizar os validadores de posição dos pinos, que já conhecem furos. Recusar ajustes que colapsem a borda e posições sem material suficiente.
4. **Loop e interface:** capturar todos os contornos de uma única região selecionada com aberturas. Não confundir furos com ilhas selecionadas. Mostrar e armazenar os contornos completos; encaminhar o corte ao mesmo motor usado por Material.
5. **Reparo seguro:** trabalhar em cópia, usar tolerância física conservadora, validar o candidato antes de publicar, retornar corretamente ao Edit Mode e não prometer cura para falhas que a soldagem não resolve.
6. **Validação e entrega:** usar a placa Arco real e geometrias sintéticas com uma e várias aberturas, além das regressões existentes. Conferir base/profundidade, contorno central preservado, sólidos fechados, folgas, pinos, rollback e instalação. Reconstruir o pacote e atualizar a instalação somente após os testes.

## Limites de aceitação

- Contornos que se cruzam, seleção realmente desconectada, regiões sem apoio/projeção válida, espessura insuficiente e folgas que colapsem detalhes continuam produzindo erro explicativo.
- Não remover verificações de manifoldness ou área para fazer um caso passar.
- Não modificar a cena aberta nem os modelos originais durante os testes.
- Preservar os reparos anteriores de contornos e pinos e as mudanças do Antigravity.

## Evidências

Todas as seis etapas concluídas: implementação, 59 suítes aprovadas, regressões finais, conferência visual, pacote e instalação com backup. O [relatório de validação 0.8.17](VALIDACAO_0.8.17.md) registra casos, logs e limites. A validação geométrica não equivale a um teste físico de impressão.
