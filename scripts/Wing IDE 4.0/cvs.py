"""This is an integration with the CVS revision control system.

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
 
import time
import wingapi

_AI = wingapi.CArgInfo

import os
import sys
from wingutils import datatype
from wingutils import location
from guiutils import formbuilder
from guiutils import dialogs
from guimgr import messages
from proj import attribs

import gettext
_ = gettext.translation('scripts_cvs', fallback = 1).ugettext
_i18n_module = 'scripts_cvs'

app = wingapi.gApplication

# This is a disabled example script
_ignore_scripts=1


#########################################################################  
# Commands
#########################################################################  

def cvs_update(filenames=wingapi.kArgFilename):
  """Perform cvs update on the given files or directories"""
  __apply_cvs_op(filenames, 'update', cb=__message_completion)
   
def _cvs_update_available(filenames=wingapi.kArgFilename):
  if filenames is None or len(filenames) == 0:
    return False
  for filename in filenames:
    if not wingapi.IsUrl(filename):
      dir, version, date, flags = __read_entries_file(filename)
      if version is not None:
        return True
  return False
cvs_update.available = _cvs_update_available
cvs_update.label = _('CVS _Update')

cvs_update.contexts = [wingapi.kContextEditor(), 
                       wingapi.kContextProject(),
                       wingapi.kContextNewMenu(_("_CVS"), 1)]

def cvs_diff(filenames=wingapi.kArgFilename):
  """Perform cvs diff on the given files or directories.  The form of diff
  is controlled from the options dialog."""
  app = wingapi.gApplication
  diff_type = app.fSingletons.fFileAttribMgr[_kDiffTypeAttrib]
  if diff_type == 'default':
    cvs_ndiff(filenames)
  elif diff_type == 'context':
    cvs_cdiff(filenames)
  else:
    cvs_udiff(filenames)
   
cvs_diff.available = _cvs_update_available
cvs_diff.label = _('CVS _Diff')
cvs_diff.contexts = [wingapi.kContextEditor(), 
                     wingapi.kContextProject(),
                     wingapi.kContextNewMenu(_("_CVS"), 2)]

def cvs_ndiff(filenames=wingapi.kArgFilename):
  """Perform cvs diff on the given files or directories"""
  __apply_cvs_op(filenames, 'diff', cb=__diff_completion)
   
cvs_ndiff.available = _cvs_update_available

def cvs_udiff(filenames=wingapi.kArgFilename):
  """Perform cvs diff -u on the given files or directories"""
  __apply_cvs_op(filenames, 'diff -u', cb=__diff_completion)
   
cvs_udiff.available = _cvs_update_available

def cvs_cdiff(filenames=wingapi.kArgFilename):
  """Perform cvs diff -c on the given files or directories"""
  __apply_cvs_op(filenames, 'diff -c', cb=__diff_completion)
   
cvs_cdiff.available = _cvs_update_available

def cvs_diff_recent(filenames=wingapi.kArgFilename):
  """Perform cvs diff between the current checked out repository 
   revision of the file and the previous revision before that."""
  filename = filenames[0]
  dir, version, date, flags = __read_entries_file(filename)
  parts = version.split('.')
  parts[-1] = str(int(parts[-1]) - 1)
  ver = '.'.join(parts)
  app = wingapi.gApplication
  diff_type = app.fSingletons.fFileAttribMgr[_kDiffTypeAttrib]
  if diff_type == 'default':
    darg = ''
  elif diff_type == 'context':
    darg = '-c '
  else:
    darg = '-u '
  __apply_cvs_op(filenames, 'diff %s-r%s -r%s' % (darg, ver, version), 
                 cb=__diff_completion)
   
def _cvs_diff_recent_available(filenames=wingapi.kArgFilename):
  if len(filenames) != 1:
    return False
  filename = filenames[0]
  dir, version, date, flags = __read_entries_file(filename)
  if version is None or dir == 'D':
    return False
  parts = version.split('.')
  return len(parts) > 1 and int(parts[-1]) > 1

cvs_diff_recent.available = _cvs_diff_recent_available
cvs_diff_recent.label = _('Show Last Re_vision Diffs')
cvs_diff_recent.contexts = [wingapi.kContextNewMenu(_("_CVS"), 2)]

def cvs_log(filenames=wingapi.kArgFilename):
  """Perform cvs log on the given files or directories"""
  __apply_cvs_op(filenames, 'log', cb=__message_completion)
   
cvs_log.available = _cvs_update_available
cvs_log.label = _('CVS _Log')
cvs_log.contexts = [wingapi.kContextEditor(), 
                    wingapi.kContextProject(),
                    wingapi.kContextNewMenu(_("_CVS"), 3)]

def cvs_status(filenames=wingapi.kArgFilename):
  """Perform cvs status on the given files or directories"""
  __apply_cvs_op(filenames, 'status', cb=__message_completion)
   
cvs_status.available = _cvs_update_available
cvs_status.label = _('CVS _Status')
cvs_status.contexts = cvs_log.contexts

def cvs_commit(message):
  """Perform cvs commit on the given files or directories"""
  __apply_cvs_op(wingapi.gApplication.GetCurrentFiles(), 'commit',
                 cb=__message_completion, message=message)
   
cvs_commit.available = _cvs_update_available
cvs_commit.label = _('CVS _Commit')
cvs_commit.arginfo = {
  'message': _AI(_("Log message to attach to this revision"), datatype.CType(''), 
                 formbuilder.CLargeTextGui(allow_newlines=True)),
}

def cvs_commit_prompt():
  """Perform cvs commit on the given files or directories
  after prompting for log message"""
  filenames = wingapi.gApplication.GetCurrentFiles()
  roots, protocols = __check_roots(filenames)  
  if not __ssh_add_warning(protocols):
    return
  else:
    wingapi.gApplication.ExecuteCommand(cvs_commit)
   
cvs_commit_prompt.available = _cvs_update_available
cvs_commit_prompt.label = _('CVS _Commit')
cvs_commit_prompt.contexts = cvs_update.contexts

def cvs_add(filenames=wingapi.kArgFilename):
  """Perform cvs add on the given files or directories"""
  __apply_cvs_op(filenames, 'add', cb=__message_completion)
   
def _cvs_add_available(filenames=wingapi.kArgFilename):
  if filenames is None or len(filenames) == 0:
    return False
  for filename in filenames:
    if not wingapi.IsUrl(filename):
      dir, version, date, flags = __read_entries_file(filename)
      if version is None:
        return True
  return False
cvs_add.available = _cvs_add_available
cvs_add.label = _('CVS _Add')
cvs_add.contexts = [wingapi.kContextEditor(), 
                    wingapi.kContextProject(),
                    wingapi.kContextNewMenu(_("_CVS"))]

def cvs_cancel():
  """Cancel pending CVS commands that are running in the background 
  but have not yet completed"""
  i = len(gCommands.all_pending_commands())
  for handler in gCommands.all_pending_commands():
    handler.Terminate(kill=True)
    gCommands.remove_pending_command(handler)
  wingapi.gApplication.SetStatusMessage("Canceled %i CVS Request(s)" % i)
def _cvs_cancel_available():
  return len(gCommands.all_pending_commands()) > 0
cvs_cancel.available = _cvs_cancel_available
cvs_cancel.label = _("Canc_el Active Requests")
cvs_cancel.contexts = [wingapi.kContextNewMenu(_("_CVS"), 4)]

def cvs_login(password):
  """Login to CVS pserver"""
  global gPassword
  gPassword = password
  filenames = wingapi.gApplication.GetCurrentFiles()
  def doit():
    roots, protocols = __check_roots(filenames, valid_protocols=['pserver'])
    for r in roots.keys():
      __do_login(r)
    return False
  # This lets the login prompt go away first
  wingapi.gApplication.InstallTimeout(1, doit)
  
def _cvs_login_available():
  filenames = wingapi.gApplication.GetCurrentFiles()
  roots, protocols = __check_roots(filenames, valid_protocols=['pserver'])
  return protocols.has_key('pserver')
cvs_login.available = _cvs_login_available
cvs_login.label = _("Login to PServer")
# Disabled because it doesn't work -- see __do_login.  pserver anon CVS
# at least for sourceforge.net does work w/o login.
#cvs_login.contexts = [wingapi.kContextNewMenu(_("_CVS"), 4)]

def cvs_configure():
  """Configure CVS options"""
  global gOptionsDialog
  if gOptionsDialog is not None:
    gOptionsDialog.Show()
    return
  gOptionsDialog = COptionsDialog()
  gOptionsDialog.Run()

cvs_configure.label = _("_Options...")
cvs_configure.contexts = [wingapi.kContextNewMenu(_("_CVS"), 5)]

#########################################################################  
# Utilities
#########################################################################  

# Used for pserver repositories only
gPassword = None

def __do_login(root):

  wingapi.gApplication.SetStatusMessage(_("Logging in..."))
  cmd = wingapi.gApplication.fSingletons.fFileAttribMgr[_kCVSCommand]
  args = ['-d', root, 'login']
  handler = wingapi.gApplication.AsyncExecuteCommandLine(cmd, os.getcwd(), *args)
  gCommands.add_pending_command(handler, 'login', '')

  end = time.time() + 5.0
  sent_pass = []

  def poll():

    if handler.terminated:
      return False

    if time.time() > end:
      wingapi.gApplication.SetStatusMessage(_("Login failed: Time out"))
      handler.Terminate()
      gCommands.remove_pending_command(handler)
      return False

    if handler.Iterate():
      stdout, stderr, err, status = handler.Terminate()
      gCommands.remove_pending_command(handler)
      if err is None:
        wingapi.gApplication.SetStatusMessage(_("Login successful"))
      else:
        wingapi.gApplication.SetStatusMessage(_("Login failed"))    
        global gPassword
        gPassword = None
      return False

    else:
      # XXX This does not work -- CVS connects to parent process I/O somehow?!?
      if len(sent_pass) == 0 and ''.join(handler.stdout).find('Logging in') >= 0:
        handler.pipes.tochild.write(gPassword + '\n')
        sent_pass.append(1)
      gCommands.update_status()
      return True
    
  wingapi.gApplication.InstallTimeout(100, poll)

def __ssh_add_warning(protocols):
  """Check to see that ssh-agent is running to avoid hanging up on
  password prompts."""
  
  if protocols.has_key('ext') and not __check_ssh_agent():
    # XXX This reaches through the API but adding buttons and checks
    # XXX really shouldn't require that
    title = _("SSH Agent Not Found")
    msg = _("Could not find ssh-agent, or there are no valid identities "
            "loaded into it.  Please make sure ssh-agent is running "
            "before starting Wing and ssh-add has been executed before "
            "attempting CVS commands on an SSH secured CVS repository.\n\n"
            "If you are using CVS with pserver or have SSH configured "
            "to use authorized_keys or an unencrypted private key, you can "
            "disable this test and your CVS operations should succeed.")
    def check_toggle(chk):
      app.fSingletons.fFileAttribMgr[_kCheckSSHAgent] = not chk
    checks = [(_("Disable this test"), 0, check_toggle),]
    buttons = [dialogs.CButtonSpec(_("OK"), None)]
    dlg = messages.CMessageDialog(wingapi.gApplication.fSingletons, 
                                  title, msg, (),
                                  buttons, check_spec=checks)
    dlg.RunAsModal(wingapi.gApplication.fSingletons.fWinMgr.GetActiveWindow())
    return False
  else:
    return True

def __apply_cvs_op(filenames, op, cb, message=None):
  """Perform given cvs operation on the given files or directories"""

  # If it's not an SSH repository, we need to run cvs login the first time
  roots, protocols = __check_roots(filenames)  
  if protocols.has_key('pserver') and gPassword is None:
    def login(password):
      cvs_login(password)
      __apply_cvs_op(filenames, op, cb, message)
    # This is reaching through the API for now
    import command.commandmgr
    cmd = command.commandmgr.CreateCommand(login)
    wingapi.gApplication.ExecuteCommand(cmd)
    return
      
  # Check to see that ssh-agent is running to avoid hanging up on
  # password prompts.
  if not __ssh_add_warning(protocols):
    return

  # Synthesize directories and files to operate on and apply operation
  # using as few commands as possible
  filedirs = __get_filedirs(filenames, prune=op!='add')
  for dirname, files in filedirs.items():
    args = ['-z5']
    args.extend(op.split())
    if message is not None:
      message = __unicode_to_fs(message)
      args.extend(["-m", message])
    if op == 'update':
      args.extend(['-d', '-P'])
    args.extend(files)

    __run_async(op, dirname, cb, *args)

def __get_filedirs(filenames, prune=True):
  """Get dict of directories and files w/in the directory from
  the given list.  If prune is True, the list is collapsed to
  remove redundant entries (assuming recursive application of
  a CVS command to directories) and to combine into as small a 
  tree as possible where 'CVS' directories exist so as few
  commands as possible can be run."""
  
  def _dir_only(items):
    return len(items) == 1 and items[0] == '.'
  def _contains_dir(items):
    return '.' in items

  def make_full_path(path):
    if sys.platform == 'win32':
      if len(path[0]) == 2 and path[0][1] == ':' and path[0][0].isalpha():
        if len(path) == 1:
          return path[0] + os.sep
        else:
          return path[0] + os.sep + os.path.join(*path[1:])
      else:
        return ur'\\' + os.path.join(*path)
    else:
      return os.path.sep + os.path.join(*path)
  
  def _traverse(tree, path, action):
    for key in tree.keys():
      if tree[key] == 1:
        action(path, key)
      else:
        _traverse(tree[key], path + [key], action)
        
  def _prune1(tree, path):
    """Prune out all items below a directory we're acting on as a
    whole since they are redundant (CVS action is itself recursive)"""
    
    dirname = os.path.sep + os.path.join(*([''] + path))
    if os.path.isdir(os.path.join(dirname, 'CVS')) and tree.has_key('.'):
      tree.clear()
      tree['.'] = 1
      
    else:
      for key in tree.keys():
        if isinstance(tree[key], dict):
          _prune1(tree[key], path + [key])
    
  def _prune2(tree, path):
    """Combine all items below a directory in CVS into one big list
    of partial paths"""

    paths = {}
    def get_paths(path, filename):
      if filename == '.':
        paths[make_full_path(path)] = 1
      else:
        paths[make_full_path(path + [filename])] = 1
    _traverse(tree, [], get_paths)

    def find_common_root(path):
      roots, protocols = __check_roots([path])
      if len(roots) == 0:
        return os.path.split(path)
      root = roots.keys()[0]

      parts = path.split(os.path.sep)
      for i in range(len(parts)-1, 0, -1):
        dirname = make_full_path(parts[:i])
        partial = make_full_path(parts[i:])
        r, p = __check_roots([dirname])
        if len(r) == 0 or r.keys()[0] != root:
          parent = make_full_path(parts[:i+1])
          partial = parts[i+1:]
          if len(partial) == 0:
            partial = '.'
          else:
            partial = os.path.join(*partial)
          return parent, partial

      return os.path.split(path)
      
    file_tree = {}
    for path in paths.keys():
      parent, partial = find_common_root(path)
      insert_tree = file_tree
      for part in parent.split(os.path.sep):
        insert_tree = insert_tree.setdefault(part, {})
      insert_tree[partial] = 1

    return file_tree
  
  # Build tree of all files/dirs we're operating on.  Each node is
  # a dictionary with leaves set to the files (or '.' for directory).
  file_tree = {}
  for filename in filenames:
    if not wingapi.IsUrl(filename):
      parts = filename.split(os.sep)
      insert_tree = file_tree
      for part in parts[:-1]:
        insert_tree = insert_tree.setdefault(part, {})
      if os.path.isdir(filename):
        sub_tree = insert_tree.setdefault(parts[-1], {})
        sub_tree['.'] = 1
      else:
        insert_tree[parts[-1]] = 1

  # If requested, prune the tree to minimize the number of
  # CVS operations performed
  if prune:
    _prune1(file_tree, [])
    file_tree = _prune2(file_tree, [])
  
  # Build dictionary from working directory to files to operate
  # on within that directory
  retval = {}
  def add_item(path, filename):
    if filename == '.':
      filename = ''
    dirname = make_full_path(path)
    retval.setdefault(dirname, []).append(filename)
  _traverse(file_tree, [], add_item)
  
  return retval

class _CCommandStatus:
  """Manage multiple pending CVS commands for single status display"""
  
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
      wingapi.gApplication.SetStatusMessage("CVS %s %s" % (title, t))

gCommands = _CCommandStatus()

def __run_async(op, dirname, cb, *args):

  cmd = wingapi.gApplication.fSingletons.fFileAttribMgr[_kCVSCommand]
  print cmd, args, dirname
  handler = wingapi.gApplication.AsyncExecuteCommandLine(cmd, dirname, *args)
  gCommands.add_pending_command(handler, op, dirname)
  
  def poll():
    if handler.terminated:
      return False
    if handler.Iterate():
      title = _("CVS %s Result") % op.title()
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
                                       
def __log_completion(op, args, dirname, stdout, stderr, err, status):

  result = []
  result.append(_("Changing to: %s") % __fs_to_unicode(dirname))
  result.append(' ' .join([__fs_to_unicode(t) for t in (cmd,) + args]))
  result.append('  ' + __to_unicode(stdout))
  if err is not None:
    result.append('  ' + _("Error executing command: errno=%i") % err)
  if status != 0:
    result.append('  ' + _("Exit status=%i") % status)
  if len(stderr.strip()) > 0:
    result.append(_("Errors/Warnings (stderr):"))
    result.append('')
    result.append(__to_unicode(stderr))
  result = '\n'.join(result)
  print result
      
def __diff_completion(op, args, dirname, stdout, stderr, err, status):

  if err is not None: # or status not in (None, 0, 256):
    __message_completion(op, args, dirname, stdout, stderr, err, status)
    return
  
  if stdout.strip() == '' and stderr.strip() == '':
    title = _("No differences found")
    msg = _("The file(s) match the corresponding CVS revision(s).  The "
            "command was:\n\ncvs %s %s\n\nExecuted in: %s") % (op, ' '.join(args), dirname)
    wingapi.gApplication.ShowMessageDialog(title, msg)
    return
    
  title = 'CVS %s %%d' % op.title()
  
  app = wingapi.gApplication
  sticky = not app.fSingletons.fFileAttribMgr[_kTransientResultBuffers]
  editor = app.ScratchEditor(title, 'text/x-diff', sticky=sticky)
  doc = editor.GetDocument()
  txt = []
  if len(stderr.strip()) > 0:
    txt.append(_("Errors/Warnings (stderr):"))
    txt.append('')
    txt.append(__to_unicode(stderr))
    txt.append('=' * 60)
  txt.append(__to_unicode(stdout))
  doc.SetText('\n'.join(txt))
      
def __message_completion(op, args, dirname, stdout, stderr, err, status):

  title = _("CVS Results")
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
  elif op == 'commit' and stderr.lower().find('up-to-date check failed') >= 0:
    alert = True
    dialog = True
    xtra = _("CVS found concurrent changes -- do an update before committing")
  if dialog:
    dtitle = _("CVS Error")
    if err is not None:
      msg = _("CVS %s failed to execute.  errno=%i") % (op.title(), err)
    else:
      msg = _("CVS %s returned unexpected exit status=%i") % (op.title(), status)      
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

def __check_ssh_agent():
  """Check that an ssh-agent is present and has at least one valid looking
  identity loaded into it."""

  # There's no way to do this w/ putty/pageant and that's OK because
  # they don't hang up on prompting for passwords
  if sys.platform == 'win32':
    return True
  
  app = wingapi.gApplication
  if not app.fSingletons.fFileAttribMgr[_kCheckSSHAgent]:
    return True
  
  cmd = 'ssh-add'
  handler = app.AsyncExecuteCommandLine(cmd, os.getcwd(), '-l')
  end = time.time() + 1.0
  while not handler.Iterate() and time.time() < end:
    time.sleep(0.01)
  stdout, stderr, err, status = handler.Terminate()
  if err is None:
    out = stdout + stderr
    if len(out) > 0 and not out.find('no identities') >= 0 and not out.find('not open') >= 0:
      return True
    
  return False

def __check_roots(filenames, valid_protocols=['ext', 'pserver', '*']):
  """Get all CVSROOTs from CVS/Root files within given directories
  and enumeration of protocols found (pserver or ext)"""

  roots = {}
  protocols = {}

  for fn in filenames:
    if os.path.isdir(fn):
      dir = fn
    else:
      dir = os.path.dirname(fn)
    root_file = os.path.join(dir, 'CVS', 'Root')
    if not os.path.isfile(root_file):
      continue
    try:
      f = open(root_file)
      l = f.readline()
      parts = l.split(':')
      if len(parts) > 2:
        p = parts[1]
      else:
        p = '*'
      if p in valid_protocols:
        protocols[p] = 1
        roots[l] = 1
      f.close()
    except:
      pass

  return roots, protocols

def __read_entries_file(filename):
  """Read the CVS/Entries file corresponding w/ given file name and
  return (dir, version, date, flags). Returns all None's if not in
  Entries file."""
  
  efile = os.path.join(os.path.dirname(filename), 'CVS', 'Entries')
  if os.path.exists(efile):
    f = open(efile)
    lines = f.readlines()
    f.close()
    for line in lines:
      try:
        dir, file, version, date, flags, ignore = line.split('/')
        if file == os.path.basename(filename):
          return dir, version, date, flags
      except ValueError:
        pass

  return None, None, None, None

  
#########################################################################
# Options dialog -- this currently reaches through the API, although
# some of this support may be exposed in cleaned up form later

from guiutils import wgtk
from guiutils import formutils
from wingutils import datatype

_kCVSCommand = datatype.CValueDef(
  'cvs', 'cvs-command',
  _('Set this to the CVS command line executable.  In some '
    'cases, a full path is needed.'),
  'cvs', datatype.CLocation(), formbuilder.CFileSelectorGui()
)
_kDiffTypes = [
  (_("Default"), 'default'),
  (_("Context Diff"), 'context'),
  (_("Unified Diff"), 'unified'),
]
_kDiffTypeAttrib = datatype.CValueDef(
  'cvs', 'diff-type',
  _('The type of diff to produce:  Default form, with added context, or '
    'as unified diffs.'),
  'default',
  datatype.CValue(*[t[1] for t in _kDiffTypes]),
  formbuilder.CPopupChoiceGui(_kDiffTypes)
)
_kTransientResultBuffers = datatype.CValueDef(
  'cvs', 'transient-result-buffers', 
  _('Set this to show results of CVS operations in transient editors '
    'that auto-close when not visible.'),
  0, datatype.CBoolean(), formbuilder.CBooleanGui()
)
_kCheckSSHAgent = datatype.CValueDef(
  'cvs', 'check-ssh-agent', 
  _('Set this to check for ssh-agent with at least one loaded '
    'key before issuing commands.  This avoids hanging up the '
    'IDE at background password prompt if SSH is not configured '
    'to display a graphical prompt.'),
  1, datatype.CBoolean(), formbuilder.CBooleanGui()
)

for attrib in [_kCVSCommand, _kDiffTypeAttrib, _kTransientResultBuffers, _kCheckSSHAgent]:
  wingapi.gApplication.fSingletons.fFileAttribMgr.AddDefinition(attrib)
  
gOptionsDialog = None

class COptionsDialog(dialogs.CWidgetDialog):
  """CVS options dialog"""
  
  def __init__(self):

    singletons = wingapi.gApplication.fSingletons
    
    if 0:
      import singleton
      assert isinstance(singletons, singleton.CWingSingletons)
      
    self.fSingletons = singletons

    pages = self._GetFormPages()
    form = formutils.Form(pages=pages, visible=True, omit_buttons=False, 
                          scrollable=True, include_apply=True)
    self.fForm = form
    self.fPages = pages
    
    dialogs.CWidgetDialog.__init__(self, self.fSingletons.fWinMgr,
                                   'cvs-options', _("CVS Options"), 
                                   widget=form, button_spec=[],
                                   close_cb=self.__CB_Close, place_window=False)
    wgtk.connect_while_alive(form, 'accepted', lambda o: self.__CB_Okay(), self)
    wgtk.connect_while_alive(form, 'cancelled', lambda o: self.__CB_Close(), self)
    wgtk.connect_while_alive(form, 'applied', lambda o: self.__CB_Apply(), self)

    self.__ValuesToPages()
    form.map_all_pages()

    self.fWindow.PlaceWindow()
    
  def _destroy_impl(self):
    global gOptionsDialog
    gOptionsDialog = None
    
  def _GetFormPages(self): 
    """Create and return the form pages to use"""
    fields = [
      formutils.FieldDefn(_("CVS Executable"), _kCVSCommand,
                          formbuilder.CFileSelectorGui()),
      formutils.FieldDefn(_("Type of Diffs"), _kDiffTypeAttrib, 
                          formbuilder.CPopupChoiceGui(_kDiffTypes)),
      formutils.FieldDefn(_("Transient Result Buffers"), _kTransientResultBuffers, 
                          formbuilder.CBooleanGui()),
    ]
    if sys.platform != 'win32':
      fields.extend([
        formutils.FieldDefn(_("Check for SSH Agent"), _kCheckSSHAgent, 
                            formbuilder.CBooleanGui()),
      ])
    page = formutils.FormPage(fields, label = _("_CVS"), visible = True)
    return [page]

  def __ValuesToPages(self):
    
    for page in self.fPages:
      page.load_data(self.fSingletons.fFileAttribMgr)
    
  def _GetValuesFromPages(self):

    for page in self.fPages:
      for key, value in page.items():
        self.fSingletons.fFileAttribMgr[key] = value
    
  def __CB_Okay(self):
    
    self._GetValuesFromPages()
    self.Close()

    return True
      
  def __CB_Apply(self):

    self._GetValuesFromPages()

    return True

  def __CB_Close(self):
    
    self.Close()

    return True

  