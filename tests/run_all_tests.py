import subprocess
import sys
import os

BLENDER_BIN = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
TESTS = [
    "tests/test_smoke_phase0.py",
    "tests/test_smoke_phase1.py",
    "tests/test_smoke_phase2.py",
    "tests/test_smoke_phase3.py",
    "tests/test_stress_phases0_3.py",
    "tests/test_phase3a_loop.py",
]

def main():
    print("=" * 70)
    print("EXECUTANDO BATERIA COMPLETA DE TESTES AUTOMATIZADOS (FASES 0 A 3A)")
    print("=" * 70)
    
    passed_count = 0
    total_count = len(TESTS)
    
    for test in TESTS:
        print(f"\n>> Executando: {test} ...")
        cmd = [BLENDER_BIN, "--background", "--factory-startup", "--python", test]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        if res.returncode == 0:
            print(f"   [OK] {test} passou com sucesso!")
            passed_count += 1
        else:
            print(f"   [FALHA] {test} falhou com código {res.returncode}")
            print(res.stdout[-1000:])
            print(res.stderr[-1000:])
            sys.exit(1)
            
    print("\n" + "=" * 70)
    print(f"RESULTADO GERAL: {passed_count}/{total_count} SUÍTES DE TESTES PASSARAM (100% OK)")
    print("=" * 70)

if __name__ == "__main__":
    main()
