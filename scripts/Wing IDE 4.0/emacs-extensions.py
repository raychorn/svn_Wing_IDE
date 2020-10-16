"""This file contains scripts that add emacs-like functionality not 
found in Wing's internal emacs support layer.

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

import os
import wingapi

# Scripts can be internationalize with gettext.  Strings to be translated
# are sent to _() as in the code below.
import gettext
_ = gettext.translation('scripts_emacs_extensions', fallback = 1).ugettext

# This special attribute is used so that the script manager can translate
# also docstrings for the commands found here
_i18n_module = 'scripts_emacs_extensions'

######################################################################
def add_change_log_entry(user_name=None, email=None, changelog=None, 
                         changed_file=None, func=None,
                         other_window=False, new_entry=False):
  """Add a change log entry"""
  
  kItemDelimiter = '\n        * '
  kDateFormat = '%Y-%m-%d'
  kDefaultUserName = os.environ.get('USERNAME', os.environ.get('USER', 'Unknown Name'))
  kDefaultEmail = '<%s@%s>' % (os.environ.get('USER', 'unknown'), 
                               os.environ.get('HOSTNAME', 'localhost'))
  app = wingapi.gApplication
  
  doc = app.GetActiveDocument()
  curfile = None
  if doc is not None:
    filename = doc.GetFilename()
    if not filename.startswith('unknown:'):
      from wingutils import location # undocumented
      dirname, curfile = location.SplitPathUrl(filename)
  
  if user_name is None:
    user_name = kDefaultUserName
  if email is None:
    email = kDefaultEmail
  if changelog is None:
    proj = wingapi.gApplication.GetProject()
    changelog = proj.GetFilename()
    changelog = os.path.join(os.path.dirname(changelog), 'ChangeLog')
  if changed_file is None:
    doc = wingapi.gApplication.GetActiveDocument()
    changed_file = os.path.basename(doc.GetFilename())
  if func is None:
    ed = wingapi.gApplication.GetActiveEditor()
    scope_info = ed.GetSourceScope()
    func = '.'.join(scope_info[2:])
    
  import time
  stime = time.strftime(kDateFormat)
  header = "%s  %s  %s" % (stime, user_name, email)
  editor = app.OpenEditor(changelog, raise_window=True)
  if editor is None:
    return
  doc = editor.GetDocument()
  txt = doc.GetText()
  pos = txt.find(header)
  if pos == -1 or new_entry:
    doc.InsertChars(0, header + '\n')
    pos = len(header) + 1
    doc.InsertChars(pos, '\n\n')
  else:
    pos += len(header) + 1

  if curfile is not None:
    item = kItemDelimiter + curfile
  if func is not None:
    item += ' (%s)' % func
  item += ': '
  doc.InsertChars(pos, item)
  editor.SetSelection(pos + len(item), pos + len(item))
