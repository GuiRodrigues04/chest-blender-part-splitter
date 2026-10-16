"""Run a Blender test under the official bpy wheel (no GUI event loop)."""
import os, sys, runpy, traceback
import bpy
path = sys.argv[1]
sys.argv = [path]
code = 0
try:
 runpy.run_path(path, run_name='__main__')
except SystemExit as exc:
 code = exc.code if isinstance(exc.code, int) else (1 if exc.code else 0)
except BaseException:
 traceback.print_exc(); code = 1
sys.stdout.flush(); sys.stderr.flush()
# bpy wheels can wait for Blender worker shutdown after an otherwise finished test.
os._exit(code)
