# Placa QR Inclinada — diagnóstico

A rotina de coincidência reconstruía as regiões descartando conexões topológicas quando uma microaresta tinha os extremos agrupados no mesmo cluster. Material 0: 3 regiões reais [443, 2, 4] eram reportadas como 46 regiões [404, 1, ...]. A região principal ficava com três vértices de grau 4 no contorno. A correção preserva as uniões topológicas antes de acrescentar uniões geométricas. Agora a região principal é reconhecida como válida; o teste sintético reproduz a falha anterior.

O corte completo ainda é recusado corretamente: embora a fonte seja manifold, a validação estrita aponta 5 microfaces abaixo de 0,000001 mm² (149, 236, 440, 1802, 1803). O saneamento conservador não conseguiu gerar um candidato totalmente válido e retorna False. Não relaxamos validações nem alteramos o arquivo original. Com profundidades de 0,10 mm e 2 mm, o próximo bloqueio é a geometria original inválida.

A captura mostra profundidade 0,10 mm e folga 0,10 mm; esses valores devem ser revistos após a recuperação da fonte, pois a folga de fundo pode consumir a camada extraída. Nenhuma alteração de profundidade foi aplicada automaticamente.

Regressões aprovadas: test_material_region_connectivity.py, test_release_interface.py, test_frame_regions.py. A correção de agrupamento está instalada, mas não significa que o corte completo desta placa foi validado.
