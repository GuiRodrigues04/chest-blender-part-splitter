# Resultados da validação 0.9.10

- Base revisada: `ed994ab935033191d43f2a5b8786fd9045a5cbba`. ZIP 0.9.10 instalado e comparado byte a byte; SHA-256 `E5BA22F63AB3C106016FB85CC4151B3878A1D523A80D5B280BCD512812FBAFF5`.
- Regressões: geometria 13/13 suites (105 testes; 1 skip por fixture privada ausente), fluxo de release 11/11, modelos reais 11/11, pacote 2/2, sizing instalado 14/14 e UV/material 5/5.
- Spot original: quatro previews com folgas de 0, 0.1, 0.2 e 1 mm passaram; a fonte e o arquivo `.blend` permaneceram inalterados. Para folga 0.1 mm, 208 amostras laterais mediram 0.099993–0.100005 mm e 96 amostras de fundo mediram 0.100001–0.100005 mm.
- Correção: a triangulação usada antes de Boolean em cortes Loop descartava as camadas UV de canto. A cópia agora preserva as UVs por `MeshLoopTriangle.loops`, costuras, camada ativa e camada ativa para render. No teste com imagem sintética de quatro cores, não houve diferenças de cor nas amostras da superfície retida.

## Limite

O `.blend` aponta para `//spot_texture.png`, que não está disponível nesta máquina. A pintura exata do arquivo do usuário não pôde ser amostrada; a verificação visual automatizada usou a imagem sintética empacotada.

