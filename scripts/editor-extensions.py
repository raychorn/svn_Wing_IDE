"""Editor extensions that also serve as examples for scripting Wing IDE.

See the Scripting chapter of the manual for more information on writing 
and using scripts.

Copyright (c) 2005-2008, Wingware All rights reserved.
Copyright (c) 2005, Ken Kinder All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Notes:

* sort_selected() was contributed by Ken Kinder
* Improved title_case() and auto-selection contributed by
  Yves Bastide

"""

import os
import stat
import wingapi

# Scripts can be internationalize with gettext.  Strings to be translated
# are sent to _() as in the code below.
import gettext
_ = gettext.translation('scripts_editor_extensions', fallback = 1).ugettext

# This special attribute is used so that the script manager can translate
# also docstrings for the commands found here
_i18n_module = 'scripts_editor_extensions'

def _active_editor_exists():
  app = wingapi.gApplication
  editor = app.GetActiveEditor()
  return editor is not None


########################################################################
# Editing commands

def delete_selected_lines(app=wingapi.kArgApplication):
  """Delete the line or range of lines that contain the current selection.
  This duplicates what the editor command delete-line does."""

  editor = app.GetActiveEditor()
  doc = editor.GetDocument()
  start, end = editor.GetSelection()

  start_lineno = doc.GetLineNumberFromPosition(start)
  end_lineno = doc.GetLineNumberFromPosition(end)

  line_start = doc.GetLineStart(start_lineno)
  line_end = doc.GetLineEnd(end_lineno)

  doc.DeleteChars(line_start, line_end)

delete_selected_lines.available = _active_editor_exists

def comment_block_toggle():
  """Toggle block comment (with ## at start) on the selected lines in editor.
  This is a different style of block commenting than Wing implements by default
  (the default in Wing is intended to work better with some of the other
  editor functionality)"""

  app = wingapi.gApplication
  editor = app.GetActiveEditor()
  eol = editor.GetEol()
  doc = editor.GetDocument()
  start, end = editor.GetSelection()

  start_lineno = doc.GetLineNumberFromPosition(start)
  end_lineno = doc.GetLineNumberFromPosition(end)

  line_start = doc.GetLineStart(start_lineno)
  line_end = doc.GetLineEnd(end_lineno)
  line_end = min(line_end, doc.GetLength() - len(eol))

  txt = doc.GetCharRange(line_start, line_end)
  txt2 = []
  if txt.startswith('##'):
    for line in txt.split(eol):
      if len(line) >= 2 and line[:2] == '##':
        line = line[2:]
      txt2.append(line)
  else:
    for line in txt.split(eol):
      if len(line.strip()) > 0:
        line = '##' + line
      txt2.append(line)
  txt2 = eol.join(txt2) + eol

  doc.BeginUndoAction()
  try:
    doc.DeleteChars(line_start, line_end)
    doc.InsertChars(line_start, txt2)
  finally:
    doc.EndUndoAction()

comment_block_toggle.available = _active_editor_exists

########################################################################
# Capitalization and other transforms of the current selection

import string

def _transform_selection(editor, xform):
  """Change current selection to all lower case"""

  doc = editor.GetDocument()
  start, end = editor.GetSelection()
  doc.BeginUndoAction()
  try:
    if start != end:
      with_selection = 1
    else:
      with_selection = 0
      wingapi.gApplication.ExecuteCommand("forward-word")
      end, dummy = editor.GetSelection()
    txt = doc.GetCharRange(start, end)
    new_txt = xform(txt)
    if new_txt != txt:
        doc.DeleteChars(start, end-1)
        doc.InsertChars(start, new_txt)
  finally:
    doc.EndUndoAction()
  if with_selection:
    editor.SetSelection(start, end)
  else:
    editor.SetSelection(end, end)

def lower_case(editor=wingapi.kArgEditor):
  """Change current selection to all lower case"""

  _transform_selection(editor, string.lower)

def upper_case(editor=wingapi.kArgEditor):
  """Change current selection to all upper case"""

  _transform_selection(editor, string.upper)

def title_case(editor=wingapi.kArgEditor):
  """Change current selection to capitalize first letter of each word"""

  def xform(x):
    """A better version of string.capwords"""
    import re
    return "".join([word.capitalize() for word in re.split(r"([\W_\d]+)", x)])
  _transform_selection(editor, xform)

def hyphen_to_under(editor=wingapi.kArgEditor):
  """Change hyphens (dashes) to underscores in current selection"""

  def xform(x):
    return x.replace('-', '_')
  _transform_selection(editor, xform)

def under_to_hyphen(editor=wingapi.kArgEditor):
  """Change underscores to hyphens (dashes) in current selection"""

  def xform(x):
    return x.replace('_', '-')
  _transform_selection(editor, xform)

def sort_selected(app=wingapi.kArgApplication):
  """Sort selected lines of text alphabetically"""

  editor = app.GetActiveEditor()
  doc = editor.GetDocument()
  eol = editor.GetEol()
  start, end = editor.GetSelection()

  start_lineno = doc.GetLineNumberFromPosition(start)
  end_lineno = doc.GetLineNumberFromPosition(end)

  line_start = doc.GetLineStart(start_lineno)
  line_end = doc.GetLineEnd(end_lineno)

  text = doc.GetCharRange(start, end).split(eol)
  text.sort()

  doc.BeginUndoAction()
  try:
    doc.DeleteChars(start, end-1)
    doc.InsertChars(start, eol.join(text))
  finally:
    doc.EndUndoAction()
  editor.SetSelection(start, end)

def copy_filename_to_clipboard(fn=wingapi.kArgFilename):
  if fn:
    wingapi.gApplication.SetClipboard('\n'.join(fn))
  
  
########################################################################
# Alternate key behaviors

def _move_right(editor, count):
  for i in range(0, count):
    editor.ExecuteCommand('forward-char')

def vs_tab(app=wingapi.kArgApplication):
  """Modified tab indentation command that acts like tab in Visual Studio."""

  editor = app.GetActiveEditor()
  tab_size = editor.GetIndentSize()
  doc = editor.GetDocument()
  start, end = editor.GetSelection()
  if start != end:
    editor.ExecuteCommand('indent-to-match')
    return

  lineno = doc.GetLineNumberFromPosition(start)
  line_start = doc.GetLineStart(lineno)
  chars = doc.GetCharRange(line_start, start)
  if len(chars) == 0:
    editor.ExecuteCommand('indent-to-match')
  else:
    chars = chars.replace('\t', tab_size * ' ')
    indents, fraction = divmod(len(chars), tab_size)
    if fraction == 0:
      fraction = tab_size
    else:
      fraction = tab_size - fraction
    doc.InsertChars(start, ' ' * fraction)
    _move_right(editor, fraction)

def _vs_tab_available(app=wingapi.kArgApplication):
  return app.GetActiveEditor() is not None
vs_tab.available = _vs_tab_available

########################################################################
# Line ending conversion commands

def _buffer_convert(app, filter):
  editor = app.GetActiveEditor()
  doc = editor.GetDocument()
  txt = doc.GetText()
  txt = filter(txt)
  state = editor.GetVisualState()
  doc.BeginUndoAction()
  try:
    doc.SetText(txt)
    editor.SetVisualState(state)
  finally:
    doc.EndUndoAction()

def convert_to_crlf_lineends(app=wingapi.kArgApplication):
  """Convert the current editor to use CR + LF style line endings"""

  def filter(txt):
    return '\r\n'.join(txt.splitlines())
  _buffer_convert(app, filter)

def convert_to_cr_lineends(app=wingapi.kArgApplication):
  """Convert the current editor to use CR style line endings"""

  def filter(txt):
    return '\r'.join(txt.splitlines())
  _buffer_convert(app, filter)

def convert_to_lf_lineends(app=wingapi.kArgApplication):
  """Convert the current editor to use LF style line endings"""

  def filter(txt):
    return '\n'.join(txt.splitlines())
  _buffer_convert(app, filter)

######################################################################
# Code folding utilities

def fold_python_methods():
  """Fold up all Python methods, expand all classes, and leave other fold
  points alone"""

  editor = wingapi.gApplication.GetActiveEditor()

  def _leading_space(line):
    return line[:len(line)-len(line.lstrip())]
  def _indent_size(line):
    indent = _leading_space(line)
    indent = indent.replace('\t', ' ' * 8)
    return len(indent)

  class_indents = []
  def _fold_methods(line):
    lstrip = line.lstrip()
    if len(lstrip) > 0 and not lstrip.startswith('#'):
      isize = _indent_size(line)
      while len(class_indents) > 0 and class_indents[-1] >= isize:
        class_indents.pop()
    if lstrip.startswith('class '):
      class_indents.append(isize)
      return 1
    elif lstrip.startswith('def '):
      if len(class_indents) == 0:
        return 1
      else:
        return 0
    else:
      return -1

  folded, expanded = editor.FoldUnfold(_fold_methods)
  return folded, expanded

def _folding_available():
  editor = wingapi.gApplication.GetActiveEditor()
  return editor is not None and editor.FoldingAvailable()

fold_python_methods.available = _folding_available

def fold_python_classes():
  """Fold up all Python classes but leave other fold points alone"""

  editor = wingapi.gApplication.GetActiveEditor()

  def _fold_classes(line):
    lstrip = line.lstrip()
    if lstrip.startswith('class '):
      return 0
    else:
      return -1

  folded, expanded = editor.FoldUnfold(_fold_classes)
  return folded, expanded

fold_python_classes.available = _folding_available

def fold_python_classes_and_defs():
  """Fold up all Python classes, methods, and functions but leave other fold
  points alone"""

  editor = wingapi.gApplication.GetActiveEditor()

  def _fold_classes(line):
    lstrip = line.lstrip()
    if lstrip.startswith('class ') or lstrip.startswith('def '):
      return 0
    else:
      return -1

  folded, expanded = editor.FoldUnfold(_fold_classes)
  return folded, expanded

fold_python_classes_and_defs.available = _folding_available

def vi_fold_more():
  """Approximation of zr key binding in vim"""
  
  folded, initial_expanded = fold_python_methods()
  if not folded:
    folded, expanded = fold_python_classes_and_defs()
    isinstance(initial_expanded, set)
    folded.difference_update(initial_expanded)
    if not folded:
      editor = wingapi.gApplication.GetActiveEditor()
      editor.FoldUnfold(0)
      
vi_fold_more.available = _folding_available

def vi_fold_less():
  """Approximation of zm key binding in vim"""
  
  initial_folded, expanded = fold_python_classes_and_defs()
  if not expanded:
    folded, expanded = fold_python_methods()
    expanded.difference_update(initial_folded)
    if not expanded:
      editor = wingapi.gApplication.GetActiveEditor()
      editor.FoldUnfold(1)
        
vi_fold_less.available = _folding_available


######################################################################
# A quick way to insert debug prints for those times that stepping
# through the debugger and/or using conditional breakpoints doesn't help

kWordChars = "_[]." + string.ascii_uppercase + string.ascii_lowercase + string.digits

def _getcontext(app):
  editor = app.GetActiveEditor()
  if editor is None:
    return None

  context = editor.GetSourceScope()
  if len(context) > 0:
    dirname, filename = os.path.split(context[0])
    modname, ext = os.path.splitext(filename)
  else:
    return None
  if len(context) > 1:
    lineno = context[1]
  else:
    return None
  if len(context) > 2:
    scope = modname + '.' + ''.join(context[2:])
  else:
    scope = modname

  start, end = editor.GetSelection()
  doc = editor.GetDocument()
  line_start = doc.GetLineStart(lineno)
  line_end = doc.GetLineEnd(lineno)
  linetxt = doc.GetCharRange(line_start, line_end)
  from wingutils import textutils
  var = textutils.GetNearestWord(linetxt, start - line_start, kWordChars)
  if len(var) == 0:
    return None

  return modname, lineno, scope, var

def insert_debug_print(app=wingapi.kArgApplication):
  """Insert a print statement to print a selected variable name and
  value, along with the file and line number."""
  context = _getcontext(app)
  if context is None:
    return
  modname, lineno, scope, var = context
  txt = 'print "###%s, L: %i, %s:", %s' % (scope, lineno, var, var)

  editor = app.GetActiveEditor()
  doc = editor.GetDocument()
  line_start = doc.GetLineStart(lineno)
  line_end = doc.GetLineEnd(lineno)
  linetxt = doc.GetCharRange(line_start, line_end)

  indent = ''
  for c in linetxt:
    if c in ' \t':
      indent += c
    else:
      break

  doc.InsertChars(line_end, editor.GetEol() + indent + txt)

def _IsAvailable_insert_debug_print(app=wingapi.kArgApplication):
  return _getcontext(app) is not None

######################################################################
# Other examples

def search_python_docs():
  """Do a search on the Python documentation for the selected text
  in the current editor"""

  editor = wingapi.gApplication.GetActiveEditor()
  if editor is None:
    return
  doc = editor.GetDocument()
  start, end = editor.GetSelection()
  txt = doc.GetCharRange(start, end)
  import urllib
  url = urllib.urlencode((('q', txt + ' site:docs.python.org'), ('ie', 'utf-8')))
  url = "http://www.google.com/search?" + url
  wingapi.gApplication.OpenURL(url)
  
def watch_selection():
  """Add a debug watch for the selected text in the current editor"""

  editor = wingapi.gApplication.GetActiveEditor()
  if editor is None:
    return
  doc = editor.GetDocument()
  start, end = editor.GetSelection()
  txt = doc.GetCharRange(start, end)
  txt = txt.strip()
  if not txt:
    return
  wingapi.gApplication.ExecuteCommand('watch-expression(expr="%s")' % txt)

def cc_checkout(app=wingapi.kArgApplication):
  """Check the current file out of clearcase.  This is best used with Wing
  configured to auto-reload unchanged files."""

  # See also svn.py, cvs.py, and perforce.py for examples of source code integration

  editor = app.GetActiveEditor()
  filename = editor.GetDocument().GetFilename()
  cmd = 'cleartool /checkout %s' % filename
  import os
  os.system(cmd)
  is_writable = (os.stat(filename)[stat.ST_MODE] & stat.S_IWRITE) != 0
  editor.SetReadOnly(not is_writable)

def toggle_vertical_split():
    """If editor is split, unsplit it and show the vertical tools panel.
    Otherwise, hide the vertical tools and split the editor left-right
    Assumes default windowing policy (combined toolbox & editor windows).
    Thanks to Jonathan March for this script."""
    app = wingapi.gApplication
    app.ExecuteCommand('focus-current-editor')
    if app.CommandAvailable('unsplit'):
        app.ExecuteCommand('unsplit', action='current')
        app.ExecuteCommand('show-vertical-tools')
    else:
        app.ExecuteCommand('hide-vertical-tools')
        app.ExecuteCommand('split-horizontally')
  
def toggle_toolbox_separate():
    """Toggle between moving the toolboxes to a separate window and
    the default single-window mode"""
    app = wingapi.gApplication
    import guimgr.prefs
    if app.GetPreference(guimgr.prefs.kWindowingPolicy) == 'combined-window':
      app.SetPreference(guimgr.prefs.kWindowingPolicy, 'separate-toolbox-window')
    else:
      app.SetPreference(guimgr.prefs.kWindowingPolicy, 'combined-window')
      
def insert_spaces_to_tab_stop(tab_size=0):
  """Insert spaces to reach the next tab stop (units of given tab size
  or editor's tab size if none is given)"""
  
  ed = wingapi.gApplication.GetActiveEditor()
  if ed is None:
    return
  doc = ed.GetDocument()
  
  if tab_size == 0:
    tab_size = ed.GetTabSize()
    
  start, end = ed.GetSelection()
  lineno = doc.GetLineNumberFromPosition(start)
  line_start = doc.GetLineStart(lineno)
  offset = start - line_start
  remainder = offset % tab_size
  
  insert = ' ' * (tab_size - remainder)
  if start != end:
    doc.DeleteChars(start, end-1)
  doc.InsertChars(start, ' ' * (tab_size - remainder))
  
  ed.SetSelection(start + (tab_size - remainder), start + (tab_size - remainder))
  
def insert_text(text):
  """Insert given text at current caret location, replacing any existing 
  selected text"""
  
  ed = wingapi.gApplication.GetActiveEditor()
  start, end = ed.GetSelection()
  doc = wingapi.gApplication.GetActiveDocument()
  doc.DeleteChars(start, end-1)
  doc.InsertChars(start, text)
  ed.SetSelection(start + len(text), start+len(text))

def indent_new_commment_line():
  """Enter a newline, indent to match previous line and insert a comment
  character and a space.  Assumes that auto-indent is enabled."""
  
  wingapi.gApplication.ExecuteCommand('new-line')
  wingapi.gApplication.ExecuteCommand('insert-text(text="# ")')

# Example of connecting to presave on documents so that some operation
# can be performed just before the document is saved to disk

def _connect_to_presave(doc):
  def _on_presave(filename, encoding):
    # Avoid operation when saving a copy to another location
    if filename is not None:
      return
    # Get editor and do action
    ed = wingapi.gApplication.OpenEditor(doc.GetFilename())
    if ed is not None:
      pass  # Insert your action here
  connect_id = doc.Connect('presave', _on_presave)

def _init():
  wingapi.gApplication.Connect('document-open', _connect_to_presave)
  for doc in wingapi.gApplication.GetOpenDocuments():
    _connect_to_presave(doc)

#_init()

# Example of connecting to active-window-changed on the application

def _init2():
  def _active_window_changed(win):
    """Save all documents automatically when Wing loses focus"""
    if win is None:
      docs = wingapi.gApplication.GetOpenDocuments()
      for doc in docs:
        if not doc.IsSavePoint():
          doc.Save()
  wingapi.gApplication.Connect('active-window-changed', _active_window_changed)
  
#_init2()

# Example of using arginfo to provide word list driven autocompletion
# via a script
  
def word_list_completion(word):
  """Provide simple word-list driven auto-completion on the current editor"""
  ed = wingapi.gApplication.GetActiveEditor()
  start, end = ed.GetSelection()
  doc = wingapi.gApplication.GetActiveDocument()
  doc.DeleteChars(start, end-1)
  doc.InsertChars(start, word)
  ed.SetSelection(start + len(word), start + len(word))
  
def _ArgInfo_word_list_completion():
  from wingutils import datatype
  from guiutils import formbuilder
  from command import commandmgr

  doc = wingapi.gApplication.GetActiveDocument()
  txt = doc.GetText()
  
  class CWordMap:
    def __init__(self, chars):
      self.chars = set(chars)
    def __getitem__(self, char):
      if unichr(char) in self.chars:
        return char
      else:
        return u' '
      
  trans = CWordMap(unicode(string.letters + string.digits + '_'))
  txt = txt.translate(trans)
  
  words = txt.split()
  choices = set()
  for word in words:
    choices.add(word)

  arginfo = {
    'word': commandmgr.CArgInfo(
      _("Word"), datatype.CType(''),
      formbuilder.CSmallTextGui(choices=list(choices)),
      _("Word:"), 'internal'
    )
  }
  return arginfo

word_list_completion.arginfo = _ArgInfo_word_list_completion

def smart_copy():
  """Implement a variant of clipboard copy that copies the whole
  current line if there is no selection on the editor."""
  app = wingapi.gApplication
  editor = app.GetActiveEditor()
  if editor is None:
    return
  selection = editor.GetSelection()
  if selection[1] - selection[0] > 0:
    app.ExecuteCommand('copy')
  else:
    doc = editor.GetDocument()
    lineno = doc.GetLineNumberFromPosition(selection[0])
    start = doc.GetLineStart(lineno)
    if lineno + 1 < doc.GetLineCount():
      end = doc.GetLineStart(lineno + 1)
    else:
      end = doc.GetLineEnd(lineno)
    editor.SetSelection(start, end)
    app.ExecuteCommand('copy')
    editor.SetSelection(selection[0], selection[1])
    
from command import commandmgr
from wingutils import datatype
from guimgr import keyboard

def describe_key_briefly(key):
  """ Display the commands that a key is bound to in the status area.  Does
  not fully work for the vi binding. """
  
  s = wingapi.gApplication.fSingletons
  
  key_seq = keyboard.KeySpecTextToTuple(key)

  view = s.fGuiMgr.GetActiveView()
  if view is None:
    ed = wingapi.gApplication.GetActiveEditor()
    if ed is not None:
      view = ed.fEditor
  if view is None:
    return
  
  key_maps = [s.fCmdMgr.fPrimaryKeyMap]
  try:
    view_map = view.GetKeyMap()
  except AttributeError:
    pass
  else:
    if view_map is not None:
      key_maps.insert(0, view_map)
  for key_map in key_maps:
    names = key_map.GetCommandNames(key_seq)
    if names:
      break
  
  if names:
    msg = key + ' is bound to ' + '; '.join(names)
  else:
    msg = key + ' is not bound'
  wingapi.gApplication.SetStatusMessage(msg)
  
describe_key_briefly.arginfo = {
  'key': commandmgr.CArgInfo(
    _("Key"), datatype.CType(''),
    keyboard.CKeyStrokeEntryFormlet(),
    _("Key"), 'internal'
    )
  }
    
def kill_line_with_eol(ed=wingapi.kArgEditor):
  """ Variant of emacs style kill-line command that always kills the eol 
  characters """
  
  doc = ed.GetDocument()
  start, end = ed.GetSelection()
  end_lineno = doc.GetLineNumberFromPosition(start)
  line_end = doc.GetLineEnd(end_lineno)
  if end == line_end:
    text = ''
  else:
    text = doc.GetCharRange(end, line_end)
  if text.strip() == '':
    wingapi.gApplication.ExecuteCommand('kill-line')
  else:
    wingapi.gApplication.ExecuteCommand('kill-line')
    wingapi.gApplication.ExecuteCommand('kill-line')
  