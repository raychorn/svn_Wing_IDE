"""Tests for Wing's scripting API."""

import os        # Don't move/remove _test_debugger uses this line!
import sys       # Don't move/remove _test_debugger uses this line!
import tempfile  # Don't move/remove _test_debugger uses this line!
import time      # Don't move/remove _test_debugger uses this line!
from guiutils import wgtk
import config

import wingapi
app = wingapi.gApplication

def _test_product_info(verbose):
  pi = app.GetProductInfo()
  if verbose:
    print "Product Info", pi
  return pi == (config.kVersion, config.kBuild, config.kProductCode, config.kProduct, 
                config.kReleaseDate)

def _test_winghome(verbose):
  wh = app.GetWingHome()
  if verbose:
    print  "Winghome", wh
  return wh == config.kWingHome

def _test_user_settings_dir(verbose):
  ud = app.GetUserSettingsDir()
  if verbose:
    print "User settings dir", ud
  return ud == config.kUserWingDir

def _test_start_dir(verbose):
  sd = app.GetStartingDirectory()
  if verbose:
    print "Starting dir", sd
  return sd == app.fSingletons.fWingIDEApp.GetStartingDirectory()

def _test_command_available(verbose):
  av1 = app.CommandAvailable('nonsense-command')
  av2 = app.CommandAvailable('show-panel')
  av3 = app.CommandAvailable('close')
  return not av1 and av2 and av3 == (app.fSingletons.fGuiMgr.GetActiveDocument() is not None)

def _test_execute_command(verbose):
  app.ExecuteCommand('scratch-document')
  app.ExecuteCommand('close')
  return 1

_gTimeoutTest = []
def _test_install_timeout(verbose):
  while len(_gTimeoutTest) > 0:
    _gTimeoutTest.pop()
  def doit():
    _gTimeoutTest.append('success')
  app.InstallTimeout(100, doit)
  time.sleep(.01)
  max_time = time.time() + 1.0
  while time.time() < max_time and len(_gTimeoutTest) == 0:
    wgtk.main_iteration()
  if len(_gTimeoutTest) == 1:
    return True
  else:
    print _gTimeoutTest,
    return False

def _test_get_active_editor(verbose):
  ed1 = app.ScratchEditor('testapi')
  ed2 = app.GetActiveEditor()
  result = ed1 is ed2
  app.ExecuteCommand('close')
  return result

def _test_get_active_document(verbose):
  ed = app.ScratchEditor('testapi')
  doc = app.GetActiveDocument()
  result = ed.GetDocument() is doc
  app.ExecuteCommand('close')
  return result

def _test_get_current_files(verbose):
  ed = app.ScratchEditor('testapi')
  files = app.GetCurrentFiles()
  result = 'unknown:testapi' in files
  app.ExecuteCommand('close')
  files = app.GetCurrentFiles()
  result = result and ('unknown:testapi' not in files)
  return result

def _test_get_current_source_scopes(verbose):
  wh = app.GetWingHome()
  fn = os.path.join(wh, 'scripts', 'editor-extensions.py')
  ed = app.OpenEditor(fn, raise_window=True)
  scopes = app.GetCurrentSourceScopes()
  app.ExecuteCommand('close')
  if not (len(scopes) == 1 and len(scopes[0]) >= 2):
    return False
  if sys.platform == 'win32':
    return bool(scopes[0][0].lower() == fn.lower())
  else:
    return os.path.samefile(scopes[0][0], fn)

def _test_get_all_files(verbose):
  ed = app.ScratchEditor('testapi')
  files = app.GetAllFiles()
  result = 'unknown:testapi' in files
  app.ExecuteCommand('close')
  files = app.GetAllFiles()
  result = result and ('unknown:testapi' not in files)
  return result

def _test_get_open_documents(verbose):
  ed = app.ScratchEditor('testapi')
  docs = app.GetOpenDocuments()
  result1 = False
  for doc in docs:
    if doc.GetFilename() == 'unknown:testapi':
      result1 = True
      break
  app.ExecuteCommand('close')
  docs = app.GetOpenDocuments()
  result2 = True
  for doc in docs:
    if doc.GetFilename() == 'unknown:testapi':
      result2 = False
      break
  return result1 and result2

def _test_create_window(verbose):
  win = app.CreateWindow('testapi')
  ed = app.ScratchEditor('testwin', window_name='testapi')
  result = app.GetActiveEditor() is ed
  app.CloseWindow('testapi', allow_cancel=False)
  return result

def _test_open_editor(verbose):
  fn = os.path.join(app.GetWingHome(), 'LICENSE.txt')
  ed = app.OpenEditor(fn)
  doc = ed.GetDocument()
  txt1 = doc.GetText()
  app.ExecuteCommand('close')
  f = open(fn, 'rb')
  txt2 = f.read()
  txt2 = unicode(txt2, config.kLatin1Encoding)
  f.close()   
  return txt1 == txt2

def _test_scratch_editor(verbose):
  ed = app.ScratchEditor('testscratch')
  doc = ed.GetDocument()
  txt1 = u'testing\n' * 3
  doc.SetText(txt1)
  txt2 = doc.GetText()
  app.ExecuteCommand('close')
  return txt1 == txt2

def _test_get_project(verbose):
  proj = app.GetProject()
  return proj is not None

def _test_get_debugger(verbose):
  debugger = app.GetDebugger()
  return debugger is not None

_gPrefValues = []
def _test_get_set_connect_preference(verbose):
  while len(_gPrefValues) > 0:
    _gPrefValues.pop()
  result = True
  save_value = app.GetPreference('edit.caret-width')
  if save_value == 1:
    test_value = 3
  else:
    test_value = 1
  def pref_changed():
    new_value = app.GetPreference('edit.caret-width')
    _gPrefValues.append(new_value)
  pref, id = app.ConnectToPreference('edit.caret-width', pref_changed)
  app.SetPreference('edit.caret-width', test_value)
  if app.GetPreference('edit.caret-width') != test_value:
    print "SetPreference failed (1)",
    result = False
  app.SetPreference('edit.caret-width', save_value)
  if app.GetPreference('edit.caret-width') != save_value:
    print "SetPreference failed (2)",
    result = False
  if tuple(_gPrefValues) != (test_value, save_value):
    print "Preference signals failed", tuple(_gPrefValues), (test_value, save_value),
    result = False
  app.DisconnectFromPreference(pref, id)
  return result
  
def _test_show_preference(verbose):
  app.ShowPreference('edit.caret-width')
  app.fSingletons.fGuiMgr.fPrefGUI.fDialog.Close()
  return True

def _test_attributes(verbose):
  print "Untested",
  return True

#def _test_message_dialog(verbose):
  #app.ShowMessageDialog('Testing API', 'Testing scripting API')
  #return True

def _test_status_area(verbose):
  app.SetStatusMessage('This message set by Wing scripting API test')
  return True

if sys.platform == 'win32':
  kListDirCmd = 'cmd.exe /c dir'
else:
  kListDirCmd = 'ls'

def _test_execute_command_line(verbose):
  err, output = app.ExecuteCommandLine(kListDirCmd, app.GetWingHome(), None, 2.0)
  if err != 0 or output.find('LICENSE.txt') < 0:
    print "err=", err
    print output
    return False
  else:
    return True

def _test_async_execute_command_line(verbose):
  argv = kListDirCmd.split(' ')
  handler = app.AsyncExecuteCommandLine(argv[0], app.GetWingHome(), *argv[1:])
  end_time = time.time() + 2.0
  while not handler.Iterate() and time.time() < end_time:
    time.sleep(0.01)
  out, err, errcode, status = handler.Terminate()
  if errcode is not None or (status is not None and status != 0) or out.find('LICENSE.txt') < 0:
    print "errcode=", errcode
    print "status=", status
    print out
    return False
  else:
    return True

def _test_document(verbose):
  success = True

  pyfn = __file__
  if pyfn.endswith('.pyc') or pyfn.endswith('.pyo'):
    pyfn = pyfn[:-1]    
  f = open(pyfn, 'rb')
  txt = f.read()
  f.close()

  fn = tempfile.mktemp() + '.py'
  f = open(fn, 'wb')
  f.write(txt)
  f.close()

  doc_signals = {}
  def doc_open(dobj, fn=fn):
    if dobj.GetFilename() == fn:
      doc_signals['open'] = 1
  do_sig = app.Connect('document-open', doc_open)

  ed = app.OpenEditor(fn)
  doc = ed.GetDocument()
  def doc_destroy(*args):
    doc_signals['destroy'] = 1
  doc.Connect('destroy', doc_destroy)
  doc.BeginUndoAction()

  if not doc_signals.has_key('open'):
    print "App document-open signal was not emitted"
    success = False
  app.Disconnect(do_sig)
  
  if doc.GetMimeType() != 'text/x-python':
    print "Bad mime type",
    success = False
  if sys.platform != 'win32' and not os.path.samefile(doc.GetFilename(), fn):
    print "Bad file name",
    success = False
  if sys.platform == 'win32' and doc.GetFilename().lower() != fn.lower():
    print "Bad file name",
    success = False
  if txt != doc.GetText():
    print "Bad initial contents",
    success =False
    
  txt = 'print "X"\nprint "Y"'
  doc.SetText(txt)
  if txt != doc.GetText():
    print "SetText failed",
    success = False

  doc.DeleteChars(0, txt.find('\n'))
  if txt[txt.find('\n')+1:] != doc.GetText():
    print "DeleteText failed",
    success = False

  doc.InsertChars(0, txt[:txt.find('\n')+1])
  if txt != doc.GetText():
    print "InsertChars failed",
    success = False
    
  if len(txt) != doc.GetLength():
    print "Bad length",
    success = False
    
  if doc.GetLineCount() != 2:
    print "Bad line count",
    success = False
    
  if doc.GetCharRange(0, txt.find('\n')) != txt[:txt.find('\n')]:
    print "GetCharRange failed",
    success = False
    
  if doc.GetLineNumberFromPosition(len(txt) - 1) != 1:
    print "GetLineNumberFromPosition failed",
    success = False
    
  if doc.GetLineStart(0) != 0:
    print "GetLineStart(0) failed",
    success = False
    
  if doc.GetLineStart(1) != txt.find('\n') + 1:
    print "GetLineStart(1) failed",
    success = False
    
  if doc.GetLineEnd(0) != txt.find('\n'):
    print "GetLineEnd(0) failed",
    success = False
  if doc.GetLineEnd(1) != len(txt):
    print "GetLineEnd(1) failed",
    success = False
  
  f = doc.GetAsFileObject()
  if f.read() != txt:
    print "GetAsFileObject failed"
    success = False
  
  doc.EndUndoAction()
  if not doc.CanUndo() or doc.CanRedo():
    print "Bad undo state 1",
    success = False    
  if doc.IsSavePoint():
    print "Bad save point 1",
    success = False
    
  doc.Undo()
  if doc.CanUndo() or not doc.CanRedo():
    print "Bad undo state 2",
    success = False
  if not doc.IsSavePoint():
    print "Bad save point 2",
    success = False
  
  app.ExecuteCommand('close')
  os.unlink(fn)
  
  if not doc_signals.has_key('destroy'):
    print "Document destroy signal not emitted"
    success = False
    
  return success

def _test_editor(verbose):

  success = True

  pyfn = __file__
  if pyfn.endswith('.pyc') or pyfn.endswith('.pyo'):
    pyfn = pyfn[:-1]    
  f = open(pyfn, 'rb')
  txt = f.read()
  f.close()

  fn = tempfile.mktemp() + '.py'
  f = open(fn, 'wb')
  f.write(txt)
  f.close()

  ed = app.OpenEditor(fn, raise_window=True)
  doc = ed.GetDocument()
 
  max_time = time.time() + 2.0
  _done = []
  def size_done(*args):
    _done.append(1)
  ed.fEditor._fScint.connect_after('size-allocate', size_done)
  while time.time() < max_time and len(_done) == 0:
    wgtk.main_iteration()

  if ed.IsReadOnly():
    print "Bad readonly state 1",
    success = False
  ed.SetReadOnly(True)
  if not ed.IsReadOnly():
    print "Bad readonly state 2",
    success = False
  ed.SetReadOnly(False)
  if ed.IsReadOnly():
    print "Bad readonly state 3",
    success = False
  
  sel_test = {}
  def sel_changed(start, end):
    sel_test[1] = (start, end)
  ed.Connect('selection-changed', sel_changed)
  ed.SetSelection(0, 100)
  ed.fEditor._ForceUIUpdate()  
  if ed.GetSelection() != (0, 100):
    print "Selection failed",
    success = False
  if not sel_test.has_key(1):
    print "Selection signal not called",
    success = False
  elif sel_test[1] != (0, 100):
    print "Selection signal passed", sel_test[1], "expected (0, 100)"
    success = False
    
  scroll_test = {}
  def scroll_changed(*args):
    scroll_test[1] = 1
  ed.Connect('scrolled', scroll_changed)
  sel_line_test = {}
  def sel_line_changed(first_line, last_line):
    sel_line_test[1] = (first_line, last_line)
  ed.Connect('selection-lines-changed', sel_line_changed)
  
  ed.ScrollToLine(99, select=1, pos='top')
  ed.fEditor._ForceUIUpdate()  
  def check_state(quiet=0):
    success = True
    sel = ed.GetSelection()
    if sel[0] != doc.GetLineStart(99) or abs(sel[1] - doc.GetLineEnd(99)) > 1:
      if not quiet:
        print "ScrollToLine select failed",
      success = False
    if ed.GetFirstVisibleLine() != 99:
      if not quiet:
        print "ScrollToLine first visible line failed",
      success = False
    if ed.GetSourceScope()[0] != fn or ed.GetSourceScope()[1] != 99:
      if not quiet:
        print "GetSourceScope failed",
      success = False
    return success
  if not check_state():
    print "First check state failed",
    success = False
  if not scroll_test.has_key(1):
    print "Scrolled signal not called",
    success = False
  if not sel_line_test.has_key(1):
    print "Selection changed not called",
    success = False
  elif not sel_line_test[1] != (99, 99):
    print "Selection changed signal passed", sel_line_changed[1], "expected (99, 99)"
    success = False
    
  state = ed.GetVisualState()
  ed.ScrollToLine(40, select=1, pos='slop')
  if check_state(quiet=1):
    print "Check state should not have passed",
    success = False
  ed.SetVisualState(state)
  if not check_state():
    print "Second check state failed",
    success = False
  ed.SetSelection(0, 100)
  if not ed.CommandAvailable('cut'):
    print "Cut not available",
    success = False
  else:
    ed.ExecuteCommand('cut')
    ed.ExecuteCommand('undo')
    if doc.GetText() != txt:
      print "ExecuteCommand failed",
      success = False
      
  if not ed.FoldingAvailable():
    print "Folding should be available (although won't be if pref is disabled)",
    success = False
  else:
    def fold_all(lineno):
      return -1
    def unfold_all(lineno):
      return 1
    ed.FoldUnfold(fold_all)
    ed.FoldUnfold(unfold_all)
    
  app.ExecuteCommand('close')
  os.unlink(fn)
  return success
 
def _test_project(verbose):
  proj = app.GetProject()
  success = True
  if len(proj.GetFilename()) == 0:
    print "Bad filename",
    success = False

  fn = __file__
  if fn.endswith('.pyc') or fn.endswith('.pyo'):
    fn = fn[:-1]    

  proj.GetSelectedFile()
  files = proj.GetAllFiles()
  proj.AddFiles([fn])
  files2 = proj.GetAllFiles()
  if fn not in files2:
    print "AddFiles failed",
    success = False
  if fn not in files and len(files2) != len(files) + 1:
    print "GetAllFiles failed (1)",
    success = False
  elif fn in files and len(files2) != len(files):
    print "GetAllFiles failed (2)",
    success = False
    
  if fn not in files:
    proj.RemoveFiles([fn])
    files2 = proj.GetAllFiles()
    if fn in files2 or len(files) != len(files2):
      print "RemoveFiles failed",
      success = False

  env = proj.GetEnvironment(set_pypath=False)
  tests = ""
  result = ""
  for key, value in env.items():
    if '$' not in value:
      tests += "$(%s)\n" %  key
      result += value + '\n'
  result2 = proj.ExpandEnvVars(tests)
  if result != result2:
    print "ExpandEnvVars failed"
    result_lines = result.splitlines()
    result2_lines = result2.splitlines()
    if len(result_lines) != len(result2_lines):
      print "  Different length lists"
    else:
      for i, line in enumerate(result_lines):
        line2 = result2_lines[i]
        if line != line2:
          print "  Mismatch for %s:" % env.items()[i][0]
          print "    '%s'" % line
          print "    '%s'" % line2
    success = False
  
  return success      
    
def _test_debugger(verbose):
  kTimeout = 5
  
  success = True

  signal_tests = {}
  def new_runstate(rs):
    signal_tests['new'] = rs
  def runstate_changed(rs):
    signal_tests['changed'] = rs
    
  dbg = app.GetDebugger()
  dbg.connect('new-runstate', new_runstate)
  dbg.connect('current-runstate-changed', runstate_changed)
  runstates = dbg.GetRunStates()
  if len(runstates) == 0:
    print "Bad runstate list",
    success = False
  rs = dbg.GetCurrentRunState()
  if rs is None:
    print "No runstate found",
    success = False
  signal_tests['changed'] = rs

  if not success:
    return False
  
  fn = __file__
  if fn.endswith('.pyc') or fn.endswith('.pyo'):
    fn = fn[:-1]    

  _state = [None]
  rs.Run(fn, stop_on_first=1)
  def paused():
    _state[0] = 'paused'
  rs.Connect('paused', paused)
  end_time = time.time() + kTimeout
  while _state[0] != 'paused' and time.time() < end_time:
    wgtk.main_iteration()
  if _state[0] != 'paused':
    print "Run failed",
    rs.Kill()
    return False
  
  _state[0] = None
  rs.Step()
  end_time = time.time() + kTimeout
  while _state[0] != 'paused' and time.time() < end_time:
    wgtk.main_iteration()
  if _state[0] != 'paused':
    print "Step failed",
    rs.Kill()
    return False

  ed = app.GetActiveEditor()
  doc = ed.GetDocument()
  if doc.GetFilename() != fn:
    print "Show doc failed", doc.GetFilename(), fn
    success = False
  
  start, end = ed.GetSelection()
  lineno = doc.GetLineNumberFromPosition(start)
  print lineno
  
  pos = doc.GetLineStart(lineno+1)
  ed.SetSelection(pos, pos)
  _state[0] = None
  rs.RunToCursor()
  end_time = time.time() + kTimeout
  while _state[0] != 'paused' and time.time() < end_time:
    wgtk.main_iteration()
  if _state[0] != 'paused':
    print "RunToCursor failed",
    rs.Kill()
    return False  
  
  start, end = ed.GetSelection()
  lineno = doc.GetLineNumberFromPosition(start)
  actual_lineno, err = rs.SetBreak(fn, lineno+2)
  if err is not None or actual_lineno != lineno+2:
    print "SetBreak failed", err, lineno, actual_lineno
  
  _state[0] = None
  rs.Continue()
  end_time = time.time() + kTimeout
  while _state[0] != 'paused' and time.time() < end_time:
    wgtk.main_iteration()
  if _state[0] != 'paused':
    print "Continue to breakpoint failed", _state[0]
    rs.ClearBreak(fn, lineno+2)
    rs.Kill()
    return False

  rs.ClearBreak(fn, lineno+2)
  
  threads = rs.GetThreads()
  if len(threads) != 1:
    print "Thread count wrong",
    rs.Kill()
    return False
  
  s = rs.GetStack()
  if s[-1][0] != fn or s[-1][1] != lineno+2:
    print "Stack wrong", s
    rs.Kill()
    return False
  
  t, i = rs.GetStackFrame()
  if i != len(s) - 1:
    print "Stack frame wrong", i
    rs.Kill()
    return False
  if t not in [thread[0] for thread in threads]:
    print "Thread", t, "not in threads list", threads
  
  rs.SetStackFrame(threads[0][0], 0)
  t, i = rs.GetStackFrame()
  if t != threads[0][0]:
    print "SetStackFrame failed (thread wrong)", t, threads[0]
    rs.Kill()
    return False
  if i != 0:
    print "SetStackFrame failed (stack index wrong)", i
    rs.Kill()
    return False

  # XXX Weak tests but runstate doesn't ever change now (but will in future versions)
  if signal_tests.has_key('new'):
    print "Unexpected new runstate"
    rs.Kill()
    return False
  if signal_tests.get('changed') != rs:
    print "current-runstate-changed signal failed", signal_tests.get('changed'), rs
    return False

  rs.Kill()  
  return success

#--------------------------------------------------------------------------------------
_all_tests = dir()
def test_api(verbose=0):
  """Test Wing's scripting API"""

  print "=" *40
  print "STARTING WING SCRIPTING API UNIT TESTS"
  
  counts = [0, 0, 0]
  for test in _all_tests:
    if not test.startswith('_test_'):
      continue
    print test, '...', 
    try:
      result = eval('%s(%i)' % (test, verbose))
      if result:
        print "OK"
        counts[0] += 1
      else:
        print "FAILED"
        counts[1] += 1
    except:
      print "EXCEPTION"
      counts[2] += 1
      from wingutils import reflect
      exc = reflect.GetCurrentException()
      exc = [e.replace('\n', '\n    ') for e in exc]
      print '    ' + '\n    '.join(exc)
      
  print "=" *40
  if counts[1] > 0 or counts[2] > 0:
    print "SOME TESTS FAILED!"
  else:
    print "ALL TESTS PASSED!"
  print "Summary: %i passed, %i failed, %i exceptions" % tuple(counts)
  print "=" *40
      
