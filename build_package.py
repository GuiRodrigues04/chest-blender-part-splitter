"""Script de empacotamento limpo para o Chest Part Splitter (Etapa 7).

Garante que o pacote comercial/distribuição (.zip) contenha apenas os arquivos
de produção essenciais, excluindo scratch/, testes, caches e documentos internos.
"""

import os
import sys
import shutil
import subprocess
import zipfile

def clean_build(blender_bin=None):
    if not blender_bin:
        blender_bin = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

    root_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(root_dir, "dist")
    stage_dir = os.path.join(dist_dir, "stage")

    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
    os.makedirs(stage_dir, exist_ok=True)

    # 1. Copia arquivos raiz obrigatórios
    essential_files = ["__init__.py", "blender_manifest.toml", "LICENSE", "README.md", "CHANGELOG.md"]
    for f in essential_files:
        src_path = os.path.join(root_dir, f)
        if os.path.exists(src_path):
            shutil.copy2(src_path, os.path.join(stage_dir, f))

    # 2. Copia pasta src limpa (sem __pycache__)
    src_folder = os.path.join(root_dir, "src")
    stage_src = os.path.join(stage_dir, "src")
    shutil.copytree(
        src_folder,
        stage_src,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
    )

    # 3. Lê versão do manifesto
    import tomllib
    manifest_path = os.path.join(stage_dir, "blender_manifest.toml")
    with open(manifest_path, "rb") as mf:
        manifest_data = tomllib.load(mf)
    version = manifest_data.get("version", "0.8.4")
    pkg_id = manifest_data.get("id", "chest_part_splitter")

    output_zip_name = f"{pkg_id}-{version}.zip"
    output_zip_path = os.path.join(root_dir, output_zip_name)

    if os.path.exists(output_zip_path):
        os.remove(output_zip_path)

    # 4. Executa comando oficial do Blender para empacotamento a partir do staging
    cmd = [
        blender_bin,
        "--command", "extension", "build",
        "--source-dir", stage_dir,
        "--output-filepath", output_zip_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Erro ao empacotar: {res.stderr}")
        sys.exit(1)

    # 5. Validação rigorosa do ZIP gerado (Checklist Seção 8)
    with zipfile.ZipFile(output_zip_path, "r") as zf:
        file_list = zf.namelist()
        for member in file_list:
            if any(forbidden in member.lower() for forbidden in ["scratch", "tests/", "__pycache__", ".blend", ".png"]):
                raise ValueError(f"Arquivo proibido encontrado no ZIP comercial: {member}")

    print(f"[OK] Pacote comercial limpo gerado com sucesso: {output_zip_name}")
    print(f"     Total de arquivos no ZIP: {len(file_list)}")
    print(f"     Tamanho: {os.path.getsize(output_zip_path):,} bytes")

    # Copia para Downloads
    downloads_path = os.path.join(os.path.expanduser("~"), "Downloads", output_zip_name)
    shutil.copy2(output_zip_path, downloads_path)
    print(f"[OK] Cópia atualizada em: {downloads_path}")

    # Limpeza da pasta temporária dist
    shutil.rmtree(dist_dir)

if __name__ == "__main__":
    clean_build()
