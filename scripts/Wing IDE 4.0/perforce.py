"""This is an integration with the Perforce revision control system
for Wing IDE.

Copyright (c) 2005, Kariel Sandler and Wingware, All rights reserved.

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

---------------------------

To use this module, you may have to defined some of the P4 environment
variables, either before starting Wing or by setting them in Project
Properties.  For example:

P4PORT=1666
P4CLIENT=<yourclientname>

This code assumes you have already set up a P4 depot by running the
P4 server and configured a P4 client directory with 'p4 client'.

---------------------------

This code was contributed by Kariel Sandler and modified by
Wingware.

"""

import time
import wingapi

_AI = wingapi.CArgInfo

import os
import os.path
import stat
import sys

from wingutils import datatype
from guiutils import formbuilder

import gettext
_ = gettext.translation('scripts_perforce', fallback = 1).ugettext
_i18n_module = 'scripts_perforce'

app = wingapi.gApplication

# This is a disabled example script
_ignore_scripts=1


#########################################################################  
# Commands
#########################################################################  

class MWT(object):
  """
    Memoize With Timeout Decorator
    by Simon Wittber.
    taken from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/325905
    """
  _caches = {}
  _timeouts = {}

  def __init__(self,timeout=2):
    self.timeout = timeout

  def collect(self):
    """Clear cache of results which have timed out"""
    for func in self._caches:
      cache = {}
      for key in self._caches[func]:
        if (time.time() - self._caches[func][key][1]) < self._timeouts[func]:
          cache[key] = self._caches[func][key]
      self._caches[func] = cache

  def __call__(self, f):
    self.cache = self._caches[f] = {}
    self._timeouts[f] = self.timeout

    def func(*args, **kwargs):
      kw = kwargs.items()
      kw.sort()
      key = (args, tuple(kw))
      try:
        v = self.cache[key]
        if (time.time() - v[1]) > self.timeout:
          raise KeyError
      except KeyError:
        v = self.cache[key] = f(*args,**kwargs),time.time()
      return v[0]

    return func

def _sync_run_cmd(cmd, to_stdin=None):
  """Run command syncronously.  Returns output or None if failed, in which
    case the failure is logged."""

  err, txt = wingapi.gApplication.ExecuteCommandLine(cmd, None, to_stdin, 5.0)
  if err == 0:
    return txt
  elif err == 2:
    print "Timeout on: %s" % cmd    
    if len(txt) > 0:
      print txt
    return None
  else:
    print "Command failed: %s" % cmd
    print "Err=%s" % str(err)
    if len(txt) > 0:
      print txt
    return None

#old-style decorators (not python2.4 or later)
_sync_run_cmd = MWT(0.5)(_sync_run_cmd)


def _p4_fstat(filename):
  return _sync_run_cmd('p4 -d "%s" fstat "%s"' % (os.path.dirname(filename), filename))

def _in_src_ctrl(filename):
  s = _p4_fstat(filename)
  return s is not None and s[:3] == '...'

def _in_src_ctrl_dir(filename):
  s = _p4_fstat(filename)
  return s is not None and not 'not under client' in s

def _is_writable(filename):
  return 0 != (os.stat(filename)[stat.ST_MODE] & stat.S_IWRITE)

def _get_editors(filename):
  loc = wingapi.location.CreateFromName(filename)
  return wingapi.gApplication.fSingletons.fEditMgr.GetEditors(loc)

def _set_writable(filename, is_writable = True):
  for ed in _get_editors(filename):
    ed.SetReadOnly(not is_writable)

def _is_unsaved(filename):
  for ed in _get_editors(filename):
    if ed.IsModified():
      return True
  return False

def _run_command(op, *args):
  __run_async(op, '', __message_completion, '-d', os.path.dirname(args[-1]), op, *args)

CONTEXTS = [wingapi.kContextProject(),
            wingapi.kContextNewMenu(_("Pe_rforce"), 0)]

def perforce_edit(filenames=wingapi.kArgFilename):
  """Perform perforce update (get latest revision/sync to head) on the given files or directories"""
  _run_command('edit', *filenames)
  for filename in filenames:
    _set_writable(filename)

def _perforce_edit_available(filenames=wingapi.kArgFilename):
  for filename in filenames:
    if not _in_src_ctrl(filename):
      return False
    if 0 != (os.stat(filename)[stat.ST_MODE] & stat.S_IWRITE):
      return False
  return len(filenames) > 0

perforce_edit.available = _perforce_edit_available
perforce_edit.label = _('Perforce _Edit')

perforce_edit.contexts = CONTEXTS

def perforce_submit(message):
  """Perform perforce submit on the given files or directories
    after prompting for log message"""

  filenames = wingapi.gApplication.GetCurrentFiles()
  depot_filenames = []
  for filename in filenames:
    s = _p4_fstat(filename)
    if s is None:
      print "Could not submit: Failed on: p4 fstat %s" % filename
      return
    depot_filenames.append(s.split('\n...')[0].split('depotFile ')[1])

  cmd = 'p4 -d "%s" submit -d "%s"' % (os.path.dirname(filenames[0]), __unicode_to_fs(message))
  output = _sync_run_cmd(cmd)
  if output is None:
    print 'Could not submit: Failed on: %s' %  cmd
    return        
  __message_completion('p4-submission', tuple(depot_filenames),
                       '', output, '', None, 0)
  for filename in filenames:
    _set_writable(filename, False)

def _perforce_submit_available(filenames=wingapi.kArgFilename):
  for filename in filenames:
    if not _in_src_ctrl(filename):
      return False
    if not _is_writable(filename):
      return False
  return len(filenames) > 0

perforce_submit.available = _perforce_submit_available
perforce_submit.label = _('Perforce S_ubmit')
perforce_submit.arginfo = {
  'message': _AI(_("Log message to attach to this revision"), datatype.CType(''), 
                 formbuilder.CLargeTextGui(allow_newlines=True)),
}
perforce_submit.contexts = CONTEXTS

def perforce_add(filenames=wingapi.kArgFilename):
  """Perform perforce add on the given files or directories"""
  _run_command('add', *filenames)

def _perforce_add_available(filenames=wingapi.kArgFilename):
  for filename in filenames:
    if not _in_src_ctrl_dir(filename) or _in_src_ctrl(filename):
      return False
  return len(filenames) > 0

perforce_add.available = _perforce_add_available
perforce_add.label = _('Perforce _Add')
perforce_add.contexts = CONTEXTS

def perforce_sync(filenames=wingapi.kArgFilename):
  """Perform perforce update (get latest revision/sync to head) on the given files or directories"""
  _run_command('sync', *filenames)

def _perforce_sync_available(filenames=wingapi.kArgFilename):
  for filename in filenames:
    if not _in_src_ctrl(filename):
      return False
  return len(filenames) > 0

perforce_sync.available = _perforce_sync_available
perforce_sync.label = _('Perforce S_ync (Get Latest Revision)')
perforce_sync.contexts = CONTEXTS

def perforce_whose_line(editor=wingapi.kArgEditor):
  selection = editor.GetSelection()
  document = editor.GetDocument()
  filename = document.GetFilename()
  first, last = map(document.GetLineNumberFromPosition, selection)

  annotate_str = _sync_run_cmd(
    'p4 -d "%s" annotate -q "%s"' % (os.path.dirname(filename), filename))
  if sys.platform == 'win32':
    # p4 on win32 apparently puts \r\r\n at end of each line
    annotate_str = annotate_str.replace('\r\r\n', '\r\n')
  filelog_str = _sync_run_cmd(
    'p4 -d "%s" filelog "%s"' % (os.path.dirname(filename), filename))

  revisions = set([line.split(':')[0] for line in annotate_str.splitlines()[first:last+1]])
  filelog_lines = [line.split('#')[1] for line in filelog_str.splitlines()
                   if '#' in line and ' by ' in line]
  whose = {}
  for line in filelog_lines:
    if line.split()[0] not in revisions:
      continue
    who = line.split(' by ')[1].split('@')[0]
    what = line.split(' on ')[0].split()[-1]
    whose.setdefault(who, set()).add(what)

  wingapi.gApplication.ShowMessageDialog(
    'Whose line:',
    ', '.join([who+' ('+', '.join(what)+')' for who, what in whose.iteritems()]))

perforce_whose_line.available = _perforce_sync_available
perforce_whose_line.label = _('Perforce: _Whose line is it?')
perforce_whose_line.contexts = [wingapi.kContextEditor()]

def perforce_diff(filenames=wingapi.kArgFilename):
  """Perform perforce diff on the given files or directories."""
  app = wingapi.gApplication
  _run_command('diff', *filenames)

perforce_diff.available = _perforce_submit_available
perforce_diff.label = _('Perforce _Diff')
perforce_diff.contexts = CONTEXTS

def perforce_revert(filenames=wingapi.kArgFilename):
  """Perform perforce log on the given files or directories"""
  _run_command('revert', *filenames)
  time.sleep(0.1)
  refresh_ro(filenames)

def _perforce_revert_available(filenames=wingapi.kArgFilename):
  if not _perforce_submit_available(filenames):
    return False
  for filename in filenames:
    if _is_unsaved(filename):
      return False
  return len(filenames) > 0

perforce_revert.available = _perforce_revert_available
perforce_revert.label = _('Perforce _Revert')
perforce_revert.contexts = CONTEXTS

def perforce_revert_if_unchanged(filenames=wingapi.kArgFilename):
  """Perform perforce log on the given files or directories"""
  args = ['-a'] + filenames
  _run_command('revert', *args)
  time.sleep(0.1)
  refresh_ro(filenames)

perforce_revert_if_unchanged.available = _perforce_revert_available
perforce_revert_if_unchanged.label = _('Perforce Re_vert If Unchanged')
perforce_revert_if_unchanged.contexts = CONTEXTS

def perforce_log(filenames=wingapi.kArgFilename):
  """Perform perforce log on the given files or directories"""
  _run_command('filelog', *filenames)

perforce_log.available = _perforce_sync_available
perforce_log.label = _('Perforce _Log')
perforce_log.contexts = CONTEXTS

def refresh_ro(filenames=wingapi.kArgFilename):
  for filename in filenames:
    _set_writable(filename, _is_writable(filename))

def _refresh_ro_available(filenames=wingapi.kArgFilename):
  return len(filenames) > 0

refresh_ro.available = _refresh_ro_available
refresh_ro.label = _('Refresh File Pe_rmissions')
refresh_ro.contexts = [wingapi.kContextProject(),
                       wingapi.kContextNewMenu(_("Pe_rforce"), 1)]

def perforce_status(filenames=wingapi.kArgFilename):
  for filename in filenames:
    result = _p4_fstat(filename)
    if result is None:
      continue

    wingapi.gApplication.ShowMessageDialog(
      'Result of Perforce Status',
      result)

perforce_status.available = _refresh_ro_available
perforce_status.label = _('Perforce _Status')
perforce_status.contexts = CONTEXTS

def perforce_cancel():
  """Cancel pending Perforce commands that are running in the background 
  but have not yet completed"""
  i = len(gCommands.all_pending_commands())
  for handler in gCommands.all_pending_commands():
    handler.Terminate(kill=True)
    gCommands.remove_pending_command(handler)
  wingapi.gApplication.SetStatusMessage("Canceled %i Perforce Request(s)" % i)
def _perforce_cancel_available():
  return len(gCommands.all_pending_commands()) > 0
perforce_cancel.available = _perforce_cancel_available
perforce_cancel.label = _("Cancel Active Re_quests")
perforce_cancel.contexts = [wingapi.kContextNewMenu(_("Pe_rforce"), 8)]

#########################################################################  
# Utilities
#########################################################################  

class _CCommandStatus:
  """Manage multiple pending Perforce commands for single status display"""

  def __init__(self):
    self.fPendingCommands = {}
    self.fUpdatePos = 0
    self.fLastUpdate = 0

  def add_pending_command(self, handler, op, dirname):
    if len(self.fPendingCommands) == 0:
      self.fUpdatePos = 0
      self.fLastUpdate = 0
    self.fPendingCommands[handler] = (op, dirname)

  def remove_pending_command(self, handler):
    del self.fPendingCommands[handler]

  def all_pending_commands(self):
    return self.fPendingCommands.keys()

  def update_status(self):
    # Somewhat of a hack pending better shared status support in Wing
    if len(self.fPendingCommands) == 0:
      return
    now = time.time()
    if now - self.fLastUpdate > 1.0:
      self.fLastUpdate = now
      self.fUpdatePos += 1
      if self.fUpdatePos > 40:
        self.fUpdatePos = 1
      t = '*' * self.fUpdatePos
      if len(self.fPendingCommands) == 1:
        op, dirname = self.fPendingCommands.values()[0]
        title = ' ' + op.title()
      else:
        title = ' (%i cmds)' % len(self.fPendingCommands)
      wingapi.gApplication.SetStatusMessage("Perforce %s %s" % (title, t))

gCommands = _CCommandStatus()

def __run_async(*a):
  __run_async_cmd('p4', *a)

def __run_async_cmd(cmd, op, dirname, cb, *args):

  handler = wingapi.gApplication.AsyncExecuteCommandLine(cmd, dirname, *args)
  gCommands.add_pending_command(handler, op, dirname)

  def poll():
    if handler.terminated:
      return False
    if handler.Iterate():
      title = _("Perforce %s Result") % op.title()
      stdout, stderr, err, status = handler.Terminate()
      wingapi.gApplication.ClearStatusMessage()
      gCommands.remove_pending_command(handler)
      cb(op, args, dirname, stdout, stderr, err, status)
      return False
    else:
      gCommands.update_status()
      return True

  wingapi.gApplication.InstallTimeout(100, poll)

def __fs_to_unicode(txt):
  if isinstance(txt, unicode):
    return txt
  try:
    return unicode(txt, wingapi.config.kFileSystemEncoding)
  except:
    return unicode(txt, 'latin-1', 'replace')

def __unicode_to_fs(txt):
  if not isinstance(txt, unicode):
    txt = __to_unicode(txt)
  try:
    return txt.encode(wingapi.config.kFileSystemEncoding)
  except:
    return txt.encode('latin-1', 'replace')

def __to_unicode(txt):
  if isinstance(txt, unicode):
    return txt
  from wingutils import mime
  try:
    return unicode(txt, mime.GetSystemTextEncoding())
  except:
    return unicode(txt, 'latin-1', 'replace')

_kTransientResultBuffers = datatype.CValueDef(
  'perforce', 'transient-result-buffers', 
  _('Set this to show results of CVS operations in transient editors '
    'that auto-close when not visible.'),
  0, datatype.CBoolean(), formbuilder.CBooleanGui()
)

wingapi.gApplication.fSingletons.fFileAttribMgr.AddDefinition(_kTransientResultBuffers)

def __message_completion(op, args, dirname, stdout, stderr, err, status):

  title = _("Perforce Results")
  if stdout.strip() == '' and stderr.strip() == '':
    stdout = "(No output)"

  alert = False
  dialog = False
  xtra = None
  if err is not None: # or status not in (None, 0, 256):
    alert = True
    dialog = True
  if op in ('status', 'log'):
    alert = True
  elif op == 'submit' and stderr.lower().find('up-to-date check failed') >= 0:
    alert = True
    dialog = True
    xtra = _("Perforce found concurrent changes -- do an update before submitting")
  if dialog:
    dtitle = _("Perforce Error")
    if err is not None:
      msg = _("Perforce %s failed to execute.  errno=%i") % (op.title(), err)
    else:
      msg = _("Perforce %s returned unexpected exit status=%i") % (op.title(), status)      
    if xtra is not None:
      msg += '\n' + xtra
    wingapi.gApplication.ShowMessageDialog(dtitle, msg)

  result = []
  result.append('*' * 60)
  result.append(_("Executing: %s") % (' ' .join([__fs_to_unicode(i) for i in (op,) + args])))
  result.append(_("In: %s") % __fs_to_unicode(dirname))
  if len(stderr.strip()) > 0:
    result.append(_("Errors/Warnings (stderr):"))
    result.append('')
    result.append(__to_unicode(stderr))
    result.append('=' * 60)
  result.append(_("Results (stdout):"))
  result.append('')
  result.append(__to_unicode(stdout))
  if err is not None:
    result.append('')
    result.append(_("Error executing command.  errno=%i:") % err)
  if status is not None:
    result.append(_("Exit status=%i") % status)
  result.append('')
  result = '\n'.join(result)

  app = wingapi.gApplication

  # Only raise the result area the first time or if showing info user
  # likely wants to see right away
  sticky = not app.fSingletons.fFileAttribMgr[_kTransientResultBuffers]
  if alert:
    editor = app.ScratchEditor(title, 'text/plain', sticky=sticky)
  else:
    editor = app.ScratchEditor(title, 'text/plain', raise_view=False, sticky=sticky)
    if editor is None:
      editor = app.ScratchEditor(title, 'text/plain', sticky=sticky)

  doc = editor.GetDocument()
  lineno = doc.GetLineCount()
  doc.InsertChars(doc.GetLength(), result)

  editor.ScrollToLine(lineno-1, select=1, pos='top')
