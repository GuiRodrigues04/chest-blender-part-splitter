"""Cross-check UI literals, exceptions, help and formatted messages in both locales."""
import ast,sys,string,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src import translations as t
ROOT=Path(__file__).resolve().parents[1]
class LanguageAudit093(unittest.TestCase):
 def test_error_literal_coverage(self):
  for p in (ROOT/'src').glob('*.py'):
   if p.name=='translations.py':continue
   for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
    if isinstance(n,ast.Raise) and isinstance(n.exc,ast.Call) and n.exc.args:
     a=n.exc.args[0]
     self.assertNotIsInstance(a,ast.JoinedStr,(p.name,n.lineno))
     if isinstance(a,ast.Constant) and isinstance(a.value,str) and ' ' in a.value:
      for loc in ('pt_BR','en_US'):self.assertIn(('*',a.value),t.TRANSLATIONS_DICT[loc],(p.name,n.lineno,loc,a.value))
 def test_catalog_parity(self):
  self.assertEqual(set(t.MESSAGES['pt_BR']),set(t.MESSAGES['en_US']))
  fmt=string.Formatter()
  for k in t.MESSAGES['pt_BR']:
   fields=lambda s:sorted(x[1] for x in fmt.parse(s) if x[1] is not None)
   self.assertEqual(fields(t.MESSAGES['pt_BR'][k]),fields(t.MESSAGES['en_US'][k]),k)
 def test_both_locales_and_nested_reason(self):
  for locale in ('pt_BR','en_US'):
   with patch.object(t,'get_addon_locale',return_value=locale):
    for pt,en in t._ERROR_LOCALE_PAIRS:
     for source in (pt,en):self.assertEqual(t.localize_text(source),t._portuguese_terms(pt) if locale=='pt_BR' else en)
    reason='A faixa de folga não é fechada.'
    result=t.tr('preview.failed_preserved',reason=reason)
    self.assertIn(reason if locale=='pt_BR' else 'The clearance band is not closed.',result)
    for key,pt,en in t._DYNAMIC_AUDIT_MESSAGES:
     vals={}
     for _,field,spec,_ in string.Formatter().parse(pt):
      if field is not None:vals[field]=1.25 if spec else 'X'
     self.assertEqual(t.localized_format(key,**vals),(t._portuguese_terms(pt) if locale=='pt_BR' else en).format(**vals))
 def test_report_exceptions_are_localized(self):
  for p in (ROOT/'src').glob('*.py'):
   if p.name=='translations.py':continue
   for n in ast.walk(ast.parse(p.read_text(encoding='utf-8'))):
    if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='report' and len(n.args)>1:
     arg=n.args[1]
     if isinstance(arg,ast.Call) and isinstance(arg.func,ast.Name):
      self.assertNotEqual(arg.func.id,'str',(p.name,n.lineno))
  from src.localized_errors import render_message
  for locale,expected in [('pt_BR','A faixa de folga não é fechada.'),('en_US','The clearance band is not closed.')]:
   with patch.object(t,'get_addon_locale',return_value=locale):
    self.assertEqual(render_message(ValueError('A faixa de folga não é fechada.')),expected)
 def test_help_languages(self):
  for topic,data in t.HELP_TOPICS.items():
   for field in ('title','tooltip','popup_lines'):
    self.assertTrue(data[field]['pt_BR'],(topic,field));self.assertTrue(data[field]['en_US'],(topic,field))
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LanguageAudit093))
 if not result.wasSuccessful():raise RuntimeError('Language audit failed')
