import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src import translations as t
from unittest.mock import patch
for language in ('pt_BR','en_US'):
 bpy.context.preferences.view.language=language
 with patch.object(t,'get_addon_preferences',return_value=None):
  print('BLENDER_LOCALE',language,t.get_addon_locale(),t.localize_text('Gerar / Atualizar Prévia'))
  assert t.get_addon_locale()==language
