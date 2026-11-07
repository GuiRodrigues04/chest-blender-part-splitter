# Correção de apoio da moldura Osso

O bloqueio era gerado em region_support por exigir planaridade em todos os contornos. O contorno externo é planar, mas o interno varia aproximadamente 1 mm na placa original. O eixo passa a ser validado no contorno externo, mantendo o apoio na maior profundidade dos contornos. A tolerância de 0,25 mm do contorno de referência não foi ampliada.

Preservadas as verificações de projeção, cruzamento, altura, espessura disponível, validade das peças e conservação de volume. O arquivo original não é salvo nem alterado.

Validação: test_stepped_frame_support.py (4 testes), test_frame_regions.py e test_clearance_profiles.py aprovados. Placa real: material 0, profundidade de 2 mm, preset FDM, sem conectores; prévia e confirmação com duas peças fechadas e volumes iguais. Modelo sintético cobre base e profundidade, sem folga e com folga em PART/CAVITY/BOTH, captura por Loop e recusa de contorno externo não planar.
