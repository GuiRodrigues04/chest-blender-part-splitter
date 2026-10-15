import os
import sys
import bpy

print("--- INITIATING VISUAL CAPTURE SCRIPT WITH TEMP_OVERRIDE ---")

artifact_dir = r"C:\Users\guiro\.gemini\antigravity\brain\d89ab39c-0ee1-4d39-9937-beacba11a756"
capture_edit_path = os.path.join(artifact_dir, "captura_grade_em_edicao.png")
capture_after_path = os.path.join(artifact_dir, "captura_apos_confirmacao_sem_grade.png")

stage = 0

def step():
    global stage
    stage += 1
    print(f"\n>>> Capture stage: {stage}")

    settings = bpy.context.scene.chest_splitter

    # Encontra área VIEW_3D e região WINDOW
    area_3d = None
    region_win = None
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            area_3d = area
            for r in area.regions:
                if r.type == 'WINDOW':
                    region_win = r
                    break
            break

    if not area_3d or not region_win:
        print("Error: VIEW_3D area/region not found!")
        bpy.ops.wm.quit_blender()
        return None

    if stage == 1:
        print("Stage 1: Setting up scene, positioning camera and opening manual editor...")
        settings.split_mode = 'LOOP'
        settings.connector_distribution = 'MANUAL'
        settings.connector_enabled = True

        # Prepara corte inicial e adiciona 2 pinos
        try:
            bpy.ops.chest.splitter_generate_preview()
            bpy.ops.chest.splitter_add_manual_connector()
            bpy.ops.chest.splitter_add_manual_connector()
            if len(settings.manual_connectors) >= 2:
                settings.manual_connectors[0].u_mm = -15.0
                settings.manual_connectors[0].v_mm = -15.0
                settings.manual_connectors[1].u_mm = 15.0
                settings.manual_connectors[1].v_mm = 15.0
        except Exception as e:
            print("Preview setup error:", e)

        # Alinha câmera para enquadrar a face de corte
        with bpy.context.temp_override(area=area_3d, region=region_win):
            try:
                bpy.ops.chest.splitter_view_cut_face()
                print("view_cut_face succeeded!")
            except Exception as e:
                print("view_cut_face error:", e)

            # Inicia o editor modal de pinos manuais
            try:
                res = bpy.ops.chest.splitter_edit_manual_connectors('INVOKE_DEFAULT')
                print(f"edit_manual_connectors result: {res}")
            except Exception as e:
                print("edit_manual_connectors error:", e)

        area_3d.tag_redraw()
        print(f"is_editing_connectors: {settings.is_editing_connectors}")
        return 1.2

    elif stage == 2:
        print(f"Stage 2: Taking screenshot of 5mm grid in editing -> {capture_edit_path}")
        area_3d.tag_redraw()
        with bpy.context.temp_override(area=area_3d, region=region_win):
            bpy.ops.screen.screenshot(filepath=capture_edit_path)
        return 0.8

    elif stage == 3:
        print("Stage 3: Confirming manual positions and generating preview...")
        with bpy.context.temp_override(area=area_3d, region=region_win):
            try:
                res = bpy.ops.chest.splitter_confirm_manual_connectors()
                print(f"confirm_manual_connectors result: {res}")
            except Exception as e:
                print("confirm_manual_connectors error:", e)

        area_3d.tag_redraw()
        print(f"is_editing_connectors after confirm: {settings.is_editing_connectors}")
        return 1.2

    elif stage == 4:
        print(f"Stage 4: Taking screenshot after confirmation (grid removed) -> {capture_after_path}")
        area_3d.tag_redraw()
        with bpy.context.temp_override(area=area_3d, region=region_win):
            bpy.ops.screen.screenshot(filepath=capture_after_path)
        return 0.6

    elif stage == 5:
        print("Stage 5: Visual captures completed successfully! Quitting.")
        bpy.ops.wm.quit_blender()
        return None

bpy.app.timers.register(step, first_interval=1.0)
