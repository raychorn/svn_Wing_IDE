"""Scripts that extend the debugger in various ways.

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

# Scripts can be internationalize with gettext.  Strings to be translated
# are sent to _() as in the code below.
import gettext
_ = gettext.translation('scripts_debugger_extensions', fallback = 1).ugettext

# This special attribute is used so that the script manager can translate
# also docstrings for the commands found here
_i18n_module = 'scripts_debugger_extensions'

def set_breaks_from_markers(app=wingapi.kArgApplication):
  """Scan current file for markers in the form %BP% and places breakpoints on
  all lines where those markers are found. A conditional breakpoint can be set
  if a condition follows the marker, for example %BP%:x > 10. Removes all old
  breakpoints first."""

  kTagFormat = '%BP%'
  
  editor = app.GetActiveEditor()
  doc = editor.GetDocument()
  filename = doc.GetFilename()
  
  debug = app.GetDebugger()
  runstate = debug.GetCurrentRunState()
  
  runstate.ClearAllBreaks()
  txt = doc.GetText()
  lines = txt.splitlines()
  for i, line in enumerate(lines):
    pos = line.find(kTagFormat)
    if pos >= 0:
      pos += len(kTagFormat)
      if len(line) > pos and line[pos] == ':':
        cond = line[pos+1:].strip()
      else:
        cond = None
      runstate.SetBreak(filename, i + 1, cond=cond)
      
      