import subprocess
import sys
import os
import shutil

# Localiza o executÃ¡vel do Blender: variÃ¡vel de ambiente, argumento ou padrÃ£o
BLENDER_BIN = os.environ.get("BLENDER_BIN")
if not BLENDER_BIN:
    for arg in sys.argv[1:]:
        if arg.startswith("--blender="):
            BLENDER_BIN = arg.split("=", 1)[1]
            break
if not BLENDER_BIN:
    which_blender = shutil.which("blender")
    if which_blender:
        BLENDER_BIN = which_blender
if not BLENDER_BIN:
    default_path = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
    if os.path.exists(default_path):
        BLENDER_BIN = default_path

TESTS = [
    "tests/test_smoke_phase0.py",
    "tests/test_smoke_phase1.py",
    "tests/test_smoke_phase2.py",
    "tests/test_smoke_phase3.py",
    "tests/test_stress_phases0_3.py",
    "tests/test_phase3a_loop.py",
    "tests/test_multicolor_support.py",
    "tests/test_capsule_lateral_size.py",
    "tests/test_acceptance_etapa2.py",
    "tests/test_acceptance_etapa3.py",
    "tests/test_acceptance_etapa4.py",
    "tests/test_verify_bug_and_fix.py",
    "tests/test_acceptance_etapa5_ui.py",
    "tests/test_acceptance_etapa6_material.py",
    "tests/test_material_regions.py",
    "tests/test_acceptance_etapa7_delivery.py",
    "tests/test_final_plan_corrections.py",
    "tests/test_b01_b07.py",
    "tests/test_plan_086_commercial.py",
    "tests/test_reversion_086.py",
]

def main():
    print("=" * 70)
    print("EXECUTANDO BATERIA COMPLETA DE TESTES AUTOMATIZADOS")
    print(f"Blender Binario: {BLENDER_BIN}")
    print("=" * 70)
    
    passed_count = 0
    total_count = len(TESTS)
    
    for test in TESTS:
        print(f"\n>> Executando: {test} ...")
        cmd = [BLENDER_BIN, "--background", "--factory-startup", "--python-exit-code", "1", "--python", test]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        if res.returncode == 0:
            print(f"   [OK] {test} passou com sucesso!")
            passed_count += 1
        else:
            print(f"   [FALHA] {test} falhou com cÃ³digo {res.returncode}")
            print(res.stdout[-1000:])
            print(res.stderr[-1000:])
            sys.exit(1)
            
    print("\n" + "=" * 70)
    print(f"RESULTADO GERAL: {passed_count}/{total_count} SUÃTES DE TESTES PASSARAM (100% OK)")
    print("=" * 70)

if __name__ == "__main__":
    main()
