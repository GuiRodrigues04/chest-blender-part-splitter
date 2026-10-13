# Guia de alterações pequenas e revisáveis

Estas são instruções/pseudocódigo, não patches já testados. O mapa atual localiza as funções. Não modificar fontes do pacote-base: implementar em checkout separado.

## 1. Captura — operators + gpu_drawing + lifecycle

Introduzir serviço de estado da captura, com funções distintas:

- clear_capture(settings, reason): limpar índices, seed, flag, contagem, planicidade, razões e propostas dependentes.
- inspect_capture(target,settings,context): resultado válido/inválido com razão, origem, signature, ciclos/arestas.

set_target chama clear_capture quando muda objeto/mesh/sessão; chamar novamente na preparação do receptor confirmado. Overlay consulta validade e não desenha inválidos; não mutar RNA/cena dentro do callback GPU a cada frame.

Geração reutiliza inspect_capture; remover duplicação de checks que possam discordar entre UI e operador. Se modoEdit usaBMesh vivo, assinatura/índices precisam ser do mesmo snapshot; não comparar mesh.data ainda não sincronizado com captura recém-editada.

## 2. Materiais — geometry_material

Esboço do argumento por operando:

```text
insert_policy = chosen_insert_policy
receiver_policy = BODY
prism_a = cutter(..., interface_material=resolved_insert_material)
prism_b = cutter(..., interface_material=resolved_receiver_material)
result_a = intersect(source, prism_a)
result_b = difference(source, prism_b)
assign_new_interface_materials(result_a, result_b, provenance)
preserve_original_exterior_materials(...)
```

Converter politicaSOURCE/EXTRACTED legado para regras novas explicitamente. Se optar por manterAPI existente, passar política BODY/SOURCE apenas ao prisma B é correção inicial, mas teste do resultado continua obrigatório.

Não classificar toda A como “face nova”. Recoloração total deA deve ser opção separada. Exterior deB remanescente não é reparado por pintura única.

## 3. Validação — operators.validate_printable_mesh

Adicionar check de área e colinearidade antes de sucesso, com unidade:

```text
area_mm2 = face.calc_area() * scale_to_mm**2
if numeric_degenerate(face, area_mm2):
    return invalid(code=DEGENERATE_FACE, face_ids, stage)
```

Usar mesma função no cortador/candidato. Incluir limites físicos/tolerância numérica explícitos, sem inventar limite universal de impressão. Os índices deTestes1 ajudam reprodução, não devem ser hardcoded na extensão.

## 4. Folga — separar domínio lateral de profundidade

Substituir apenas depth_a/depth_b por construção que retorna lateral_domain_a/b + bottom_offset_a/b. Inputs: domínio nominal, folga lateral, fundo, alvoPART/CAVITY/BOTH.

Gerar cortadores da geometria offset e preservarposição da abertura exterior. Não usar scale_global emA ou prismas. Devolver diagnóstico de colapso com região afetada.

## 5. Encaixes — reutilizar compute_connector_layout

Extrair helpers já existentes para pipeline:

```text
nominal_candidates = generate_for_requested_layout(...)
safe_candidates = filter_by_complete_footprint_and_domain(...)
proposed = search_or_score_for_count_if_requested(...)
valid3d = verify_receiving_volume_and_attachment(...)
return ConnectorProposal(positions, status, reasons, resolution)
```

Expor adjust_to_valid_area enquantoAUTO_SHAPE é implementado; não chamar grade25×25 de solução exata. Reusar distância às bordas/validadores, ampliando para múltiplos candidatos e cápsula.

Guardar proposta com origem/interface e posiçõesUV/oumundo consistentes. Manual e pinosfixos revalidam; não bypass do domínio.

## 6. Continuação — lifecycle

Novo operador de continuar usa resolve_operation, record de confirmação e created_objects/roles existentes. Não usar active_object como única origem após commit, pois o código atual ativaA.

Criar papel semântico deRECEIVER/INSERT para associação, compatível com legados. Ligação de operação filha usa chest_operation_id do receptor; não limpar esse metadado ao torná-lo alvo. NovoIDgerado pela próxima geração, não no simples foco.

## 7. Cortador — separar factory/resolver/focus

ensure_solid_cutter pode ser dividido em get_session_cutter, create_session_cutter e reset_session_cutter. focus só seleciona/enquadra.

Objeto externo não passa porreset/cleanup de owned_objects. Duplica mesh se criar cópia editável. Novas ferramentas de referência usam snapshot e coordenadas físicas.

## 8. Idioma — preferências, templates e erros

Registrar AddonPreferences uma vez e catálogoPT/EN central. Código de erro não é uma frase traduzida. Relatórios armazenamparams+code; renderer e operator.report traduzem no momento de apresentação.

Idioma não entra na assinatura geométrica nem altera validação da prévia. Testar enums, descriçãoRNA, popup e fallback técnico, não apenas labels do painel.

## 9. Testes e entrega

Adicionar casos assertivos aos testes existentes; registrarSKIP sefixture ausente. D06 deve realmente medir sobreposição/cobertura quando anunciado, não apenasva>0/vb>0.

Encaixes emSOLID/MATERIAL ainda são bloqueados na base. Para prisma planar derivado que suporte novos pinos, adicionarCutInterface real evalidadores; manter recusa para sólidos gerais seminterface. Não reutilizar settings.loop_interface_normal antigo.

Cada patch tem teste da causa e uma regressão associada; só depois ampliar. Nenhum trecho deste guia autoriza apagar malha/caches do usuário fora da operação em foco.
