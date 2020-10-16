"""This is an integration with the SVN revision control system.

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
import xml.sax
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
_ = gettext.translation('scripts_svn', fallback = 1).ugettext
_i18n_module = 'scripts_svn'

app = wingapi.gApplication

# This is a disabled example script
_ignore_scripts=1

_require_login = ('commit', 'update', 'blame', 'list', 'log')

#########################################################################  
# Commands
#########################################################################  

def svn_update(filenames=wingapi.kArgFilename):
  """Perform svn update on the given files or directories"""
  __apply_svn_op(filenames, 'update', cb=__message_completion)
  
def _svn_update_available(filenames=wingapi.kArgFilename):
  if filenames is None or len(filenames) == 0:
    return False
  for filename in filenames:
    if not wingapi.IsUrl(filename):
      version, date, kind, author, url, exists = __read_entries_file(filename)
      if version is not None or kind == 'dir':
        return True
  return False
svn_update.available = _svn_update_available
svn_update.label = _('SVN _Update')

svn_update.contexts = [wingapi.kContextEditor(), 
                       wingapi.kContextProject(),
                       wingapi.kContextNewMenu(_("S_VN"), 1)]

def svn_revert(filenames=wingapi.kArgFilename):
  """Perform svn revert on the given files or directories"""
  def doit():
    __apply_svn_op(filenames, 'revert', cb=__message_completion)
  title = _("Discard Changes in Files?")
  msg = _("Are you sure you want to discard your changes to all the "
          "selected files and revert to the current state on this "
          "branch in Subversion?")
  buttons = [
    dialogs.CButtonSpec(_("OK"), doit),
    dialogs.CButtonSpec(_("Cancel"), None),
  ]
  dlg = messages.CMessageDialog(wingapi.gApplication.fSingletons, title, msg,
                                (), buttons)
  dlg.RunAsModal(wingapi.gApplication.fSingletons.fWinMgr.GetActiveWindow())    
  
svn_revert.available = _svn_update_available
svn_revert.label = _('SVN _Revert')

svn_revert.contexts = [wingapi.kContextEditor(), 
                       wingapi.kContextProject(),
                       wingapi.kContextNewMenu(_("S_VN"), 1)]

def svn_diff(filenames=wingapi.kArgFilename):
  """Perform svn diff on the given files or directories."""
  app = wingapi.gApplication
  __apply_svn_op(filenames, 'diff', cb=__diff_completion)
   
svn_diff.available = _svn_update_available
svn_diff.label = _('SVN _Diff')
svn_diff.contexts = [wingapi.kContextEditor(), 
                     wingapi.kContextProject(),
                     wingapi.kContextNewMenu(_("S_VN"), 2)]

def svn_diff_recent(filenames=wingapi.kArgFilename):
  """Perform svn diff between the current checked out repository 
   revision of the file and the previous revision before that."""
  filename = filenames[0]
  version, date, kind, author, url, exists = __read_entries_file(filename)
  version = str(int(version) - 1)
  __apply_svn_op(filenames, 'diff -r%s' % version, 
                 cb=__diff_completion)
   
def _svn_diff_recent_available(filenames=wingapi.kArgFilename):
  if len(filenames) == 0:
    return False
  filename = filenames[0]
  version, date, kind, author, url, exists = __read_entries_file(filename)
  if version is None or kind == 'dir':
    return False
  return int(version) > 1

svn_diff_recent.available = _svn_diff_recent_available
svn_diff_recent.label = _('Show Last Re_vision Diffs')
svn_diff_recent.contexts = [wingapi.kContextNewMenu(_("S_VN"), 2)]

def svn_log(filenames=wingapi.kArgFilename):
  """Perform svn log on the given files or directories"""
  __apply_svn_op(filenames, 'log', cb=__message_completion)
   
svn_log.available = _svn_update_available
svn_log.label = _('SVN _Log')
svn_log.contexts = [wingapi.kContextEditor(), 
                    wingapi.kContextProject(),
                    wingapi.kContextNewMenu(_("S_VN"), 3)]

def svn_status(filenames=wingapi.kArgFilename):
  """Perform svn status on the given files or directories"""
  __apply_svn_op(filenames, 'status', cb=__message_completion)
   
def _svn_status_available(filenames=wingapi.kArgFilename):
  if filenames is None or len(filenames) == 0:
    return False
  for filename in filenames:
    if not wingapi.IsUrl(filename):
      version, date, kind, author, url, exists = __read_entries_file(filename)
      if kind is not None:
        return True
  return False
  
svn_status.available = _svn_status_available
svn_status.label = _('SVN _Status')
svn_status.contexts = svn_log.contexts

def svn_blame(filenames=wingapi.kArgFilename):
  """Perform svn blame/praise on the given files or directories."""
  app = wingapi.gApplication
  __apply_svn_op(filenames, 'blame', cb=__blame_completion)
   
svn_blame.available = _svn_update_available
svn_blame.label = _('SVN Blame_/Praise')
svn_blame.contexts = [wingapi.kContextEditor(), 
                     wingapi.kContextProject(),
                     wingapi.kContextNewMenu(_("S_VN"), 3)]

def svn_list(filenames=wingapi.kArgFilename):
  """Perform svn list on the given files or directories."""
  app = wingapi.gApplication
  __apply_svn_op(filenames, 'list', cb=__message_completion)
   
def _svn_list_available(filenames=wingapi.kArgFilename):
  if filenames is None or len(filenames) == 0:
    return False
  for filename in filenames:
    if not wingapi.IsUrl(filename):
      version, date, kind, author, url, exists = __read_entries_file(filename)
      if kind == 'dir':
        return True
  return False

svn_list.available = _svn_list_available
svn_list.label = _('SVN Lis_t')
svn_list.contexts = [wingapi.kContextEditor(), 
                     wingapi.kContextProject(),
                     wingapi.kContextNewMenu(_("S_VN"), 3)]

def svn_commit(message):
  """Perform svn commit on the given files or directories"""
  __apply_svn_op(wingapi.gApplication.GetCurrentFiles(), 'commit',
                 cb=__message_completion, message=message)
   
svn_commit.available = _svn_status_available
svn_commit.label = _('SVN _Commit')
svn_commit.arginfo = {
  'message': _AI(_("Log message to attach to this revision"), datatype.CType(''), 
                 formbuilder.CLargeTextGui(allow_newlines=True)),
}

def svn_commit_prompt():
  """Perform svn commit on the given files or directories
  after prompting for log message"""
  filenames = wingapi.gApplication.GetCurrentFiles()
  roots, protocols = __check_roots(filenames)  
  if not __ssh_add_warning(protocols):
    return
  else:
    wingapi.gApplication.ExecuteCommand(svn_commit)
   
svn_commit_prompt.available = _svn_status_available
svn_commit_prompt.label = _('SVN _Commit')
svn_commit_prompt.contexts = svn_update.contexts

def svn_resolved(filenames=wingapi.kArgFilename):
  """Perform svn resolved on the given files or directories"""
  __apply_svn_op(filenames, 'resolved', cb=__message_completion)

svn_resolved.available = _svn_update_available
svn_resolved.label = _('SVN Res_olved')
svn_resolved.contexts = svn_update.contexts

def svn_add(filenames=wingapi.kArgFilename):
  """Perform svn add on the given files or directories"""
  __apply_svn_op(filenames, 'add', cb=__message_completion)
   
def _svn_add_available(filenames=wingapi.kArgFilename):
  if filenames is None or len(filenames) == 0:
    return False
  for filename in filenames:
    if not wingapi.IsUrl(filename):
      if not os.path.exists(filename):
        return False
      version, date, kind, author, url, exists = __read_entries_file(filename)
      # Item not in svn file but svn file exists
      if kind is None and exists:
        return True
      # Directories alreasy in svn file always enable 'add' as easy way to add new sub-items
      elif kind == 'dir':
        return True      
      # Directory not in svn file: Enable 'add' if parent is in svn
      elif os.path.isdir(filename):
        version, date, kind, author, url, exists = __read_entries_file(os.path.dirname(filename))
        if exists:
          return True
  return False
svn_add.available = _svn_add_available
svn_add.label = _('SVN _Add')
svn_add.contexts = [wingapi.kContextEditor(), 
                    wingapi.kContextProject(),
                    wingapi.kContextNewMenu(_("S_VN"))]

def svn_cancel():
  """Cancel pending SVN commands that are running in the background 
  but have not yet completed"""
  i = len(gCommands.all_pending_commands())
  for handler in gCommands.all_pending_commands():
    handler.Terminate(kill=True)
    gCommands.remove_pending_command(handler)
  wingapi.gApplication.SetStatusMessage("Canceled %i SVN Request(s)" % i)
def _svn_cancel_available():
  return len(gCommands.all_pending_commands()) > 0
svn_cancel.available = _svn_cancel_available
svn_cancel.label = _("Cancel Active Re_quests")
svn_cancel.contexts = [wingapi.kContextNewMenu(_("S_VN"), 4)]

def svn_configure():
  """Configure SVN options"""
  global gOptionsDialog
  if gOptionsDialog is not None:
    gOptionsDialog.Show()
    return
  gOptionsDialog = COptionsDialog()
  gOptionsDialog.Run()

svn_configure.label = _("_Options...")
svn_configure.contexts = [wingapi.kContextNewMenu(_("S_VN"), 5)]

#########################################################################  
# Utilities
#########################################################################  

# Authentication cache (map from hostname to username/password pair)
gAuthCache = {}

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

def __ssh_add_warning(protocols):
  """Check to see that ssh-agent is running to avoid hanging up on
  password prompts."""
  
  ssh = False
  for p in protocols:
    if p.find('ssh') >= 0:
      ssh = True
      break

  if ssh and not __check_ssh_agent():
    # XXX This reaches through the API but adding buttons and checks
    # XXX really shouldn't require that
    title = _("SSH Agent Not Found")
    msg = _("Could not find ssh-agent, or there are no valid identities "
            "loaded into it.  Please make sure ssh-agent is running "
            "before starting Wing and ssh-add has been executed before "
            "attempting SVN commands on an SSH secured SVN repository.\n\n"
            "If you are using SVN with pserver or have SSH configured "
            "to use authorized_keys or an unencrypted private key, you can "
            "disable this test and your SVN operations should succeed.")
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

def __apply_svn_op(filenames, op, cb, message=None):
  """Perform given svn operation on the given files or directories"""

  # For non-file/non-ssh access, we may need to login the first time
  # (but only if user has set option to do this; usually the svn or
  # ssh-provided auth cache is used instead)
  req_login = app.fSingletons.fFileAttribMgr[_kAuthMode] == 'manual'
  # XXX Assume we only need to collect one login for now -- should
  # XXX instead prompt for each host and also use correct host
  # XXX below rather than assuming all is on same host
  hosts, protocols = __check_roots(filenames)  
  host = hosts.keys()[0]
  req_login = req_login and (not hosts[host].find('ssh') >= 0 and not hosts[host].find('file:///') == 0)
  if req_login and op in _require_login:
    if not gAuthCache.has_key(host):
      def login(username, password):
        gAuthCache[host] = (username, password)
        __apply_svn_op(filenames, op, cb, message)
      # This is reaching through the API for now
      import command.commandmgr
      cmd = command.commandmgr.CreateCommand(login)
      cmd.label = _("Login for %s:") % host
      wingapi.gApplication.ExecuteCommand(cmd)
      return
      
  # Check to see that ssh-agent is running to avoid hanging up on
  # password prompts.
  if op in _require_login and not __ssh_add_warning(protocols):
    return

  # Synthesize directories and files to operate on and apply operation
  # using as few commands as possible
  # XXX Should change this to also extract host so correct login info
  # XXX can be used
  filedirs = __get_filedirs(filenames, prune=op!='add')
  for dirname, files in filedirs.items():
    args = []
    args.extend(op.split())
    if op == 'status':
      args.append('-v')
    if req_login and op in _require_login:
      if not gAuthCache.has_key(host):
        return
      args.append('--username')
      args.append(gAuthCache[host][0])
      args.append('--password')
      args.append(gAuthCache[host][1])
      args.append('--no-auth-cache')
    if op in _require_login + ('diff',):
      args.append('--non-interactive')
    if message is not None:
      message = __unicode_to_fs(message)
      args.extend(["-m", message])
    args.extend(files)

    __run_async(op, dirname, cb, *args)

def __get_filedirs(filenames, prune=True):
  """Get dict of directories and files w/in the directory from
  the given list.  If prune is True, the list is collapsed to
  remove redundant entries (assuming recursive application of
  a SVN command to directories) and to combine into as small a 
  tree as possible where 'SVN' directories exist so as few
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
    whole since they are redundant (SVN action is itself recursive)"""
    
    dirname = os.path.sep + os.path.join(*([''] + path))
    if os.path.isdir(os.path.join(dirname, 'SVN')) and tree.has_key('.'):
      tree.clear()
      tree['.'] = 1
      
    else:
      for key in tree.keys():
        if isinstance(tree[key], dict):
          _prune1(tree[key], path + [key])
    
  def _prune2(tree, path):
    """Combine all items below a directory in SVN into one big list
    of partial paths"""

    paths = {}
    def get_paths(path, filename):
      if filename == '.':
        paths[make_full_path(path)] = 1
      else:
        paths[make_full_path(path + [filename])] = 1
    _traverse(tree, [], get_paths)

    def find_common_root(path):
      hosts, protocols = __check_roots([path])
      if len(hosts) == 0:
        return os.path.split(path)
      host = hosts.keys()[0]

      parts = path.split(os.path.sep)
      for i in range(len(parts)-1, 0, -1):
        dirname = make_full_path(parts[:i])
        partial = make_full_path(parts[i:])
        h, p = __check_roots([dirname])
        if len(h) == 0 or h.keys()[0] != host:
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
  # SVN operations performed
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
  """Manage multiple pending SVN commands for single status display"""
  
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
      wingapi.gApplication.SetStatusMessage("SVN %s %s" % (title, t))

gCommands = _CCommandStatus()

def __run_async(op, dirname, cb, *args):

  cmd = wingapi.gApplication.fSingletons.fFileAttribMgr[_kSubversionCommand]
  print cmd, args, dirname
  handler = wingapi.gApplication.AsyncExecuteCommandLine(cmd, dirname, *args)
  gCommands.add_pending_command(handler, op, dirname)
  
  def poll():
    if handler.Iterate():
      title = _("SVN %s Result") % op.title()
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
                                       
def __diff_completion(op, args, dirname, stdout, stderr, err, status):

  if err is not None: # or status not in (None, 0, 256):
    __message_completion(op, args, dirname, stdout, stderr, err, status)
    return
  
  if stdout.strip() == '' and stderr.strip() == '':
    title = _("No differences found")
    msg = _("The file(s) match the corresponding SVN revision(s).  The "
            "command was:\n\nsvn %s\n\nExecuted in: %s") % (' '.join(args), dirname)
    wingapi.gApplication.ShowMessageDialog(title, msg)
    return
    
  title = 'SVN %s %%d' % op.title()
  
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
      
def __blame_completion(op, args, dirname, stdout, stderr, err, status):

  if err is not None: # or status not in (None, 0, 256):
    __message_completion(op, args, dirname, stdout, stderr, err, status)
    return
  
  title = 'SVN %s %%d' % op.title()
  
  app = wingapi.gApplication
  sticky = not app.fSingletons.fFileAttribMgr[_kTransientResultBuffers]
  editor = app.ScratchEditor(title, 'text/plain', sticky=sticky)
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

  title = _("SVN Results")
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
    xtra = _("SVN found concurrent changes -- do an update before committing")
  if dialog:
    dtitle = _("SVN Error")
    if err is not None:
      msg = _("SVN %s failed to execute.  errno=%i") % (op.title(), err)
    else:
      msg = _("SVN %s returned unexpected exit status=%i") % (op.title(), status)      
    if xtra is not None:
      msg += '\n' + xtra
    wingapi.gApplication.ShowMessageDialog(dtitle, msg)
    
  cmd = wingapi.gApplication.fSingletons.fFileAttribMgr[_kSubversionCommand]
  result = []
  result.append('*' * 60)
  result.append(_("Executing: %s") % (' ' .join([__fs_to_unicode(i) for i in (cmd,) + args])))
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

def __find_svn_dir(dirname):
  """ Return the pathname for the svn directory or None if none exists. """
  
  for name in '.svn', '_svn':
    svn_dir = os.path.join(dirname, name)
    if os.path.isdir(svn_dir):
      return svn_dir

  return None

def __check_roots(filenames):
  """Get all the hosts and protocols used by the .svn/entries files'
  entry w/ name="" corresponding to the given filenames"""

  hosts = {}
  protocols = {}

  for fn in filenames:
    version, date, kind, author, url, exists = __read_entries_file(fn, '')
    if not exists:
      continue

    try:
      import urllib
      t, o = urllib.splittype(url)
      hostname, path = urllib.splithost(o)
      protocols[t] = 1
      hosts[hostname] = t      
    except:
      pass

  return hosts, protocols

class __CSVNEntriesHandler(xml.sax.ContentHandler):
  def __init__(self, filename):
    self.__filename = filename
    self._attrs = None
    
  def startElement(self, name, attrs):
    if name == 'entry' and attrs.get('name') == self.__filename:
      self._attrs = attrs

def __read_entries_file(filename, expected_name=None):
  """Read the .svn/entries file corresponding w/ given file name and return
  (version, date, kind, author, url, exists) where exists is true if the
  .svn/entries file exists and the other values are None if not in Entries file."""

  if expected_name is None:
    expected_name = os.path.basename(filename)
    
  if os.path.isdir(filename):
    sdir = filename
    expected_name = ''
  else:
    sdir = os.path.dirname(filename)
  svn_dir = __find_svn_dir(sdir)
  if svn_dir is None:
    return None, None, None, None, None, False
  efile = os.path.join(svn_dir, 'entries')
  efile_exists = os.path.exists(efile)
  if efile_exists:
    
    # Determine type of entries file
    f = open(efile)
    lines = f.readlines()
    f.close()
    if len(lines) == 0:
      return None, None, None, None, None, efile_exists

    # Warn if unexpected Subversion version
    if not lines[0].lower().startswith('<?xml') and not lines[0].startswith('8') and \
       not lines[0].startswith('9'):
      print "WARNING: Unsupported Subversion version; some functions may fail"
      print "First line of entries file:", lines[0]
      
    # SVN client <= 1.3
    if lines[0].lower().startswith('<?xml'):
      h = __CSVNEntriesHandler(expected_name)
      p = xml.sax.parse(efile, h)
      if h._attrs is not None:
        return (h._attrs.get('committed-rev'),
                h._attrs.get('committed-date'),
                h._attrs.get('kind'),
                h._attrs.get('last-author'),
                h._attrs.get('url'),
                efile_exists)

    # SVN client >= 1.4 directory info is read from first part of entries file
    elif expected_name == '':
      
      # SVN client >= 1.5
      if lines[0].startswith('9'):
        value_lines = {
          'committed-rev': 3,
          'committed-date': 9,
          'kind': 2,
          'last-author': 11,
          'url': 4,
        }      
        
      # SVN client 1.4.x
      else:
        value_lines = {
          'committed-rev': 10,
          'committed-date': 9,
          'kind': 2,
          'last-author': 11,
          'url': 4,
        }
  
      if len(lines) <= max(*value_lines.values()):
        return None, None, None, None, None, efile_exists

      fields = ('committed-rev', 'committed-date', 'kind', 'last-author',  'url')
      retval = []
      for item in [lines[value_lines[r]].strip() for r in fields]:
        if len(item) == 0:
          retval.append(None)
        else:
          retval.append(item)      
      retval.append(efile_exists)
      return retval
    
    # SVN client >= 1.4 file info is read from specific section of entries file
    else:
      # SVN client >= 1.5
      if lines[0].startswith('9'):
        value_lines = {
          'committed-rev': 9,
          'committed-date': 6,
          'kind': 1,
          'last-author': 10,
        }
      
      # SVN client 1.4.x
      else:
        value_lines = {
          'committed-rev': 9,
          'committed-date': 6,
          'kind': 1,
          'last-author': 10,
        }

      # Find the file section
      next_is_filename = False
      found_filename = False
      file_lines = []
      for line in lines:
        if found_filename:
          if line.startswith('\f'):
            break
          file_lines.append(line)
        elif next_is_filename:
          next_is_filename = False
          if line.strip() == expected_name:
            found_filename = True
            file_lines.append(line)
        elif line.startswith('\f'):
          next_is_filename = True
          
      # File section not found or malformed so it's not in revision control
      if len(file_lines) <= max(*value_lines.values()):
        return None, None, None, None, None, efile_exists
      
      # Read values out of the file section
      fields = ('committed-rev', 'committed-date', 'kind', 'last-author',)
      retval = []
      
      for item in [file_lines[value_lines[r]].strip() for r in fields]:
        if len(item) == 0:
          retval.append(None)
        else:
          retval.append(item)      
      retval.append(None)
      retval.append(efile_exists)
      return retval

  return None, None, None, None, None, efile_exists

  
#########################################################################
# Options dialog -- this currently reaches through the API, although
# some of this support may be exposed in cleaned up form later

from guiutils import wgtk
from guiutils import formutils
from wingutils import datatype

_kSubversionCommand = datatype.CValueDef(
  'svn', 'svn-command',
  _('Set this to the subversion command line executable.  In some '
    'cases, a full path is needed.'),
  'svn', datatype.CLocation(), formbuilder.CFileSelectorGui()
)
_kTransientResultBuffers = datatype.CValueDef(
  'svn', 'transient-result-buffers', 
  _('Set this to show results of SVN operations in transient editors '
    'that auto-close when not visible.'),
  0, datatype.CBoolean(), formbuilder.CBooleanGui()
)
_kCheckSSHAgent = datatype.CValueDef(
  'svn', 'check-ssh-agent', 
  _('Set this to check for ssh-agent with at least one loaded '
    'key before issuing commands when working with a repository '
    'that is accessed via an ssh tunnel.  This avoids hanging up the '
    'IDE at background password prompt if SSH is not configured '
    'to display a graphical prompt.'),
  1, datatype.CBoolean(), formbuilder.CBooleanGui()
)
_kAuthModeTypes = [
  (_("Use SVN or SSH cache"), 'default'),
  (_("Manual (from Wing)"), 'manual'),
]
_kAuthMode = datatype.CValueDef(
  'svn', 'auth-mode',
  _('Set this to manual to ask for user name and password for each repository '
    'the first time it is used.  This information is cached for the '
    'length of the session and sent to svn with the --username and '
    '--password arguments, but is not stored on disk.  In most cases '
    'using Subversion\'s builtin authentication cache (or ssh-agent '
    'or Pageant when working through an ssh tunnel) is preferable.'),
  'default',
  datatype.CValue(*[t[1] for t in _kAuthModeTypes]),
  formbuilder.CPopupChoiceGui(_kAuthModeTypes)
)

for attrib in [_kSubversionCommand, _kTransientResultBuffers, _kCheckSSHAgent, _kAuthMode]:
  wingapi.gApplication.fSingletons.fFileAttribMgr.AddDefinition(attrib)
  
gOptionsDialog = None

class COptionsDialog(dialogs.CWidgetDialog):
  """SVN options dialog"""
  
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
                                   'svn-options', _("SVN Options"), 
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
      formutils.FieldDefn(_("SVN Executable"), _kSubversionCommand,
                          formbuilder.CFileSelectorGui()),
      formutils.FieldDefn(_("Transient Result Buffers"), _kTransientResultBuffers, 
                          formbuilder.CBooleanGui()),
    ]
    if sys.platform != 'win32':
      fields.extend([
        formutils.FieldDefn(_("Check for SSH Agent"), _kCheckSSHAgent, 
                            formbuilder.CBooleanGui()),
      ])
    fields.append(formutils.FieldDefn(_("Authentication"), _kAuthMode))

    page = formutils.FormPage(fields, label = _("S_VN"), visible = True)
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

  