"""Example script that implements editing files using templates, both creating 
files from templates or inserting templated bits of code into the current editor.

NOTE: This script is disabled and provided as an example only.  As of Wing
3.1, the  templating/snippets capability is implemented internally rather 
than as a script.  This script represents the functionality that was
delivered in Wing version 2.1.

Some of the API's capabilities exhibited in this script are:

* Accessing the document and editor objects
* Making use of the editor's inline data entry mode
* Accessing project-provided environment variables

The following additional capabilities are also illustrated, but these
reach through the formal API into stable but not formalized internal
functionality of the IDE:

* Writing a data entry dialog
* Adding adhoc commands and custom key bindings for them
* Adding a new tool panel to Wing that includes a notebook of
  several lists and a popup context menu

In general, writing a script of this complexity requires running Wing IDE from
the source distribution, so that Wing (and the script) can be debugged inside
another copy of Wing IDE.

Copyright (c) 2005-2008, Wingware All rights reserved.

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

------
Thanks to Peter Mott for adding support for %% escaping so string formats
can be given as part of templates (and not processed by the template) and
for other improvements.

"""

# This is just an example script so it is disabled
_ignore_scripts = True

import os
import stat
import time
import re
import glob
from sets import Set

import wingapi
_AI = wingapi.CArgInfo
import edit.prefs

# Scripts can be internationalized with gettext.  Strings to be translated
# are sent to _() as in the code below.
import gettext
_ = gettext.translation('scripts_templating', fallback = 1).ugettext

# This special attribute is used so that the script manager can translate
# also docstrings for the commands found here
_i18n_module = 'scripts_templating'

# XXX These modules are not part of the documented API and are 
# XXX subject to change
from guiutils import formbuilder
from wingutils import datatype
from wingutils import textutils

# Set this to True to collect arguments before pasting the snippet 
# rather than pasting snippet and collecting args inline
_kOldStyleArgCollection = False

######################################################################
# Utilities

gTemplateDirs = [
  (_("System-wide"), os.path.join(wingapi.gApplication.GetWingHome(), 'scripts', 'templates')),
  (_("User-specific"), os.path.join(wingapi.gApplication.GetUserSettingsDir(), 'templates'))
]

def _get_environment(env, default=None):
  """Get value for given environment variable, either as defined in 
  Project Properties or in the inherited environment if present.
  Returns the given default when the value cannot be found."""
  
  app = wingapi.gApplication
  proj = app.GetProject()
  doc = app.GetActiveDocument()
  if doc is not None:
    filename = doc.GetFilename()
  else:
    filename = None
  env_dict = proj.GetEnvironment(filename)

  return env_dict.get(env, os.environ.get(env, default))
  
def _expand_envs(txt):
  if txt is None:
    return None
  app = wingapi.gApplication
  proj = app.GetProject()
  doc = app.GetActiveDocument()
  txt = txt.replace('$(__DATE_NOW__)', _get_date_string())
  txt = txt.replace('$(__DATE_TIME_NOW__)', _get_datetime_string())
  if doc is not None:
    filename = doc.GetFilename()
  else:
    filename = None
  return proj.ExpandEnvVars(txt, filename)

def _get_date_string():
  dformat = _get_environment('__DATE_FORMAT__', "%x")
  return time.strftime(dformat)

def _get_datetime_string():
  dformat = _get_environment('__DATETIME_FORMAT__', "%x %X")
  return time.strftime(dformat)

gTemplates = {}

_parse_regex = re.compile(r"(?<!%)%\((.*?)\)s")

def _parse_argspec(spec):
  """Parse argument spec to determine argname, arginfo to use for
  collecting the value from user if necessary, and specification
  for default value."""
  
  spec = spec[2:-2]
  
  parts = spec.split('|')
  if len(parts) > 3:
    parts = (parts[0], parts[1], '|'.join(parts[2:]))
  name = parts[0].strip().lower()
  type = 'string'
  default = None
  if len(parts) > 1:
    type = parts[1].strip().lower()
    if type == '':
      type = 'string'
  if len(parts) > 2:
    default = parts[2]

  if type.startswith('string'):
    if type.find('(') > 0:
      slen = int(type[type.find('(')+1:-1])
    else:
      slen = 80
    arginfo = _AI(name.replace('_', ' ').title(), 
                  datatype.CType(''), formbuilder.CSmallTextGui(slen))
  elif type == 'filename':
    arginfo = _AI(name.replace('_', ' ').title(), 
                  datatype.CType(''), formbuilder.CFileSelectorGui())
  elif type.startswith('date'):
    arginfo = _AI(name.replace('_', ' ').title(), 
                  datatype.CType(''), formbuilder.CSmallTextGui())
    if type == 'date':
      default = '$(__DATE_NOW__)'
    else:
      default = '$(__DATE_TIME_NOW__)'
  else:
    raise NotImplementedError, "Invalid argument type '%s'" % type

  return name, arginfo, default

def _parse_template(txt):
  """Parse template text to extract information about the arguments to 
  collect from user and where to insert them in the template.  Returns
  (ptxt, info) where ptxt is the text with argument specs removed and
  info is a list of (argname, arginfo, default, pos, flags) that defines the
  argument name, _AI() spec for data collection, default spec (which
  isn't interpreted until the template is actually used), and the
  position in ptxt where that argument should be placed."""
  
  ret_txt = '' 
  c_ret_txt = ''
  ret_info = []
  txtpos = 0 
  matches = _parse_regex.finditer(txt)
  for match in matches:

    segment = txt[txtpos:match.start()]   
    ret_txt += segment
    c_ret_txt += segment.replace("%%","%")
    txtpos = match.end()

    argspec = txt[match.start():match.end()]
    argname, arginfo, default = _parse_argspec(argspec)
    flags = {}
    while len(argname) > 0 and argname[0] in '!@':
      if argname.startswith('!'):
        argname = argname[1:]
        flags['always-show'] = 1
      if argname.startswith('@'):
        argname = argname[1:]
        flags['wrap-lines'] = 1
    
    # Position of the arg in new text is just at the end of the shortened text 
    ret_info.append((argname, arginfo, default, len(c_ret_txt), flags))

  c_ret_txt += txt[txtpos:].replace("%%","%") #segment after last variable   
  return c_ret_txt, ret_info

def _process_template(tdir, fname):
  """Read in a single template and add it to the registry"""

  templates = gTemplates.setdefault(tdir, {})
  
  name, ext = os.path.splitext(fname)
  filename = os.path.join(tdir, fname)
  if not os.path.exists(filename) or os.path.isdir(filename):
    if templates.has_key(name):
      filename, ptxt, arginfos, modinfo = templates[name]
      if os.path.samefile(os.path.abspath(os.path.expanduser(os.path.dirname(filename))), 
                          os.path.abspath(os.path.expanduser(tdir))):
        del templates[name]
    return
  
  f = open(filename)
  txt = f.read()
  f.close()

  ptxt, arginfos = _parse_template(txt)

  modtime = os.stat(filename).st_mtime
  templates[name] = (filename, ptxt, arginfos, (modtime, tdir, fname))
  
def _scan_for_templates():
  """Scan templates directories and load templates found in them"""
  
  if _ignore_scripts:
    return
  
  app = wingapi.gApplication

  for label, tdir in gTemplateDirs:
    if not os.path.exists(tdir):
      try:
        os.mkdir(tdir)
      except:
        pass
    try:
      files = os.listdir(tdir)
    except:
      files = []
    for fname in files:
      try:
        _process_template(tdir, fname)
      except:
        print "Warning: Failed to process template %s:" % fname
        from wingutils import reflect
        exc = reflect.GetCurrentException()
        print "  " + "\n  ".join(exc)

_scan_for_templates()

def _fill_in_defaults(arginfos, value_dict):
  """Fill in any missing default values from the given value dict."""

  new_arginfos = []

  for i in range(0, len(arginfos)):
    argname, arginfo, default, insert_pos, flags = arginfos[i]
    default = value_dict.get(argname, default)
    new_arginfos.append((argname, arginfo, default, insert_pos, flags))

  return new_arginfos

def _find_wrap_prefix(txt):
  """Find prefix to use in wrapping long lines for a value placed on
  the last line of the given text"""
  
  lines = txt.splitlines()
  if len(lines) == 0:
    return '', ''
  
  line = lines[-1]
  prefix = ''
  while len(line) > 0 and line[0] in ' \t#':
    prefix += line[0]
    line = line[1:]

  return prefix, prefix + line

def _template_to_text(ttxt, arginfos, completion, use_window=False):
  """Turn given template into text by resolving defaults, prompting user for
  values, and inserting them into the template.  The completion routine
  is called with the final text when ready."""
  
  app = wingapi.gApplication

  # Resolve defaults for arginfo and determine if we need to collect
  # any from the user
  missing = []
  value_list = []
  value_positions = []
  value_flags = []
  known_values = {}
  for argname, arginfo, default, insert_pos, flags in arginfos:
    if default is not None:
      default = _expand_envs(default)
      known_values[argname] = default
    if default is None:
      missing.append((argname, arginfo, insert_pos))
    value_list.append(default)
    value_positions.append(insert_pos)
    value_flags.append(flags)

  # Insert default values into text and prepare for inline argument entry
  if not _kOldStyleArgCollection:
    txt = []
    ttxtpos = 0
    txtpos = 0
    tab_sequence = []
    for i, value in enumerate(value_list):
      pos = value_positions[i]
      if value is None:
        value = ''
      if value_flags[i].get('wrap-lines', 0):
        prefix_line = ttxt[ttxtpos:pos]
        if len(txt) > 0:
          prefix_line = txt[-1] + prefix_line
        prefix, prefix_line = _find_wrap_prefix(prefix_line)
        from edit import prefs
        wrap_col = app.GetPreference(prefs.kTextWrapColumn) - len(prefix_line)
        value = textutils.WrapParagraph(value, wrap_col, '', prefix)
      txt.append(ttxt[ttxtpos:pos] + value)
      txtpos += pos - ttxtpos + len(value)
      ttxtpos = pos
      tab_sequence.append((txtpos, txtpos - len(value)))
    txt.append(ttxt[ttxtpos:])
    txt = ''.join(txt)
    completion(txt, tab_sequence)

  # Old style arg collection through command manager
  else:

    # No missing args -- build text and pass to completion routine
    if len(missing) == 0:
      txt = []
      ttxtpos = 0
      for i, value in enumerate(value_list):
        pos = value_positions[i]
        if value_flags[i].get('wrap-lines', 0):
          prefix_line = ttxt[ttxtpos:pos]
          if len(txt) > 0:
            prefix_line = txt[-1] + prefix_line
          prefix, prefix_line = _find_wrap_prefix(prefix_line)
          from edit import prefs
          wrap_col = app.GetPreference(prefs.kTextWrapColumn) - len(prefix_line)
          value = textutils.WrapParagraph(value, wrap_col, '', prefix)
        txt.append(ttxt[ttxtpos:pos] + value)
        ttxtpos = pos
      txt.append(ttxt[ttxtpos:])
      txt = ''.join(txt)
      completion(txt)
      
    # Collect any missing args by building a command on the fly with 
    # the same arguments as the template.  Then execute the so the 
    # command manager collects any missing values from the user.
    else:
      argnames = []
      ainfo_dict = {}
      for i in range(0, len(arginfos)):
        argname, arginfo, default, insert_pos, flags = arginfos[i]
        if not known_values.has_key(argname) or flags.get('always-show', False):
          argnames.append(argname)
          ainfo_dict[argname] = arginfo
        if known_values.has_key(argname):
          arginfos[i] = argname, arginfo, known_values[argname], insert_pos, flags
  
      def do_cmd(**args):
        _template_to_text(ttxt, _fill_in_defaults(arginfos, args), completion,
                          use_window)      
      def no_dup(L):
        return list(Set(L))
      def_str = 'lambda ' + ', '.join(no_dup(argnames)) + ': do_cmd(**locals())'
      env = { 'do_cmd': do_cmd }
      env.update(known_values)
      syn_cmd = eval(def_str, env)
      if use_window:
        flags = { 'override_emacs_argentry': True }
      else:
        flags = commandmgr.kNoFlags
  
      import command.commandmgr
      syn_cmd = command.commandmgr.CreateCommand(syn_cmd, 'user', 'templating',
                                                 arginfo=ainfo_dict, flags=flags)
  
      app.ExecuteCommand(syn_cmd, **known_values)

def _convert_for_file(txt, tab_sequence, editor):
  """Convert the given text's indent style and newlines for insertion into 
  the given editor"""
  
  # Determine tab/indent for this file
  indent_style = editor.GetIndentStyle()
  indent_size = editor.GetIndentSize()
  tab_size = editor.GetTabSize()

  # Delete current selection on editor
  start, end = editor.GetSelection()
  doc = editor.GetDocument()
  doc.DeleteChars(start, end-1)

  # Parse and remove any fixed indent level indicator at start
  level = ''
  if len(txt) > 2 and txt[0] == '|':
    bpos = txt.find('|', 1)
    if bpos > 0:
      level = txt[1:bpos]
      txt = txt[bpos+1:]
      tab_sequence = textutils.AdjustTextOffsets(tab_sequence, 0, -bpos-1)

  # Compute indent for match-based indent positioning
  indent_incr = 0
  if level.startswith('m'):
    editor.ExecuteCommand('indent-to-match')
    level = level[1:]
    line_start = doc.GetLineStart(doc.GetLineNumberFromPosition(start))
    start, end = editor.GetSelection()
    indent_incr = (start - line_start) / indent_size
    doc.DeleteChars(line_start, start-1)
    start = line_start

  # Modify indent level for absolute or relative indent positioning
  if len(level) > 0:
    try:
      indent_incr += int(level)
    except:
      indent_incr = 0
      
  # Added leading indent must be zero or more
  indent_incr = max(0, indent_incr)
  
  # Convert indents from tab-only canonical form used in templates
  text_lines = txt.splitlines()
  text_pos = 0
  for i in range(0, len(text_lines)):
    line = text_lines[i]
    indent_level = 0
    while indent_level < len(line) and line[indent_level] == '\t':
      indent_level += 1
    indent = textutils.GetIndentPrefix((indent_level + indent_incr) * indent_size, 
                                       indent_style==1, tab_size)
    text_lines[i] = indent + line[indent_level:]
    tab_sequence = textutils.AdjustTextOffsets(tab_sequence, text_pos, len(indent)-indent_level)
    text_pos += len(text_lines[i]) + len(editor.GetEol())

  # Convert newlines to correct form for the file
  newline = editor.GetEol()
  txt = newline.join(text_lines)

  # Find cursor location indicator
  cursor_pos = txt.find('|!|')
  if cursor_pos >= 0:
    txt = txt.replace('|!|', '')
    tab_sequence = textutils.AdjustTextOffsets(tab_sequence, cursor_pos, -3)
    tab_sequence.append((cursor_pos, cursor_pos))
    auto_terminate = True
  else:
    auto_terminate = False

  # Insert template into editor
  if _kOldStyleArgCollection:
    doc.InsertChars(start, txt)
  else:
    editor.PasteTemplate(txt, tab_sequence, auto_terminate)
  
  # Set focus on editor
  editor.GrabFocus()
  
def _new_file_template(ext, txt, tab_sequence):
  """Create a new file with given extension and initial content"""
  
  # Create new file of appropriate type
  app = wingapi.gApplication  
  app.ExecuteCommand('new-file', ext=ext)
  
  # Convert text indents and newlines to match file
  editor = app.GetActiveEditor()
  _convert_for_file(txt, tab_sequence, editor)
  
def _insert_template(txt, tab_sequence):
  """Insert given content into currently active editor"""

  # Convert text indents and newlines to match file
  app = wingapi.gApplication
  editor = app.GetActiveEditor()
  if editor is None:
    wingapi.gApplication.ShowMessageDialog(
      _("No Active Editor"),
      _("Could not paste the selected template because there is "
        "no active editor"),
    )
    return
  _convert_for_file(txt, tab_sequence, editor)

def _get_template(template_name, tdir=None):
  """Get given template by name, optionally constraining search to given
  directory. This also loads new templates on demands and reloads the template
  if it has changed on disk. Returns (filename, template_text, arginfos)."""

  # Compute which template dirs are acceptible
  if tdir is not None:
    allowed_tdirs = [tdir]
  else:
    allowed_tdirs = [t for l, t in gTemplateDirs]
    
  # Run through template directories backwards (so that user-defined templates
  # can override system-defined ones)
  for i in range(len(gTemplateDirs)-1, -1, -1):
    
    # Look for existing template entry
    label, tdir = gTemplateDirs[i]
    if tdir not in allowed_tdirs:
      continue
    templates = gTemplates.setdefault(tdir, {})    
    filename, ttxt, arginfos, modinfo = templates.get(template_name, (None, None, None, None))
    
    # If not found, try to load it:  There may be a newly added template file
    if ttxt is None:
      candidates = glob.glob(os.path.join(tdir, template_name + '.*'))
      for candidate in candidates:
        _process_template(tdir, os.path.basename(candidate))
        if templates.has_key(template_name):
          filename, ttxt, arginfos, modinfo = templates.get(template_name, (None, None, None, None))
          break
      if templates.has_key(template_name):
        break
  
    # If found and changed on disk, then reload it if needed
    else:
      old_modtime, tdir, fname = modinfo
      try:
        modtime = os.stat(filename).st_mtime
      except:
        modtime = old_modtime + 1
      if old_modtime < modtime:
        _process_template(tdir, fname)
        filename, ttxt, arginfos, modinfo = templates.get(template_name, (None, None, None, None))

    # Return if anything found
    if ttxt is not None:
      return filename, ttxt, arginfos

  # Nothing found
  print "Unknown template name %s" % template_name
  return None, None, None
  
def _all_template_names():
  names = {}
  for label, tdir in gTemplateDirs:
    names.update(gTemplates.setdefault(tdir, {}))
  return names.keys()

def _template_name_arginfo():
  return _AI(_("Template Name"), datatype.CType(''), 
             formbuilder.CSmallTextGui(choices=_all_template_names()))

######################################################################
# Commands

def template(template_name, tdir=None, use_window=0):
  """Insert given template into current editor. When a template directory is
  used, the template is drawn from there. Otherwise, the template path is
  traversed to find the template. When use_window is True, argument collection
  occurs in a dialog box instead of at the bottom of the current document
  window."""

  # Find template
  filename, ttxt, arginfos = _get_template(template_name, tdir)
  if ttxt is None:
    return

  # Convert template into text and insert into current editor
  _template_to_text(ttxt, arginfos, _insert_template, use_window)

# This defines how arguments are collected from the user if the command
# is executed with missing arguments
template.arginfo = {
  'template_name': _template_name_arginfo,
  'tdir': _AI('', datatype.CNoneOr(datatype.CType('')), formbuilder.CHiddenGui()),
  'use_window': _AI('', datatype.CBoolean(), formbuilder.CHiddenGui()),
}

def template_file(template_name, tdir=None, use_window=0):
  """Create a new file containing the given template. When a template directory is
  used, the template is drawn from there. Otherwise, the template path is
  traversed to find the template. When use_window is True, argument collection
  occurs in a dialog box instead of at the bottom of the current document
  window."""

  # Find template
  filename, ttxt, arginfos = _get_template(template_name, tdir)
  if ttxt is None:
    return
  name, ext = os.path.splitext(filename)
  
  # Convert template into text and build new file with it
  def doit(rtxt, tab_sequence):
    _new_file_template(ext, rtxt, tab_sequence)
  _template_to_text(ttxt, arginfos, doit, use_window)

template_file.arginfo = template.arginfo

######################################################################
# Simple template management tool

# XXX This is advanced scripting that accesses Wing IDE internals, which
# XXX are subject to change from version to version without notice.

from wingutils import location
from guiutils import wgtk
from guiutils import dockview
from guiutils import wingview
from guiutils import winmgr
from guiutils import dialogs

from command import commandmgr
import guimgr.menus
from guimgr import messages
from guimgr import keyboard

# Note that panel IDs must be globally unique so all user-provided panels
# MUST add a random uniquifier after '#'.  The panel can still be referred 
# to by the portion of the name before '#' and Wing will warn when there 
# are multiple panel definitions with the same base name (in which case
# Wing-defined panels win over user-defined panels and otherwise the
# last user-defined panel type wins when referred to w/o the uniquifier).
_kPanelID = 'templating#02EFWRQK9X23'

class _CTemplatePanelDefn(dockview.CPanelDefn):
  """Panel definition for the project manager"""
  
  def __init__(self, singletons):
    self.fSingletons = singletons
    dockview.CPanelDefn.__init__(self, self.fSingletons.fPanelMgr,
                                 _kPanelID, 'tall', 0)
    winmgr.CWindowConfig(self.fSingletons.fWinMgr, 'panel:%s' % _kPanelID,
                         size=(350, 1000))
    
  def _CreateView(self):
    return _CTemplateView(self.fSingletons)
    
  def _GetLabel(self, panel_instance):
    """Get display label to use for the given panel instance"""

    return _('Templates')
  
  def _GetTitle(self, panel_instance):
    """Get full title for the given panel instance"""

    return _('Template Manager')

class _CTemplateViewCommands(commandmgr.CClassCommandMap):
  """Commands available on a specific instance of the template manager tool"""
  
  kDomain = 'user'
  kPackage = 'templating'
  
  def __init__(self, singletons, view):
    commandmgr.CClassCommandMap.__init__(self, i18n_module=_i18n_module)
    assert isinstance(view, _CTemplateView)

    self.fSingletons = singletons
    self.__fView = view

  def template_add(self, new_template_name, file_extension):
    """Add a new template"""

    self.__fView._AddTemplate(new_template_name, file_extension)
    
  _Flags_template_add = { 'override_emacs_argentry': True }
  _ArgInfo_template_add = {
    'new_template_name': _AI(_("Template Name"), datatype.CType(''), 
                         formbuilder.CSmallTextGui()),
    'file_extension': _AI(_("New File Extension"), datatype.CType(''),
                          formbuilder.CSmallTextGui()),
  }
  
  def template_selected_edit(self):
    """Edit the selected template"""

    tdir, template_name = self.__fView._GetSelectedTemplate()
    templates = gTemplates[tdir]
    filename, ptxt, arginfos, modinfo = templates[template_name]
    wingapi.gApplication.OpenEditor(filename)
    
  def _IsAvailable_template_selected_edit(self):
    tdir, template_name = self.__fView._GetSelectedTemplate()
    return template_name is not None
  
  def template_selected_remove(self):
    """Remove the selected template"""
    
    self.__fView._RemoveTemplate()
    
  _IsAvailable_template_selected_remove = _IsAvailable_template_selected_edit
  
  def template_assign_key_binding(self):
    """Assign/reassign/unassign the key binding associated with
    the given template"""
    
    tdir, template_name = self.__fView._GetSelectedTemplate()

    def assign_cmd(key_binding, template_name=template_name):
      self.__fView._SetKeyBinding(template_name, key_binding)
    arginfo = {
      'key_binding': _AI(_("Key Binding"), datatype.CType(''), keyboard.CKeyStrokeEntryFormlet()),
      'template_name': _AI('', datatype.CType(''), formbuilder.CHiddenGui()),
    }
    flags = { 'force_dialog_argentry': True }
    
    import command.commandmgr
    syn_cmd = command.commandmgr.CreateCommand(assign_cmd, 'user', 'templating',
                                               arginfo=arginfo, flags=flags)

    wingapi.gApplication.ExecuteCommand(syn_cmd)

  _IsAvailable_template_assign_key_binding = _IsAvailable_template_selected_edit
  
  def template_clear_key_binding(self):
    """Clear the key binding associated with the given template"""
    
    tdir, template_name = self.__fView._GetSelectedTemplate()

    self.__fView._SetKeyBinding(template_name, '')

  _IsAvailable_template_clear_key_binding = _IsAvailable_template_selected_edit
  
  def template_show_docs(self):
    """Show the Wing IDE documentation section for the template manager"""

    wingapi.gApplication.ExecuteCommand('show-document', section='edit/templating')
    
  def template_selected_paste(self):
    """Paste the currently selected template into the current editor"""

    tdir, template_name = self.__fView._GetSelectedTemplate()
    template(template_name, tdir, use_window=True)
    
  def _IsAvailable_template_selected_paste(self):
    tdir, template_name = self.__fView._GetSelectedTemplate()
    editor = wingapi.gApplication.GetActiveEditor()
    return template_name is not None and editor is not None

  def template_selected_new_file(self):
    """Paste the currently selected template into a new editor"""
    
    tdir, template_name = self.__fView._GetSelectedTemplate()
    template_file(template_name, tdir, use_window=True)

  _IsAvailable_template_selected_new_file = _IsAvailable_template_selected_edit
  
  def template_reload_all(self):
    """Reload all the template files.  The template manager does this
    automatically most of the time, but reload can be useful to cause
    the template panel display to update when templates are added or
    removed from outside of Wing."""
    
    self.__fView._UpdateGui()
    
class _CTemplateView(wingview.CViewController):
  """A single template manager view"""
  
  def __init__(self, singletons):
    """ Constructor """

    # Init inherited
    wingview.CViewController.__init__(self, ())
    
    # External managers
    self.fSingletons = singletons

    self.__fCmdMap = _CTemplateViewCommands(self.fSingletons, self)

    self.__fLastClicked = None
    self.fTrees = {}
    
    self.__CreateGui()
    self._UpdateGui()
    
  def _destroy_impl(self):
    
    for tree, sview in self.fTrees.values():
      sview.destroy()

  ##########################################################################
  # Inherited calls from wingview.CViewController 
  ##########################################################################

  def GetDisplayTitle(self):
    """ Returns the title of this view suitable for display. """

    return _("Template Manager")
  
  def GetCommandMap(self):
    """ Get the command map object for this view. """

    return self.__fCmdMap

  @wgtk.perspective_tools_and_editors(set())
  @wgtk.perspective_tools_only(set())
  def GetVisualState(self, errs, constraint=None):
    try:
      tree_states = {}
      for tdir, (tree, sview) in self.fTrees.items():
        tree_states[tdir] = tree.GetSelectedContent()
      state = {
        'tree-states': tree_states,
      }
    except:
      raise
      errs.append(_("Template manager state"))
      state = {}
      
    return state
  
  def SetVisualState(self, state, errs):
    try:
      tree_states = state.get('tree-states')
      for tdir, (tree, sview) in self.fTrees.items():
        if tree_states.has_key(tdir):
          tree._SetTreeState(tree_states[tdir])
    except:
      errs.append(_("Template manager state"))

  def BecomeActive(self):
    pass

  ##########################################################################
  # Popup menu and actions
  ##########################################################################

  def __CreateGui(self):

    notebook = wgtk.Notebook()
    
    for label, tdir in gTemplateDirs:
      
      key_binding_renderer = wgtk.CellRendererText()
      tree = wgtk.SimpleTree([wgtk.gobject.TYPE_STRING] * 2, 
                             [wgtk.CellRendererText(), wgtk.CellRendererText()],
                             [_("Template Name"), _("Key Binding")])
      tree.unset_flags(wgtk.CAN_FOCUS)
      tree.set_property('headers-visible', False)
      
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
      wgtk.set_tooltip(tab_event_box, tdir)

      notebook.append_page(sview, tab_event_box)
      self.__fNotebook = notebook
      
      self.fTrees[tdir] = (tree, sview)
      
    notebook.set_current_page(len(gTemplateDirs)-1)
    self._SetGtkWidget(notebook)
    
  def _UpdateGui(self):
    for label, tdir in gTemplateDirs:
      tree, sview = self.fTrees[tdir]
      template_names = gTemplates.setdefault(tdir, {}).keys()
      template_names.sort()
      tree.set_contents([((name, self._LookupKeyBinding(name)),) for name in template_names])

  def _LookupKeyBinding(self, template_name):
    """Look up the key binding for the given template"""
    
    from guimgr import prefs
    keymap = wingapi.gApplication.GetPreference(prefs.kKeyMapOverridesPref)
    cmd = 'template(template_name="%s")' % template_name
    for k, v in keymap.items():
      if v == cmd:
        return k
    return ''
    
  def _SetKeyBinding(self, template_name, key_binding):
    """Set the key binding for the given template"""

    key_binding = key_binding.strip()
    
    from guimgr import prefs
    keymap = wingapi.gApplication.GetPreference(prefs.kKeyMapOverridesPref)
    keymap = dict(keymap)

    cmd = 'template(template_name="%s")' % template_name
    for k, v in list(keymap.items()):
      if v == cmd:
        del keymap[k]
    if key_binding != '':
      keymap[key_binding] = cmd

    wingapi.gApplication.SetPreference(prefs.kKeyMapOverridesPref, keymap)
    self._UpdateGui()
    
  def _GetSelectedTemplate(self):
    """Get the template directory and template name for currently selected template"""
    
    pos = self.__fNotebook.get_current_page()
    label, tdir = gTemplateDirs[pos]
    templates = gTemplates.setdefault(tdir, {})
    tree, sview = self.fTrees[tdir]
    
    template_names = tree.GetSelectedContent()
    if len(template_names) != 1:
      return tdir, None

    return tdir, template_names[0][0]
    
  def _AddTemplate(self, new_template_name, file_extension):
    """Add a new template to the currently selected template directory"""

    while len(file_extension) > 0 and file_extension[0] in '.*':
      file_extension = file_extension[1:]
      
    pos = self.__fNotebook.get_current_page()
    label, tdir = gTemplateDirs[pos]
    templates = gTemplates.setdefault(tdir, {})
    
    # Check if template already exists and offer to open it
    if templates.has_key(new_template_name):      
      filename, ptxt, arginfos, modinfo = templates[new_template_name]
      title = _("Template already exists")
      text = _("The template '%s' already exists in %s.  Do you want to open "
               "the existing file?") % (new_template_name, filename)
      def open_cb(*args):
        wingapi.gApplication.OpenEditor(filename)
      buttons = [
        dialogs.CButtonSpec(_("Open Existing"), open_cb, wgtk.STOCK_YES),
        dialogs.CButtonSpec(_("Cancel"), None, wgtk.STOCK_NO),
      ]
      dlg = messages.CMessageDialog(self.fSingletons, title, text, [], buttons)
      dlg.RunAsModal()
      return

    # Add dummy entry so it gets loaded when saved and inserted into panel
    filename = os.path.join(tdir, new_template_name + '.' + file_extension)
    ptxt = None
    arginfos = []
    modinfo = (0, tdir, filename)
    templates[new_template_name] = (filename, ptxt, arginfos, modinfo)

    # Update panel
    self._UpdateGui()
    
    # Open the new template file
    editor = wingapi.gApplication.OpenEditor(filename)
    
    # Always indent with tabs only
    editor.SetIndentStyle(2)
    
    # Watch the document -- when closed, we remove the template listing
    # if the file doesn't exist on disk because it was never saved
    doc = editor.GetDocument()
    def destroy_cb(obj):
      if not os.path.exists(filename):
        del templates[new_template_name]
        self._UpdateGui()
    doc.connect_while_alive('destroy', destroy_cb, self)

  def _RemoveTemplate(self):
    """Add currently selected template from template directory"""

    tdir, template_name = self._GetSelectedTemplate()
    templates = gTemplates[tdir]
    filename, ptxt, arginfos, modinfo = templates[template_name]
    
    title = _("Remove Disk File?")
    text = _("Really remove the template '%s' in %s?  This will permanently "
             "erase the file from disk.") % (template_name, filename)
    def remove_cb(*args):
      os.unlink(filename)
      del templates[template_name]
      self._UpdateGui()
    buttons = [
      dialogs.CButtonSpec(_("Remove File"), remove_cb, wgtk.STOCK_YES),
      dialogs.CButtonSpec(_("Cancel"), None, wgtk.STOCK_NO),
    ]
    dlg = messages.CMessageDialog(self.fSingletons, title, text, [], buttons)
    dlg.RunAsModal()

  def __CreatePopup(self):
    """Construct popup menu for this object."""

    kPopupDefn = [
      ( _("Paste Into Current Editor"), 'template-selected-paste' ),
      ( _("Paste Into New File"), 'template-selected-new-file' ),
      None,
      ( _("Add New Template"), 'template-add' ),
      ( _("Edit Template"), 'template-selected-edit' ),
      ( _("Remove Template"), 'template-selected-remove' ),
      None,
      ( _("Assign Key Binding"), 'template-assign-key-binding' ),
      ( _("Clear Key Binding"), 'template-clear-key-binding' ),
      None,
      ( _("Reload All Templates"), 'template-reload-all' ),
      None,
      ( _("Show Templating Documentation"), 'template-show-docs' ),
    ]
  
    # Create menu
    defnlist = guimgr.menus.GetMenuDefnList(kPopupDefn, self.fSingletons.fGuiMgr, 
                                            self.__fCmdMap, is_popup=1, static=1)
    menu = guimgr.menus.CMenu(_("Templates"), self.fSingletons.fGuiMgr,
                              defnlist, can_tearoff=0, is_popup=1)
    return menu

  def __CB_SelectionChanged(self, sel):

    pos = self.__fNotebook.get_current_page()
    label, tdir = gTemplateDirs[pos]
    tree, sview = self.fTrees[tdir]
    rows = tree.GetSelectedContent()

  def __CB_ButtonPress(self, tree, event):

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
  
    # Middle mouse or double click pastes template into current editor
    selected = tree.GetSelectedContent()
    if len(selected) != 0:
      template_name = selected[0][0]
    else:
      template_name = None
    if ((event.button == 2 and event.type == wgtk.gdk.BUTTON_PRESS) or
        (event.button == 1 and event.type == wgtk.gdk._2BUTTON_PRESS and
         self.__fLastClicked == template_name and template_name is not None)):
      editor = wingapi.gApplication.GetActiveEditor()
      if editor is None:
        wingapi.gApplication.ShowMessageDialog(
          _("No Active Editor"),
          _("Could not paste the selected template because there is "
            "no active editor"),
        )
      else:
        template(template_name, use_window=True)
      return 1
    
    self.__fLastClicked = template_name

  def __PopupMenu(self, event, pos):
    """Callback to display the popup menu"""

    menu = self.__CreatePopup()
    menu.Popup(event, pos=pos)

# Register this panel type:  Note that this needs to be at the
# very end of the module so that all the classes defined here
# are already available
if not _ignore_scripts:
  _CTemplatePanelDefn(wingapi.gApplication.fSingletons)

