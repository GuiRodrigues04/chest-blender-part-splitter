import sys, tempfile, subprocess
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from scripts.build import prepare_stage,inspect_package
import bpy
out=root/'dist'/'chest_part_splitter-0.8.32-folga-uniforme.zip'
out.parent.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='clearance_stage_') as td:
 stage=Path(td)/'source';stage.mkdir();prepare_stage(stage)
 subprocess.run([bpy.app.binary_path,'--factory-startup','--command','extension','validate',str(stage)],check=True)
 subprocess.run([bpy.app.binary_path,'--factory-startup','--command','extension','build','--source-dir',str(stage),'--output-filepath',str(out)],check=True)
 inspect_package(out)
 subprocess.run([bpy.app.binary_path,'--factory-startup','--command','extension','validate',str(out)],check=True)
print('PACKAGE='+str(out))
