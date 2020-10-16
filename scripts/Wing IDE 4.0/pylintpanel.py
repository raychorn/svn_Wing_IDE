"""
PyLint integration for Wing IDE.

Copyright (c) 2006-2007 Markus Meyer <meyer@mesw.de>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

----------------------------------------------------------------------------
Change Log
----------------------------------------------------------------------------

Version 1.0 (2006-10-12)

* First release

Version 1.1 (2007-03-19)

* Fix compatibility issues with newer PyLint versions
* Fix error message when PyLint returns no errors

Version 1.2 (2008-06-05)  Modifications by Wingware:

* Pass configured environment to the pylint sub-process
  (includes also PYTHONPATH if it's set in project)
* Use presence of a settings file to enable/disable for easier upgrades
* Removed obsolete example args
* Renamed "preferences" to "configure" in context menu to avoid confusion
* Renamed command execute_pylint to pylint_execute and pylint_preferences
  to pylint_configure
* Changed execution of pylint to be asyncronous

Version 1.3 (2008-09-30)  Modifications by Wingware:

* Added ability to process whole packages, if current file is in
  a package

Version 1.4 (2010-06-03)  Modifications by Jan Nabbefeld:

* Added ability to use per project pylintpanel.cfg (copy the file from
  your user settings directory into the same directory as your project file)

Version 1.5 (2011-09-07)  Modifications by Ronan Le Gallic and Wingware:

* Support for pylint 0.24+ column number output (Le Gallic)
* Avoid reporting empty output in pylint 0.24+ as an error (Le Gallic)
* Fix failure to set parseable output flag (Wingware)
* Don't assume scope names are in all pylint messages (Wingware)
* Better handle multiple pylint views (Wingware)

"""

import os
import wingapi
import time

PYLINTPANEL_VERSION = "1.5"

import re
_AI = wingapi.CArgInfo

# Scripts can be internationalized with gettext.  Strings to be translated
# are sent to _() as in the code below.
import gettext
_ = gettext.translation('scripts_pylintpanel', fallback = 1).ugettext

# This special attribute is used so that the script manager can translate
# also docstrings for the commands found here
_i18n_module = 'scripts_pylintpanel'

######################################################################
# Utilities

gMessageCategories = [
  ("errors", _("Errors"), _("Errors that must be fixed")),
  ("warnings", _("Warnings"), _("Warnings that could indicate problems")),
  ("information", _("Info"), _("General informative messages"))
]

gTheView = None # Will be set later

######################################################################
# Configuration file support

class PylintConfig:
  def __init__(self):
    pass
  
  def get(self, name, default=""):
    """
    Get configuration option from configuration file
    """
    try:
      lines = file(self._get_config_file_name(), "rt").readlines()
    except IOError:
      return default
    for line in lines:
      words = line.split("=", 1)
      if len(words) == 2:
        key = words[0].strip()
        value = words[1].strip()
        if key == name:
          return value
    return default
  
  def edit(self):
    """
    Edit and possibly create configuration file. Currently, this will just
    open the configuration file inside WingIDE.
    """
    try:
      # Check if config file can be opened
      cfgfile = file(self._get_config_file_name(), "rt")
    except IOError:
      # The config file does not yet exist, create it
      cfgfile = file(self._get_config_file_name(), "wt")
      cfgfile.writelines([
        '#\n',
        '# PyLint Panel Configuration\n',
        '#\n',
        '\n',
        '# Full path to PyLint executable\n',
        'command = \n',
        '#command = /usr/bin/pylint\n',
        '#command = C:\Python24\Scripts\pylint.bat\n',
        '\n',
        '# Additional args to give to PyLint (may be blank)\n',
        'args = \n',
        '\n',
        '# Timeout for execution of pylint command\n',
        'timeout = 30\n',
        '\n',
        '# Save files before running PyLint (0=no, 1=current file only, 2=save all files)\n',
        'autosave = 1\n'
        ])
    cfgfile.close()
    
    wingapi.gApplication.OpenEditor(self._get_config_file_name())

  def _get_config_file_name(self):
    """
    Get full name and path of config file
    """
    # Check for pylintpanel.cfg file in current project directory 
    # before using the one in the users settings directory
    app = wingapi.gApplication
    proj = app.GetProject()
    proj_dir = os.path.dirname(proj.GetFilename())
    cfg = os.path.join(proj_dir, "pylintpanel.cfg")
    if os.path.exists(cfg):
        return cfg
      
    dir = wingapi.gApplication.GetUserSettingsDir()
    return os.path.join(dir, "pylintpanel.cfg")

gTheConfig = PylintConfig()

kResultParseExpr = re.compile("(?P<type>[^:]+):[ ]*(?P<line>[0-9,]+):[ ]*(?P<descr>.*)")
kParseableResultParseExpr = re.compile("(?P<path>[^:]+):(?P<line>[0-9,]+):[ ]*\[(?P<type>.*)\][ ]*(?P<descr>.*)")

######################################################################
# Commands

def pylint_configure():
  """Show the pylint configuration file so it can be edited"""
  gTheConfig.edit()

def pylint_execute():
  """Execute pylint for the current editor"""
  filenames = _get_selected_python_files()
  _pylint_execute(filenames)  
  
def _IsAvailable_pylint_execute():
  python_files = _get_selected_python_files()
  return len(python_files) > 0

pylint_execute.available = _IsAvailable_pylint_execute

def pylint_package_execute():
  """Execute pylint on all files in the package to which the
  file in the current editor belongs"""
  
  packages = _get_selected_packages()
  _pylint_execute(packages)

def _IsAvailable_pylint_package_execute():
  packages = _get_selected_packages()
  return len(packages) > 0

pylint_package_execute.available = _IsAvailable_pylint_package_execute

######################################################################
# XXX This is advanced scripting that accesses Wing IDE internals, which
# XXX are subject to change from version to version without notice.

from wingutils import location
from guiutils import wgtk
from guiutils import dockview
from guiutils import wingview
from guiutils import winmgr

from command import commandmgr
import guimgr.menus

def pylint_show_docs():
  """Show the Wing IDE documentation section for the PyLint integration"""
  wingapi.gApplication.ExecuteCommand('show-document', section='edit/pylint')

def _get_selected_packages():
  app = wingapi.gApplication
  filenames = app.GetCurrentFiles()
  packages = []
  for filename in filenames:
    dirname = os.path.dirname(filename)
    if os.path.exists(os.path.join(dirname, '__init__.py')):
      if not dirname in packages:
        packages.append(dirname)
  return packages

def _get_selected_python_files():
  app = wingapi.gApplication
  filenames = app.GetCurrentFiles()
  if not filenames:
    return []
  python_files = []
  for filename in filenames:
    mimetype = _GetMimeType(filename)
    if mimetype == 'text/x-python':
      python_files.append(filename)
  return python_files
  
kPyLintVersion = None
def _init_pylint_version():

  if kPyLintVersion is not None:
    return kPyLintVersion
  
  app = wingapi.gApplication
  
  pylint_command = gTheConfig.get("command", None)
  if pylint_command is None:
    return None
  
  # Execute PyLint asyncronously
  cmd = pylint_command
  args = ('--version',)
  start_time = time.time()
  timeout = 10
  print 'getting pylint version'
  import config
  handler = app.AsyncExecuteCommandLineE(cmd, os.getcwd(), config.gStartupEnv, *args)
  
  def poll():
    if handler.Iterate():
      stdout, stderr, err, status = handler.Terminate()      
      if err:
        print 'err=', err
        print "stderr:\n", stderr.rstrip()
      else:
        if len(stderr.strip()) > 0:
          print "stderr:\n", stderr.rstrip()
        print "stdout:\n", stdout.rstrip()
        for line in stdout.splitlines():
          if line.startswith('pylint'):
            parts = line.split()
            if len(parts) >= 2:
              version = parts[1].strip()
              if version.endswith(','):
                version = version[:-1]
              global kPyLintVersion
              kPyLintVersion = version
              print 'set pylint version=', version
      return False
    elif time.time() > start_time + timeout:
      print 'timeout'
      return False
    else:
      return True
    
  wingapi.gApplication.InstallTimeout(100, poll)
 
def _pylint_execute(filenames):
  if gTheView is None:
    # Panel is not visible
    return
  
  view = gTheView
  app = wingapi.gApplication
  
  # Parse config
  pylint_command = gTheConfig.get("command", None)
  pylint_args = gTheConfig.get("args", "")
  pylint_timeout = gTheConfig.get("timeout", "10000")
  pylint_autosave = gTheConfig.get("autosave", "1")
  
  # Look for project-specific .pylintrc file
  if '--rcfile=' not in pylint_args:
    proj = app.GetProject()
    proj_dir = os.path.dirname(proj.GetFilename())
    pylintrc = os.path.join(proj_dir, '.pylintrc')
    if os.path.isfile(pylintrc):
      pylint_args = '--rcfile="%s" %s' % (pylintrc, pylint_args)

  if pylint_command is None:
    app.ShowMessageDialog(_('Error'), _('PyLint panel configuration file not found. '
                          'Choose "Configure" from the context menu to edit '
                          'the configuration file.  You will need to install pylint '
                          'separately.'))
    return
  
  try:
    timeout = int(pylint_timeout)
    autosave = int(pylint_autosave)
  except ValueError:
    app.ShowMessageDialog(_("Error"), _("Invalid values specified in configuration file"))
    return

  # Guess at run directory
  rundir = os.path.dirname(filenames[0])
  if len(filenames) == 1:
    if os.path.isdir(filenames[0]):
      base_msg = _("Updating for package %s") % os.path.basename(filenames[0])
    else:
      base_msg = _("Updating for %s") % os.path.basename(filenames[0])
  else:
    base_msg = _("Updating for %i items") % len(filenames)

  # Save active document before executing PyLint
  if autosave == 1 and app.CommandAvailable("save"):
    app.ExecuteCommand("save")
  elif autosave == 2 and app.CommandAvailable("save-all"):
    app.ExecuteCommand("save-all")
  
  # Completion routine that updates the tree when pylint is finished running
  def _update_tree(result):
    resultLines = result.split('\n')

    tree_contents = [ [], [], [], [] ]

    for line in resultLines:

      parts = line.split(':')
      # Form output with --output-format=parseable (used w/ >1 file or package name)
      if len(parts) >= 3 and parts[2].strip().startswith('['):
        matchobj = kParseableResultParseExpr.match(line)
        if matchobj is not None:

          msg_type  = matchobj.group('type').strip()
          msg_line, msg_col = (matchobj.group('line') + ',0').split(',')[0:2]
          msg_descr = matchobj.group('descr').strip()

          if ',' in msg_type:
            type_parts = msg_type.split(',', 1)
            msg_type = type_parts[0].strip()
            msg_descr = type_parts[1].strip() + ': ' + msg_descr

          if msg_type[0] == 'F' or msg_type[0] == 'E':
            msg_index = 0
          elif msg_type[0] == 'W':
            msg_index = 1
          else:
            msg_index = 2
          fullpath = os.path.join(rundir, matchobj.group('path'))
          tree_contents[msg_index].append(
            ((os.path.basename(fullpath) + ':' + msg_line,
              msg_col,
              msg_type + ": " + msg_descr,
              fullpath,
              msg_line),))
          
      # Default output format (only used w/ one file in filenames list)
      else:
        matchobj = kResultParseExpr.match(line)
        if matchobj is not None:

          msg_type = matchobj.group('type').strip()
          msg_line, msg_col = (matchobj.group('line') + ',0').split(',')[0:2]
          msg_descr = matchobj.group('descr').strip()

          if msg_type[0] == 'F' or msg_type[0] == 'E':
            msg_index = 0
          elif msg_type[0] == 'W':
            msg_index = 1
          else:
            msg_index = 2
          tree_contents[msg_index].append(
            ((msg_line,
              msg_col,
              msg_type + ": " + msg_descr,
              filenames[0],
              msg_line),))

    view.set_tree_contents(tree_contents)

  # Show pending execution message in tree column title
  view._ShowStatusMessage(base_msg)
    
  from wingutils import spawn
  import config
   
  # Execute PyLint asyncronously
  cmd = pylint_command
  if kPyLintVersion is not None and kPyLintVersion > '0.15':
    args = []
  else:
    args = ['--reports=n', '--include-ids=yes']
  # Column info (and possibly other things) is not available w/ parseable 
  # output so only use it where we need to get the file name b/c we're
  # scanning multiple files or a package directory
  if len(filenames) > 1:
    args.append('--output-format=parseable')
  elif os.path.isdir(filenames[0]):
    args.append('--output-format=parseable')
  args.extend(spawn.ParseCmdArgs(pylint_args, ' '))
  for filename in filenames:
    args.append(filename.encode(config.kFileSystemEncoding))
  args = tuple(args)
  env = app.GetProject().GetEnvironment(filenames[0], set_pypath=True)
  start_time = time.time()
  print '-' * 60
  print 'pylint exec in directory', rundir
  print 'env=', env
  print cmd, ' '.join(args)
  handler = app.AsyncExecuteCommandLineE(cmd, rundir, env, *args)
  last_dot = [int(start_time)]
  dots = []
  
  def poll():
    if handler.Iterate():
      view._ShowStatusMessage('')
      stdout, stderr, err, status = handler.Terminate()
      if err or (not stdout and kPyLintVersion < '0.24'):
        app.ShowMessageDialog(_("PyLint Failed"), _("Error executing PyLint:  Command failed with error=%s, status=%s; stderr:\n%s") % (err, status, stderr))
      else:
        if len(stderr.strip()) > 0:
          print "pylint stderr:\n", stderr.rstrip()
        print "pylint stdout:\n", stdout.rstrip()
        _update_tree(stdout)
      print '-' * 60
      return False
    elif time.time() > start_time + timeout:
      view._ShowStatusMessage('')
      stdout, stderr, err, status = handler.Terminate()      
      app.ShowMessageDialog(_("PyLint Timed Out"), _("PyLint timed out:  Command did not complete within timeout of %i seconds.  Right click on the PyLint tool to configure this value.  Output from PyLint:\n\n%s") % (timeout, stderr + stdout))
      print '-' * 60
      return False
    else:
      if int(time.time()) > last_dot[0]:
        dots.append('.')
        if len(dots) > 3:
          while dots:
            dots.pop()
        view._ShowStatusMessage(base_msg + ''.join(dots))
        last_dot[0] = int(time.time())
      return True
    
  wingapi.gApplication.InstallTimeout(100, poll)

def _GetMimeType(filename):
  loc = location.CreateFromName(filename)
  return wingapi.gApplication.fSingletons.fFileAttribMgr.GetProbableMimeType(loc)

# Note that panel IDs must be globally unique so all user-provided panels
# MUST add a random uniquifier after '#'.  The panel can still be referred 
# to by the portion of the name before '#' and Wing will warn when there 
# are multiple panel definitions with the same base name (in which case
# Wing-defined panels win over user-defined panels and otherwise the
# last user-defined panel type wins when referred to w/o the uniquifier).
_kPanelID = 'pylintpanel#02EFWRQK9X24'

class _CPylintPanelDefn(dockview.CPanelDefn):
  """Panel definition for the project manager"""
  
  def __init__(self, singletons):
    self.fSingletons = singletons
    dockview.CPanelDefn.__init__(self, self.fSingletons.fPanelMgr,
                                 _kPanelID, 'tall', 0)
    winmgr.CWindowConfig(self.fSingletons.fWinMgr, 'panel:%s' % _kPanelID,
                         size=(350, 1000))
    
  def _CreateView(self):
    return _CPylintView(self.fSingletons)
    
  def _GetLabel(self, panel_instance):
    """Get display label to use for the given panel instance"""

    return _('PyLint')
  
  def _GetTitle(self, panel_instance):
    """Get full title for the given panel instance"""

    return _('PyLint Panel')

class _CPylintViewCommands(commandmgr.CClassCommandMap):
  
  kDomain = 'user'
  kPackage = 'pylintpanel'
  
  def __init__(self, singletons, view):
    commandmgr.CClassCommandMap.__init__(self, i18n_module=_i18n_module)
    assert isinstance(view, _CPylintView)

    self.fSingletons = singletons
    self.__fView = view

class _CPylintView(wingview.CViewController):
  """A single template manager view"""
  
  def __init__(self, singletons):
    """ Constructor """
    global gTheView

    # Init inherited
    wingview.CViewController.__init__(self, ())
    
    # External managers
    self.fSingletons = singletons

    self.__fCmdMap = _CPylintViewCommands(self.fSingletons, self)

    self.fTrees = {}
    self.fLabels = {}
    
    self.__CreateGui()

    _init_pylint_version()

    # Remember that this is the default view now
    gTheView = self
    
  def _destroy_impl(self):
    for tree, sview in self.fTrees.values():
      sview.destroy()

  def set_tree_contents(self, tree_contents):
    idx = 0
    for catkey, labeltext, tooltip in gMessageCategories:
      label = gTheView.fLabels[catkey]
      label.set_text('%s (%i)' % (labeltext, len(tree_contents[idx])))
      tree, sview = gTheView.fTrees[catkey]
      tree.set_contents(tree_contents[idx])
      cols = tree.get_columns()

      cols[1].set_visible(False)
      for row in tree_contents[idx]:
        if row[0][1] != '0':
          cols[1].set_visible(True)
          break
        
      idx += 1

  ##########################################################################
  # Inherited calls from wingview.CViewController 
  ##########################################################################

  def GetDisplayTitle(self):
    """ Returns the title of this view suitable for display. """

    return _("PyLint Panel")
  
  def GetCommandMap(self):
    """ Get the command map object for this view. """

    return self.__fCmdMap

  def BecomeActive(self):
    pass

  ##########################################################################
  # Popup menu and actions
  ##########################################################################

  def __CreateGui(self):
    notebook = wgtk.PopupNotebook()
    def popup(widget, event):
      self.__PopupMenu(event, (event.x_root, event.y_root))
    notebook.connect('popup', popup)
    
    for catkey, label, tooltip in gMessageCategories:
      tree = wgtk.SimpleTree([wgtk.gobject.TYPE_STRING] * 5,
                             [wgtk.CellRendererText(), wgtk.CellRendererText(),
                              wgtk.CellRendererText(), wgtk.CellRendererText(),
                              wgtk.CellRendererText()],
                             [_("Line"), _("Column"), _("Message"), _("Full Path"), _("Line Number")])
      tree.unset_flags(wgtk.CAN_FOCUS)
      tree.set_property('headers-visible', True)

      cols = tree.get_columns()
      # Show 'col' column only if any column is > 0
      cols[1].set_visible(False)
      # These are data columns
      cols[3].set_visible(False)
      cols[4].set_visible(False)
      for col in cols:
        col.set_resizable(True)
      
      tree.connect('button-press-event', self.__CB_ButtonPress)
      sel = tree.get_selection()
      sel.connect('changed', self.__CB_SelectionChanged)
      tree.show()
      
      sview = wgtk.ScrolledWindow()
      sview.set_policy(wgtk.POLICY_AUTOMATIC, wgtk.POLICY_AUTOMATIC)
      sview.add(tree)
      sview.show()

      # Event box is needed to make tooltips work in this context (don't ask)
      tab_event_box = wgtk.TooltipBox()
      tab_label = wgtk.Label(label)
      tab_event_box.add(tab_label)
      tab_event_box.show_all()
      wgtk.set_tooltip(tab_event_box, tooltip)

      notebook.append_page(sview, tab_event_box)
      self.__fNotebook = notebook
      
      self.fTrees[catkey] = (tree, sview)
      self.fLabels[catkey] = tab_label
      
    notebook.set_current_page(0)
    self._SetGtkWidget(notebook)
  
  def __CreatePopup(self):
    """Construct popup menu for this object."""

    update_label = _("Update")
    update_label2 = _("Update for Package")
    app = wingapi.gApplication
    ed = app.GetActiveEditor()
    if ed:
      filename = ed.GetDocument().GetFilename()
      update_label = _("Update for %s") % os.path.basename(filename)
      dirname = os.path.dirname(filename)
      if os.path.exists(os.path.join(dirname, '__init__.py')):
        update_label2 = _("Update for Package %s") % os.path.basename(dirname)

    kPopupDefn = [
      ( update_label, 'pylint-execute', {'uscoremagic': False } ),
      ( update_label2, 'pylint-package-execute', {'uscoremagic': False } ),
      ( _("Configure..."), 'pylint-configure' ),
      None,
      ( _("Show PyLint Tool Documentation"), 'pylint-show-docs' ),
    ]
  
    # Create menu
    defnlist = guimgr.menus.GetMenuDefnList(kPopupDefn, self.fSingletons.fGuiMgr, 
                                            self.__fCmdMap, is_popup=1, static=1)
    menu = guimgr.menus.CMenu(_("PyLint"), self.fSingletons.fGuiMgr,
                              defnlist, can_tearoff=0, is_popup=1)
    global gTheView
    gTheView = self
    return menu

  def __CB_SelectionChanged(self, sel):
    pos = self.__fNotebook.get_current_page()
    catkey, label, tdir = gMessageCategories[pos]
    tree, sview = self.fTrees[catkey]
    rows = tree.GetSelectedContent()

  def __CB_ButtonPress(self, tree, event):
    app = wingapi.gApplication

    # Always select the row that the pointer is over
    event_path_info = tree.get_path_at_pos(int(event.x), int(event.y))
    if event_path_info is not None:        
      event_path = event_path_info[0]
      selected_paths = tree.GetSelectedPaths()
      if event_path not in selected_paths:
        sel = tree.get_selection()
        sel.unselect_all()
        sel.select_path(event_path)

    # Popup menu on right mouse button
    if event.button == 3:
      self.__PopupMenu(event, (event.x_root, event.y_root))
      return 1
  
    selected = tree.GetSelectedContent()
    if selected is not None and len(selected) != 0:
      filename = selected[0][3]
      line = int(selected[0][4])
      if event.button == 1 and event.type == wgtk.gdk.BUTTON_PRESS:
        doc = app.OpenEditor(filename)
        doc.ScrollToLine(lineno=line-1, pos='center', select=1)

  def __PopupMenu(self, event, pos):
    """Callback to display the popup menu"""

    menu = self.__CreatePopup()
    menu.Popup(event, pos=pos)

  def _ShowStatusMessage(self, msg):
    for tree, sview in self.fTrees.values():
      column = tree.get_column(2)
      if msg:
        column.set_title(_("Message: %s") % msg.replace('_', '__'))
      else:
        column.set_title(_("Message"))
      
# Register this panel type:  Note that this needs to be at the
# very end of the module so that all the classes defined here
# are already available
_CPylintPanelDefn(wingapi.gApplication.fSingletons)

