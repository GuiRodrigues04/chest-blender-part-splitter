# IndexError na recuperação do histórico em Edit Mode — 0.8.34

A captura mostra `IndexError: bpy_prop_collection[index]: index 0 out of range, size 0` ao acessar `previous.data[face.index]` em `recover_previous_interfaces`. O operador chama essa recuperação antes de construir o corte.

Reprodução determinística: criar um objeto com ancestral de corte registrado, criar os atributos FACE/INT `splitter_contact_surface` e `splitter_previous_interface` no objeto atual, entrar em Edit Mode e chamar a recuperação. No Blender 5.2, o atributo existe via RNA, mas seu array de valores está vazio enquanto os dados reais vivem na BMesh de edição. `update_from_editmode()` não elimina esse estado. O teste falhou na mesma linha e com o mesmo erro da captura antes da correção.

A recuperação agora lê a geometria e os atributos de uma cópia temporária da BMesh quando o alvo ou um ancestral está em edição. As marcações recuperadas são escritas na BMesh real do alvo. O modo, seleção, marcas existentes e geometria são preservados; as cópias são sempre liberadas. Mantidas as verificações de procedência do ancestral e a restrição de malhas compartilhadas em edição.

Teste de integração adicional gera uma prévia pelo operador real a partir de Edit Mode com os dois atributos existentes. A prévia termina como PREVIEW_VALID. São 13 testes de histórico aprovados, incluindo ancestrais em edição, preservação das marcas e ausência de vazamento de malhas temporárias. As seis suítes de histórico, estado, folga e geometria relacionadas passaram; logs e resumo estão nesta pasta.

Versão do manifesto, metadados, painel, README e changelog atualizados para 0.8.34. Pacote: `dist/chest_part_splitter-0.8.34.zip`, validado pelo Blender. A instalação mantém backup da versão anterior e confere os hashes de todos os arquivos do pacote; os testes de histórico são executados novamente a partir dos módulos instalados.

A aplicação já aberta continua usando módulos carregados anteriormente até ser reiniciada. O instalador não salva nem reabre a cena do usuário.
