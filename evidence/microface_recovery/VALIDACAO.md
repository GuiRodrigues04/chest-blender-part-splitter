# Investigação e reparo de microfaces — 2026-10-21

Na placa QR Inclinada, três das cinco faces antes rejeitadas apenas por área são pequenos triângulos bem formados. O critério passou a exigir, além da área pequena, altura abaixo da tolerância física existente de 0,0001 mm; vértices coincidentes e arestas nulas continuam rejeitados. Diagnóstico e motor agora usam a mesma validação.

As duas faces quase colineares restantes são saneadas localmente numa cópia. Na amostra real: 1886 -> 1884 faces, mesmos 945 vértices, sólido fechado. Alteração medida de volume: cerca de -0,0000002683 mm³; alteração de área por material: aproximadamente -0,0000005236 mm² e +0,0000000200 mm². Não há remalhagem global, preenchimento de buracos nem suavização.

A aceitação exige validade e fechamento estritos, limite de volume max(0,00001 mm³, volume*1e-8), áreas por material max(0,000001 mm², área*1e-10), mesmos materiais usados, limites e amostragem bidirecional das superfícies por material em 0,0001 mm. Faces idênticas são verificadas exatamente. As partes alteradas usam distâncias ponto-triângulo em precisão dupla, pois consultas BVH float tiveram falsos desvios até em faces inalteradas. A validação é uma checagem de candidatos produzidos apenas por operações locais, não uma prova geral para remalhagem arbitrária.

Interface: Tentar reparo seguro e Mostrar faces; reparo preserva contexto de edição, invalida prévia e captura do Loop. A cópia é publicada somente após validação. O arquivo original em disco não é salvo nem alterado. Buracos reais são recusados.

Limitação separada: após o reparo, a folga FDM de 0,10 mm colapsa microaberturas da região QR. A falha recebe mensagem orientada e os parâmetros permanecem intactos. Um ensaio sem folga também encontrou falha booleana de fechamento. O reparo da fonte foi validado, mas o corte completo desta região QR não está declarado resolvido.
