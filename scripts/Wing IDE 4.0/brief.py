"""Scripts that provide functionality specific to the Brief key binding.

Copyright (c) 2005, Wingware All rights reserved.

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
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE."""

import wingapi
from guiutils import formbuilder
from wingutils import datatype


def toggle_mark_command(style="char", select_right=0):
  """Change between text-marking and non-text-marking mode.  Style is
  "char" for stream select, "block" for rectangular select, and "line" for line select.
  Set select_right=1 to select the character to right of the cursor
  when marking is toggled on."""
  
  app = wingapi.gApplication
  editor = app.GetActiveEditor()
  if editor.fEditor._fSelectMode is not None:
    app.ExecuteCommand('stop-mark-command')
  else:
    # Select right isn't quite the same because the editor
    # doesn't support Brief's cursor+1 selection style
    if select_right:
      app.ExecuteCommand('forward-char')
    app.ExecuteCommand('set-mark-command', unit=style)
    if select_right:
      app.ExecuteCommand('backward-char')

def _toggle_mark_command_available():
  app = wingapi.gApplication
  editor = app.GetActiveEditor()
  return editor is not None
  
toggle_mark_command.available = _toggle_mark_command_available

_last_home_operation = (None, 0, 0)
_last_home_count = 0

def cursor_home():
  """Bring cursor to start of line, to start of visible area, or to 
  start of document each successive consecutive invocation of this
  command."""
  
  global _last_home_operation
  global _last_home_count

  app = wingapi.gApplication
  editor = wingapi.gApplication.GetActiveEditor()
  doc = editor.GetDocument()

  start, end = editor.GetSelection()
  if _last_home_operation == (doc.GetFilename(), start, end):
    _last_home_count += 1
  else:
    _last_home_count = 1
    
  if _last_home_count == 1:
    app.ExecuteCommand('beginning-of-line')

  elif _last_home_count == 2:
    lineno = editor.GetFirstVisibleLine()
    start = doc.GetLineStart(lineno)
    editor.SetSelection(start, start)

  else:
    app.ExecuteCommand('start-of-document')

  start, end = editor.GetSelection()
  _last_home_operation = (doc.GetFilename(), start, end)
  
_last_end_operation = (None, 0, 0)
_last_end_count = 0

def cursor_end():
  """Bring cursor to end of line, to end of visible area, or to 
  end of document each successive consecutive invocation of this
  command."""
  
  global _last_end_operation
  global _last_end_count

  app = wingapi.gApplication
  editor = wingapi.gApplication.GetActiveEditor()
  doc = editor.GetDocument()

  start, end = editor.GetSelection()
  if _last_end_operation == (doc.GetFilename(), start, end):
    _last_end_count += 1
  else:
    _last_end_count = 1
    
  if _last_end_count == 1:
    app.ExecuteCommand('end-of-line')

  elif _last_end_count == 2:
    lineno = editor.GetFirstVisibleLine()
    # Reaching through API:
    num_lines = editor.fEditor._fScint.lines_on_screen()
    lineno += num_lines - 1
    doc = editor.GetDocument()
    end = doc.GetLineEnd(lineno)
    editor.SetSelection(end, end)
 
  else:
    app.ExecuteCommand('end-of-document')

  start, end = editor.GetSelection()
  _last_end_operation = (doc.GetFilename(), start, end)
  
_kBookmarkAttrib = datatype.CValueDef(
  'gui', 'named-bookmarks',
  'Named bookmarks',
  {},
  datatype.CDict(datatype.CFixed(datatype.CType(1), 
                                 datatype.CDict(datatype.CType(''), 
                                                datatype.CAny()))),
  formbuilder.CSmallTextGui() # Not used here
)
wingapi.gApplication.fSingletons.fFileAttribMgr.AddDefinition(_kBookmarkAttrib)

def _bookmark_available(editor=wingapi.kArgEditor):
  app = wingapi.gApplication
  editor = app.GetActiveEditor()
  return editor is not None

def _bookmark(num):
  app = wingapi.gApplication
  editor = app.GetActiveEditor()
  fn = editor.GetDocument().GetFilename()
  bookmarks = app.fSingletons.fFileAttribMgr[_kBookmarkAttrib]
  bookmarks[num] = (fn, editor.GetVisualState())
  app.fSingletons.fFileAttribMgr[_kBookmarkAttrib] = bookmarks

def _goto_bookmark_available(num):
  app = wingapi.gApplication
  bookmarks = app.fSingletons.fFileAttribMgr[_kBookmarkAttrib]
  bookmarks.has_key(num)

def _goto_bookmark(num):
  app = wingapi.gApplication
  bookmarks = app.fSingletons.fFileAttribMgr[_kBookmarkAttrib]
  try:
    fn, state = bookmarks[num]
  except KeyError:
    app.ShowMessageDialog('Undefined bookmark',
                          'Bookmark %i has not been defined' % num)
    return
  editor = app.OpenEditor(fn)
  editor.SetVisualState(state)
  
def bookmark_0():
  """Set bookmark '0'"""
  _bookmark(0)
bookmark_0.available = _bookmark_available
def bookmark_1():
  """Set bookmark '1'"""
  _bookmark(1)
bookmark_1.available = _bookmark_available
def bookmark_2():
  """Set bookmark '2'"""
  _bookmark(2)
bookmark_2.available = _bookmark_available
def bookmark_3():
  """Set bookmark '3'"""
  _bookmark(3)
bookmark_3.available = _bookmark_available
def bookmark_4():
  """Set bookmark '4'"""
  _bookmark(4)
bookmark_4.available = _bookmark_available
def bookmark_5():
  """Set bookmark '5'"""
  _bookmark(5)
bookmark_5.available = _bookmark_available
def bookmark_6():
  """Set bookmark '6'"""
  _bookmark(6)
bookmark_6.available = _bookmark_available
def bookmark_7():
  """Set bookmark '7'"""
  _bookmark(7)
bookmark_7.available = _bookmark_available
def bookmark_8():
  """Set bookmark '8'"""
  _bookmark(8)
bookmark_8.available = _bookmark_available
def bookmark_9():
  """Set bookmark '9'"""
  _bookmark(9)
bookmark_9.available = _bookmark_available

def goto_bookmark_0():
  """Go to bookmark '0'"""
  _goto_bookmark(0)
goto_bookmark_0.available = lambda: _bookmark_available(0)
def goto_bookmark_1():
  """Go to bookmark '1'"""
  _goto_bookmark(1)
goto_bookmark_1.available = lambda: _bookmark_available(1)
def goto_bookmark_2():
  """Go to bookmark '2'"""
  _goto_bookmark(2)
goto_bookmark_2.available = lambda: _bookmark_available(2)
def goto_bookmark_3():
  """Go to bookmark '3'"""
  _goto_bookmark(3)
goto_bookmark_3.available = lambda: _bookmark_available(3)
def goto_bookmark_4():
  """Go to bookmark '4'"""
  _goto_bookmark(4)
goto_bookmark_4.available = lambda: _bookmark_available(4)
def goto_bookmark_5():
  """Go to bookmark '5'"""
  _goto_bookmark(5)
goto_bookmark_5.available = lambda: _bookmark_available(5)
def goto_bookmark_6():
  """Go to bookmark '6'"""
  _goto_bookmark(6)
goto_bookmark_6.available = lambda: _bookmark_available(6)
def goto_bookmark_7():
  """Go to bookmark '7'"""
  _goto_bookmark(7)
goto_bookmark_7.available = lambda: _bookmark_available(7)
def goto_bookmark_8():
  """Go to bookmark '8'"""
  _goto_bookmark(8)
goto_bookmark_8.available = lambda: _bookmark_available(8)
def goto_bookmark_9():
  """Go to bookmark '9'"""
  _goto_bookmark(9)
goto_bookmark_9.available = lambda: _bookmark_available(9)

SC_SEL_STREAM=0
SC_SEL_RECTANGLE=1
SC_SEL_LINES=2
