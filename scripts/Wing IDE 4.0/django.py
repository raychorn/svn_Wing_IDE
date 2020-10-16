"""A plugin that provides Django-specific functionality when a project
looks like it contains Django files.

Copyright (c) 2010, Wingware All rights reserved.

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

"""

import os
import sys
import time
import wingapi
from wingutils import datatype
from wingutils import wingwebbrowser
from wingutils import fileutils
from wingutils import location
from guiutils import formbuilder

# Scripts can be internationalize with gettext.  Strings to be translated
# are sent to _() as in the code below.
import gettext
_ = gettext.translation('scripts_django', fallback = 1).ugettext

# This special attribute is used so that the script manager can translate
# also docstrings for the commands found here
_i18n_module = 'scripts_django'

def _override_context():
  """Utility that determines contexts attribute for always-active 
  commands so those commands don't show in the GUI when the plugin
  is inactive"""  
  if _CDjangoPluginActivator._instance._IsDjangoProject():
    return [wingapi.kContextNewMenu(_("Djang_o"), group=2)]
  else:
    return []
  
def _appname_formlet():
  apps = _CDjangoPluginActivator._instance._GetDjangoAppDirs()
  appnames = [os.path.basename(a) for a in apps]
  choices = [(a, a) for a in appnames]
  return formbuilder.CPopupChoiceGui(choices)

def _get_pyexec_from_django_admin(django_admin):
  try:
    f = open(django_admin)
    lines = f.readlines()
    f.close()
  except:
    return None, ''
  if lines and lines[0].startswith('#!'):
    py = lines[0][2:].strip()
    parts = py.split()
    if len(parts) > 1 and parts[0].endswith('env'):
      if sys.platform != 'win32':
        py = wingapi.gApplication.FindPython()
      else:
        dirs = ('bin', 'django', 'site-packages', 'Lib')
        dirname = django_admin
        ok = True
        for dir in dirs:
          dirname = os.path.dirname(dirname)
          if not dirname.endswith(dir):
            ok = False
            break
        if not ok:
          py = wingapi.gApplication.FindPython()
        else:
          py = os.path.join(os.path.dirname(dirname), 'python.exe')        
    return py
  return None, ''
  
def _get_actions_list(actions):
  msg = _("The following actions were completed successfully:\n\n")
  for i, action in enumerate(actions):
    msg += "(%i) %s" % (i+1, action)
    if i < len(actions) - 2:
      msg += ",\n"
    elif i < len(actions) - 1:
      msg += _(", and\n")
    else:
      msg += '.'
  return msg
  
def _get_errors_list(errs):
  if not errs:
    return ''
  else:
    msg = _("Some errors occurred.  You may need to correct these manually:")
    for err in errs:
      msg += '\n\n* %s' % err
    return msg + '\n\n'
  
def _get_eol(txt):
  if txt.find('\r\n') >= 0:
    eol = '\r\n'
  elif txt.find('\r') >= 0:
    eol = '\r'
  else:
    eol = '\n'
  return eol

_kMissingPythonMessage = _("You may need to configure Python Executable in Project Properties")
def _get_output(output, separator='\n\n', pfx=('Stdout: ', 'Stderr: '), verbose=0):
  retval = []
  if output[0]:
    retval.append(pfx[0] + output[0].rstrip() + separator)
  if output[1]:
    retval.append(pfx[1] + output[1].rstrip())
  if verbose and output[1]:
    retval.append(separator + _kMissingPythonMessage)
  return ''.join(retval)

def _store_dialog_fields(django_admin, parent_directory, superuser, superuser_email):
  proj = wingapi.gApplication.GetProject()
  proj.SetAttribute('django-admin', django_admin)
  proj.SetAttribute('django-parent-directory', parent_directory)
  proj.SetAttribute('django-superuser', superuser)
  proj.SetAttribute('django-superuser-email', superuser_email)

def django_start_project(django_admin, parent_directory, site_name,
                         superuser, superuser_email, superuser_password):
  """Start a new Django project with given site name and superuser account.
  This will prompt for the location of django-admin.py, the parent directory,
  and the site name to use. It then runs django-admin.py startproject, edits
  settings.py fields DATABASE_ENGINE and DATABASE_NAME to use sqlite3 by
  default, adds django.contrib.admin to INSTALLED_APPS in settings.py, runs
  syncdb (creating superuser account if one was given), sets up the default
  admin templates by copying base_site.html into the project, and then offers
  to create a new project in Wing and run the django-setup-wing-project
  command to configure the Wing IDE project for use with the new Django
  project."""
  
  actions = []
  errs = []
  app = wingapi.gApplication

  # Store last entered dialog fields in current project
  _store_dialog_fields(django_admin, parent_directory, superuser, superuser_email)
  
  # Try to expand if did not give full path
  if not os.path.isabs(django_admin):
    path = os.environ.get("PATH")
    if path:
      for d in path.split(os.pathsep):
        fullpath = fileutils.join(d, django_admin)
        if os.path.exists(fullpath):
          django_admin = fullpath

  # Check that django-admin.py could be found
  if not os.path.exists(django_admin):
    title = _("Could not find django-admin.py")
    if not os.path.isabs(django_admin):
      msg = _("Could not find django-admin.py on the path.  Please specify the full path.")
    else:
      msg = _("Could not open %s -- please check the path") % django_admin
    app.ShowMessageDialog(title, msg)
    return

  # Start project
  cmd = '"%s" startproject "%s"' % (django_admin, site_name)
  if sys.platform == 'win32':
    pyexec = _get_pyexec_from_django_admin(django_admin)
    if pyexec is None:
      title = _("Could not read django-admin.py")
      msg = _("Could not open %s -- please check the path") % django_admin
      app.ShowMessageDialog(title, msg)
      return
    cmd = '"%s" %s' % (pyexec, cmd)
  err, output = app.ExecuteCommandLine(cmd, parent_directory, None, 10.0,
                                       return_stderr=True)
  if err != 0 or output[1]:
    title = _("Failed to Execute django-admin.py startproject")
    msg = _("The command '%s' failed with error code %i and the following output:\n\n%s") % \
        (cmd, err, _get_output(output))
    msg += _("\n\nWing may not be finding the right Python.  Please edit django-admin.py to set "
             "the correct path for Python after #! on the first line.")
    app.ShowMessageDialog(title, msg)
    return
  proj_dir = os.path.join(parent_directory, site_name)
  settings_py = os.path.join(proj_dir, 'settings.py')
  if not os.path.isfile(settings_py):
    title = _("Failed to Start Project")
    msg = _("The command '%s' failed to produce output: %s is missing.") % (cmd, settings_py)
    msg += _("\n\nWing may not be finding the right Python.  Please edit django-admin.py to set "
             "the correct path for Python after #! on the first line.")
    app.ShowMessageDialog(title, msg)
    return
  actions.append(_("site directory %s was created with django-admin.py startproject") % \
                 proj_dir)
  
  # Edit settings.py to add DATABASE_ENGINE and DATABASE_NAME fields
  # for sqlite3 default and add to INSTALLED_APPS
  try:
    f = open(settings_py)
    txt = f.read()
    f.close()
  except:
    errs.append(_("Could not read %s to set default settings") % settings_py)
  else:
    lines = txt.splitlines()
    eol = _get_eol(txt)
    app_insert_line = None
    db_engine_line = None
    db_name_line = None
    in_databases = False
    in_default = False
    databases_style = 'django1.1'
    for i in range(0, len(lines)):
      line = lines[i]
      if line.lstrip().startswith('INSTALLED_APPS'):
        app_insert_line = i
      elif line.lstrip().startswith('DATABASE_ENGINE'):
        db_engine_line = i
      elif line.lstrip().startswith('DATABASE_NAME'):
        db_name_line = i
      elif line.lstrip().startswith('DATABASES'):
        in_databases = True
        databases_style = 'django1.2'
      elif in_databases and line.lstrip().startswith("'default'"):
        in_default = True
      elif in_default and line.lstrip().startswith("'ENGINE'"):
        db_engine_line = i
      elif in_default and line.lstrip().startswith("'NAME'"):
        db_name_line = i
      elif in_default and line.strip().startswith('}'):
        in_default = False
      elif in_databases and line.strip().startswith('}'):
        in_databases = False
    if app_insert_line is not None:
      lines = lines[:app_insert_line+1] + ["    'django.contrib.admin',"] + lines[app_insert_line+1:]
    else:
      lines.extend(["INSTALLED_APPS = (", "    'django.contrib.admin',", ")"])
    db_name = os.path.join(proj_dir, site_name + '.db'),
    if db_engine_line is None or db_name_line is None:
      lines.extend[
        '', 
        "DATABASE_ENGINE='sqlite3'", 
        "DATABASE_NAME=r'%s'" % db_name,
        ''
      ]
    elif databases_style == 'django1.1':
      txt = lines[db_engine_line]
      lines[db_engine_line] = txt.replace("''", "'sqlite3'")
      txt = lines[db_name_line]
      lines[db_name_line] = txt.replace("''", "'%s'" % db_name)
    else:
      txt = lines[db_engine_line]
      lines[db_engine_line] = txt.replace("backends.'", "backends.sqlite3'")
      txt = lines[db_name_line]
      lines[db_name_line] = txt.replace("''", "'%s'" % db_name)
    txt = eol.join(lines)
    try:
      f = open(settings_py, 'w')
      f.write(txt)
      f.close()
    except:
      errs.append(_("Failed to write updated settings to %s") % settings_py)
    else:
      actions.append(_("database engine and name in settings.py were set to "
                       "use sqlite3 by default"))
      actions.append(_("django.contrib.admin was added to INSTALLED_APPS in settings.py"))
    
  # Run sync db
  if superuser:
    inp = "yes\n%s\n%s\n%s\n%s\n" % (superuser, superuser_email, superuser_password,
                                     superuser_password)
    inp_flag = ''
  else:
    inp = None
    inp_flag = '--noinput '
  cmd = '"%s" syncdb %s--settings="%s" --pythonpath="%s"' % (django_admin, inp_flag, 
                                                             '%s.settings' % site_name,
                                                             parent_directory)
  if sys.platform == 'win32':
    cmd = '"%s" %s' % (pyexec, cmd)
  err, output = app.ExecuteCommandLine(cmd, parent_directory, inp, 10.0,
                                       return_stderr=True)
  if output[1]:
    lines = output[1].rstrip().splitlines()
    if len(lines) == 2 and 'GetPassWarning' in lines[0] and 'fallback_getpass' in lines[1]:
      stderr_failure = False
    else:
      stderr_failure = True
  else:
    stderr_failure = False
  if err != 0 or stderr_failure:
    out = _get_output(output)
    if out:
      errs.append(_("The command %s exited with error code %i and output as follows:  %s") % \
                  (cmd, err, out))
    else:
      errs.append(_("The command %s exited with error code %i and no output") % \
                  (cmd, err))
  else:
    actions.append(_("django-admin.py syncdb was run"))
    
  # Copy in base_site.html
  pyexec = _get_pyexec_from_django_admin(django_admin)
  if pyexec is None:
    errs.append(_("Could not extract Python Executable from %s") % django_admin)
  else:
    cmd = '"%s" -c "import django; print(django.__file__)"' % pyexec
    err, output = app.ExecuteCommandLine(cmd, None, None, 10.0, return_stderr=True)
    if err != 0 or output[1]:
      errs.append(_("Could not execute %s to locate base_site.html:  Err=%i; %s") % \
                  (cmd, err, _get_output(output, separator='; ')))
    else:
      django_dir = os.path.dirname(output[0])
      base_html = os.path.join(django_dir, 'contrib', 'admin', 'templates', 
                               'admin', 'base_site.html')
      try:
        f = open(base_html)
        txt = f.read()
        f.close()
        target_html = os.path.join(parent_directory, site_name, 'templates', 'admin', 
                                   'base_site.html')
        from wingutils import build_utils
        build_utils.EnsureDirExists(target_html)
        f = open(target_html, 'w')
        f.write(txt)
        f.close()
      except:
        errs.append(_("Could not copy base_site.html into the project"))
      else:
        actions.append(_("the default admin template %s was copied into the project") % base_html)

  # Show confirmation of what was done so far and offer to set up new Wing project
  title = _("Created Django Project")
  msg = _("The Django project has been created.  ")
  if errs:
    msg += _get_errors_list(errs)
  msg += _get_actions_list(actions)
  msg += _("\n\nYou can now set up a new Wing IDE project if desired.")
  def new_completed():
    _store_dialog_fields(django_admin, parent_directory, superuser, superuser_email)
    proj = app.GetProject()
    proj.AddDirectory(proj_dir)
    def setup_project():
      app.ExecuteCommand('django-setup-wing-project')
    _CDjangoPluginActivator._instance._SetPendingAction(setup_project)
  def new_failed():
    title = _("Wing Project Setup Canceled")
    msg = _("Setting up a Wing project for your newly created Django site was canceled.  You "
            "can set one up manually later by creating a project, adding the Django site files, "
            "and choosing Configure Project for Django from the Django menu that will "
            "appear in the menu bar after the Django files have been added to the project.")
    app.ShowMessageDialog(title, msg, modal=False)
  def create_proj():
    app.NewProject(new_completed, new_failed)
  buttons = [
    (_("Create Wing Project"), create_proj),
    (_("Cancel"), new_failed)
  ]
  app.ShowMessageDialog(title, msg, buttons=buttons, modal=False)

django_start_project.contexts = _override_context
django_start_project.plugin_override = True
django_start_project.label = _("Start New Project")
django_start_project.flags = { 'force_dialog_argentry': True }

def _django_admin_default_gui():
  app = wingapi.gApplication
  proj = app.GetProject()
  try:
    default = proj.GetAttribute('django-admin')
  except KeyError:
    default = 'django-admin.py'
  return formbuilder.CFileSelectorGui(default=default)  
def _django_parent_dir_gui():
  settings_py, manage_py = _CDjangoPluginActivator._instance._FindKeyFiles()
  if settings_py is not None:
    default = os.path.dirname(os.path.dirname(settings_py))
  else:
    proj = wingapi.gApplication.GetProject()
    try:
      default = proj.GetAttribute('django-parent-directory')
    except KeyError:
      default = wingapi.gApplication.GetStartingDirectory()
  return formbuilder.CFileSelectorGui(default=default, want_dir=1)  
def _django_superuser_gui():
  proj = wingapi.gApplication.GetProject()
  try:
    default = proj.GetAttribute('django-superuser')
  except KeyError:
    default = 'admin'
  return formbuilder.CSmallTextGui(default=default)  
def _django_superuser_email_gui():
  proj = wingapi.gApplication.GetProject()
  try:
    default = proj.GetAttribute('django-superuser-email')
  except KeyError:
    default = ''
  return formbuilder.CSmallTextGui(default=default)  
django_start_project.arginfo = {
  'django_admin': wingapi.CArgInfo(
    _("Which django-admin.py and Django installation to use for the new project. "
      "Use the default if the desired django-admin.py is on your PATH."),
    datatype.CType(''), _django_admin_default_gui),
  'parent_directory': wingapi.CArgInfo(
    _("The parent directory into which the new project's site directory "
      "should be written."), 
    datatype.CType(''), _django_parent_dir_gui),
  'site_name': wingapi.CArgInfo(
    _("The Django site name for the new project."), 
    datatype.CType(''), formbuilder.CSmallTextGui()),
  'superuser': wingapi.CArgInfo(
    _("The superuser account name (blank to skip creating account)"),
    datatype.CType(''), _django_superuser_gui),
  'superuser_email': wingapi.CArgInfo(
    _("The superuser account's email address (ignored when not creating account)"),
    datatype.CType(''), _django_superuser_email_gui),
  'superuser_password': wingapi.CArgInfo(
    _("The superuser account password (ignored when not creating account)"),
    datatype.CType(''), formbuilder.CSmallTextGui()),
}

def django_setup_wing_project():
  """Sets up a Wing project to work with an existing Django project. This
  assumes that you have already added files to the project so that your
  manage.py and settings.py files are in the project. It sets up the Python
  Executable project property, sets "manage.py runserver --noreload 8000" as
  the main debug file, sets up the Wing project environment by defining
  DJANGO_SITENAME and DJANGO_SETTINGS_MODULE, adds the site directory to the
  Python Path in the Wing project, sets TEMPLATE_DEBUG = True in the
  settings.py file, ensures that the Template Debugging project property
  is enabled, sets up the unit testing framework and file patterns in
  project properties."""

  actions = []
  errs = []
  
  app = wingapi.gApplication
  manage_py, settings_py = _CDjangoPluginActivator._instance._FindKeyFiles()
  if manage_py is None:
    title = _("Django Files Not Found")
    msg = _("Please add your Django project directory to your Wing IDE Project then "
            "try again.  This command requires that the files manage.py and settings.py "
            "can be found in the project.")
    app.ShowMessageDialog(title, msg)
    return
  
  # Set up Python Executable
  proj = app.GetProject()
  try:
    django_admin = proj.GetAttribute('django-admin')
  except KeyError:
    errs.append(_("Could not determine which Python Executable to use in Project Properties. "
                  "Set this manually if the default Python "
                  "is not the one being used with Django."))
  else:
    pyexec = _get_pyexec_from_django_admin(django_admin)
    if pyexec is None:
      errs.append(_("Could not obtain Python Executable to use in Project Properties from "
                    "%s. Set this manually if the default Python "
                    "is not the one being used with Django.") % django_admin)
    else:
      proj.SetPythonExecutable(None, pyexec)
      actions.append(_("%s was set as the Python Executable in Project Properties") % pyexec)
  
  # Set up main debug file and its run arguments
  proj.SetMainDebugFile(manage_py)
  runargs = 'runserver --noreload 8000'
  proj.SetRunArguments(manage_py, runargs)
  actions.append(_("%s was set as main debug file with run arguments "
                   "%s") % (manage_py, runargs))
  
  # Set up environment project-wide
  env = proj.GetEnvironment(None, overrides_only=True).copy()
  proj_dir = _CDjangoPluginActivator._instance._GetDjangoProjectDir()
  env['DJANGO_SITENAME'] = os.path.basename(proj_dir)
  env['DJANGO_SETTINGS_MODULE'] = "${DJANGO_SITENAME}.settings"
  
  # Add site directory and enclosing directory to python path if not already 
  # in there.  Note that by default Django has only the site directory on
  # the path and seems to use import magic for "from sitename.models import *"
  pypath = env.get('PYTHONPATH', None)
  if pypath is not None:
    pypath = pypath.split(os.pathsep)
  else:
    pypath = []
  if not os.path.dirname(proj_dir) in pypath:
    pypath.append(os.path.dirname(proj_dir))
  if not proj_dir in pypath:
    pypath.append(proj_dir)
  pypath = os.pathsep.join(pypath)
  env['PYTHONPATH'] = pypath
  
  # Set both env and pypath into project properties
  proj.SetEnvironment(None, 'startup', env)
  actions.append(_("DJANGO_SITENAME and DJANGO_SETTINGS_MODULE "
                   "environment variables were added to the project-wide environment"))
  actions.append(_("added directories %s and %s to the Python Path in Project Properties") % (os.path.dirname(proj_dir), proj_dir))
  
  # Make sure that template debugging is enabled in settings file
  try:
    f = open(settings_py)
    txt = f.read()
    f.close()
  except:
    errs.append(_("Failed to read %s to modify TEMPLATE_DEBUG setting") % settings_py)
  else:
    changed = False
    found = False
    lines = txt.splitlines()
    eol = _get_eol(txt)
    for i in range(0, len(lines)):
      if lines[i].strip().startswith('TEMPLATE_DEBUG'):
        words = lines[i].split()
        if len(words) > 2 and words[1] == '=':
          found = True
          if words[2] not in ('1', 'True'):
            leading = lines[i][:lines[i].find('TEMPLATE_DEBUG')]
            lines[i] = '#' + lines[i]
            lines.insert(i+1, leading + 'TEMPLATE_DEBUG = True')
            changed = True
            break
    if not found:
      lines.extend(['', 'TEMPLATE_DEBUG = True', ''])
      changed = True
    if changed:
      try:
        f = open(settings_py, 'w')
        txt = eol.join(lines)
        f.write(txt)
        f.close()
      except:
        errs.append(_("Failed to write %s with TEMPLATE_DEBUG enabled") % settings_py)
      else:
        actions.append(_("set TEMPLATE_DEBUG = True in the site's settings.py file so "
                         "Wing's debugger can debug templates"))
    
  # Make sure template debugging project property is enabled
  import proj.attribs
  value = app.fSingletons.fFileAttribMgr.GetValue(proj.attribs.kTemplateDebugging)
  if not value:
    app.fSingletons.fFileAttribMgr.SetValue(proj.attribs.kTemplateDebugging, True)
    actions.append(_("enabled Template Debugging in Project Properties"))

  # Set up unit testing in project properties
  import testing.attribs
  import testing.adaptors
  manage_loc = location.CreateFromName(manage_py)
  value = app.fSingletons.fFileAttribMgr.GetValue(testing.attribs.kTestFramework, manage_loc)
  if value != testing.adaptors.CDjangoTestAdaptor.internal_id:
    app.fSingletons.fFileAttribMgr.SetValue(testing.attribs.kTestFramework, manage_loc,
                                            testing.adaptors.CDjangoTestAdaptor.internal_id)
    cmd = 'add-testing-files(locs="%s")' % manage_py
    app.ExecuteCommand(cmd)
    actions.append(_("configured unit testing for Django"))

  # Show confirmation to user
  title = _("Django Configuration Complete")
  msg = _("The project file has been configured for Django.  ")
  if errs:
    msg += _get_errors_list(errs)
  msg += _get_actions_list(actions)
  app.ShowMessageDialog(title, msg, modal=False)
  
django_setup_wing_project.contexts = _override_context
django_setup_wing_project.plugin_override = True
django_setup_wing_project.label = _("Configure Project for Django")

def _get_base_cmdline():
  app = wingapi.gApplication
  manage_py, settings_py = _CDjangoPluginActivator._instance._FindKeyFiles()
  if manage_py is None:
    return None, None, _("Could not find manage.py and/or settings.py in the project")
  project = wingapi.gApplication.GetProject()
  py = project.GetPythonExecutable(None)
  if py is None:
    py = wingapi.gApplication.FindPython()
  if py is None:
    return None, None, _("Could not find Python.  Please set Python Executable in Project Properties, accessed from the Project menu")
  return [py, manage_py], os.path.dirname(manage_py), None
  
def django_start_app(appname):
  """Start a new application within the current Django project and add it to the 
  INSTALLED_APPS list in the project's settings.py file."""
  
  actions = []
  errs = []
  
  app = wingapi.gApplication
  cmdline, dirname, err = _get_base_cmdline()
  if err is not None:
    title = _("Failed to Start App")
    msg = _("The Django app could not be created:  %s") % err
    app.ShowMessageDialog(title, msg)
    return
  cmdline += ['startapp', appname]
  err, output = app.ExecuteCommandLine(cmdline, dirname, None, 5.0, return_stderr=True)
  if err != 0 or output[1]:
    title = _("Failed to Start App")
    msg = _("The command %s failed with error code %i and output:\n\n%s\n\n%s") % (cmdline, err, _get_output(output), _kMissingPythonMessage)
    app.ShowMessageDialog(title, msg)
    return
  actions.append(_("Created Django app %s in %s") % (appname, dirname))
  
  # Add the new app to INSTALLED_APPS in settings.py
  manage_py, settings_py = _CDjangoPluginActivator._instance._FindKeyFiles()
  try:
    f = open(settings_py)
    txt = f.read()
    f.close()
  except:
    errs.append(_("Unable to read %s to update INSTALLED_APPS"))
  else:
    lines = txt.splitlines()
    eol = _get_eol(txt)
    insert_line = None
    in_installed_apps = False
    for i, line in enumerate(lines):
      if line.lstrip().startswith('INSTALLED_APPS'):
        in_installed_apps = True
      elif in_installed_apps and line.strip().startswith(')'):
        in_installed_apps = False
        insert_line = i
    if insert_line is None:
      lines.extend(['', 'INSTALLED_APPS =', "    '%s'," % appname, ')', ''])
    else:
      lines = lines[:insert_line] + ["    '%s'," % appname] + lines[insert_line:]
    try:
      txt = eol.join(lines)
      f = open(settings_py, 'w')
      f.write(txt)
      f.close()
    except:
      errs.append(_("Unable to write %s to update INSTALLED_APPS"))
    else:
      actions.append(_("Added %s to INSTALLED_APPS in %s") % (appname, settings_py))
  
  title = _("The App was Created")
  msg = _("The application was created.  ")
  if errs:
    msg += _get_errors_list(errs)
  msg += _get_actions_list(actions)
  app.ShowMessageDialog(title, msg, modal=False)

django_start_app.contexts = [wingapi.kContextNewMenu(_("Djang_o"), group=2)]
django_start_app.label = _("Start New Application")
django_start_app.flags = { 'force_dialog_argentry': True }

def django_sync_db():
  """Run manage.py syncdb"""
  app = wingapi.gApplication
  cmdline, dirname, err = _get_base_cmdline()
  if err is not None:
    title = _("Failed to Sync DB")
    msg = _("Could not sync db:  %s") % err
    app.ShowMessageDialog(title, msg)
    return
  cmdline += ['syncdb', '--noinput']
  handler = app.AsyncExecuteCommandLine(cmdline[0], dirname, *cmdline[1:])
  timeout = time.time() + 120
  def poll(timeout=timeout):
    kill = time.time() > timeout
    if kill or handler.Iterate():
      stdout, stderr, err, status = handler.Terminate(kill)
      if kill:
        msg = _("Could not sync the database: Sub-process timed out")
      elif err is not None:
        msg = _("Could not sync the database: Sub-process failed with exit_status=%s, errno=%s") % (str(status), str(err))
      else:
        msg = _("Sync DB completed")
      if stderr:
        msg += '\n\n' + stderr + '\n\n' + _kMissingPythonMessage
      if stdout:
        msg += '\n\n' + stdout
      if msg == _("Sync DB completed"):
        title = msg
        msg = _("Sync DB completed with no errors or output")
        app.ShowMessageDialog(title, msg)
      else:
        editor = app.ScratchEditor(_("Django Sync DB"), 'text/plain')
        doc = editor.GetDocument()
        doc.SetText(msg)
      return False
    else:
      # XXX Would be nice; need to use pexpect to make this work, however
      #out = ''.join(handler.stdout).lower()
      #if out.find('auth system') > 0 and out.rstrip().endswith('(yes/no):'):
        #title = _("Create Superuser Account?")
        #msg = _("You have just enabled Django's auth system.  Do you want to create a "
                #"superuser account now?")
        #def create_acct():
          #def collect_args(superuser, superuser_email, superuser_password):
            #handler.pipes.tochild.write('yes\n%s\n%s\n%s\n%s\n' % (superuser, superuser_email,
                                                                   #superuser_password, 
                                                                   #superuser_password))
            #app.fSingletons.fCmdMgr.Execute(collect_args)
        #def dont_create_acct():
          #handler.pipes.tochild.write('no\n')
        #app.ShowMessageDialog(title, msg, buttons=[("Yes", create_acct),
                                                   #("No", dont_create_acct)])        
      return True
    
  wingapi.gApplication.InstallTimeout(100, poll)
  
django_sync_db.contexts = [wingapi.kContextNewMenu(_("Djang_o"), group=1)]
django_sync_db.label = _("Sync Database")

def django_run_tests():
  """Run manage.py unit tests in the Testing tool"""
  
  settings_py, manage_py = _CDjangoPluginActivator._instance._FindKeyFiles()
  loc = location.CreateFromName(settings_py)
  cmd = 'run_test_files(locs="%s")' % settings_py
  wingapi.gApplication.ExecuteCommand(cmd)
  
django_run_tests.contexts = [wingapi.kContextNewMenu(_("Djang_o"), group=1)]
django_run_tests.label = _("Run Unit Tests")

def django_run_tests_to_scratch_buffer():
  """Run manage.py tests with output in a scratch buffer"""
  
  app = wingapi.gApplication
  cmdline, dirname, err = _get_base_cmdline()
  if err is not None:
    title = _("Failed to run Django unit tests")
    msg = _("Could not run Django :  %s") % err
    app.ShowMessageDialog(title, msg)
    return
  cmdline += ['test']
  editor = app.ScratchEditor(_("Django Unit Tests"), 'text/plain')
  doc = editor.GetDocument()
  doc.SetText(_('Starting Django Unit Tests at %s:\n') % time.ctime())

  handler = app.AsyncExecuteCommandLine(cmdline[0], dirname, *cmdline[1:])
  timeout = time.time() + 120
  def poll(timeout=timeout):
    kill = time.time() > timeout
    if kill or handler.Iterate():
      stdout, stderr, err, status = handler.Terminate(kill)
      if kill:
        msg = _("Could not run Django unit tests: Sub-process timed out")
      elif err is not None:
        msg = _("Could not run Django unit tests: Sub-process failed with exit_status=%s, errno=%s") % (str(status), str(err))
      else:
        msg = _("Django unit tests passed successfully")
      if stderr:
        msg += '\n\nSTDERR:\n\n' + stderr
        msg += '\n\n' + _kMissingPythonMessage
      if stdout:
        msg += '\n\nSTDOUT:\n\n' + stdout
      if msg == _("Django unit tests passed successfully"):
        title = msg
        msg = _("Django unit tests passed successfully with no output")
        app.ShowMessageDialog(title, msg)
      else:
        editor = app.ScratchEditor(_("Django Unit Tests"), 'text/plain')
        doc = editor.GetDocument()
        doc.InsertChars(doc.GetLength(), msg)
      return False
    else:
      editor = app.ScratchEditor(_("Django Unit Tests"), 'text/plain')
      doc = editor.GetDocument()
      doc.InsertChars(doc.GetLength(), ''.join(handler.stderr))
      handler.stderr = []
      return True
    
  wingapi.gApplication.InstallTimeout(100, poll)

def django_sql(appname):
  """Run manage.py sql for given app name and display the output in a
  scratch buffer."""
  app = wingapi.gApplication
  cmdline, dirname, err = _get_base_cmdline()
  if err is not None:
    title = _("Failed to Generate SQL")
    msg = _("Could not generate SQL:  %s") % err
    app.ShowMessageDialog(title, msg)
    return
  cmdline += ['sql', appname]
  err, output = app.ExecuteCommandLine(cmdline, dirname, None, 5.0, return_stderr=True)
  if err != 0:
    if err == 1:
      reason = _("Failed to start sub-process")
    else:
      reason = _("Sub-process timed out")
    title = _("Failed to Generate SQL")
    msg = _("Could not generate SQL: %s") % reason
    out = _get_output(output)
    if out:
      msg += '\n\n' + out
    app.ShowMessageDialog(title, msg)
  else:
    editor = app.ScratchEditor(_("Django SQL"), 'text/x-sql')
    doc = editor.GetDocument()
    doc.SetText(_get_output(output, pfx=('', ''), verbose=1))

django_sql.contexts = [wingapi.kContextNewMenu(_("Djang_o"), group=1)]
django_sql.label = _("Generate SQL")
django_sql.arginfo = {
  'appname': wingapi.CArgInfo(_("Django App Name"), datatype.CType(''),
                              _appname_formlet)
}
django_sql.flags = { 'force_dialog_argentry': True }

def _django_sql_avail():
  apps = _CDjangoPluginActivator._instance._GetDjangoAppDirs()
  return len(apps) > 0
django_sql.available = _django_sql_avail

def django_validate():
  """Run manage.py validate"""
  app = wingapi.gApplication
  cmdline, dirname, err = _get_base_cmdline()
  if err is not None:
    title = _("Failed to Validate")
    msg = _("Could not validate:  %s") % err
    app.ShowMessageDialog(title, msg)
    return
  cmdline += ['validate']
  err, output = app.ExecuteCommandLine(cmdline, dirname, None, 5.0, return_stderr=True)
  if err != 0:
    if err == 1:
      reason = _("Failed to start sub-process")
    else:
      reason = _("Sub-process timed out")
    title = _("Could Not Validate")
    msg = _("Could not validate: %s") % reason
    out = _get_output(output)
    if out:
      msg += '\n\n' + out
    app.ShowMessageDialog(title, msg)
  elif output[0].find('0 errors') == 0:
    app.ShowMessageDialog(_("Validate Succeeded"), _("Validated with 0 errors found"))
  else:
    editor = app.ScratchEditor(_("Django Validate"))
    doc = editor.GetDocument()
    doc.SetText(_get_output(output, pfx=('', ''), verbose=1))
    
django_validate.contexts = [wingapi.kContextNewMenu(_("Djang_o"), group=1)]
django_validate.label = _("Validate")

def django_show_docs():
  """Show documentation for using Wing IDE and Django together"""
  app = wingapi.gApplication
  app.ExecuteCommand('show-document', section="howtos/django")
  
django_show_docs.contexts = [wingapi.kContextNewMenu(_("Djang_o"), group=3)]
django_show_docs.label = _("Show Documentation")

def django_restart_shell():
  """Show and restart the Python Shell tool, which works in the same
  environment as "manage.py shell".  To show the tool without restarting
  it, use the Tools menu."""
  
  singles = wingapi.gApplication.fSingletons
  shell = singles.fGuiMgr.ShowPanel('python-shell', flash=True, grab_focus=True)
  if shell is not None:
    shell.fOwner.ScheduleRestart()
  
django_restart_shell.contexts = [wingapi.kContextNewMenu(_("Djang_o"), group=1)]
django_restart_shell.label = _("Restart Shell")


#########################################################################
# Support code and setup auto-activation of this script as a plugin
# for Django projects

class _CDjangoPluginActivator:
  """Tracks whether the Django plugin should be enabled or not. Install
  signals so plugin can activate or deactivate based on what project is open
  and what it contains."""

  _instance = None
  if 0:
    isinstance(_instance, _CDjangoPluginActivator)
  
  def __init__(self, plugin_id):

    self.plugin_id = plugin_id
    self._timeout_id = None
    self._project_connections = []
    self.__fCachedFiles = None
    self.__fPendingAction = None

    app = wingapi.gApplication
    app.Connect('project-open', self.__CB_ProjectOpen)
    self.ConnectToProject()
        
  def ConnectToProject(self):
    """Connect to signals on project so plugin can enable when appropriate"""
    
    # Remove old connections
    for proj, signal in self._project_connections:
      if not proj.destroyed():
        proj.Disconnect(signal)
    self._project_connections = []
      
    # Connect to new project
    app = wingapi.gApplication
    proj = app.GetProject()
    self._project_connections.append((proj, proj.Connect('files-added', self.__CB_ProjectChanged, proj)))
    self._project_connections.append((proj, proj.Connect('files-removed', self.__CB_ProjectChanged, proj)))
    
    self.ScheduleUpdate()
    
  def __CB_ProjectOpen(self, *args):
    """Current project has changed"""
    
    self.ConnectToProject()

  def __CB_ProjectChanged(self, files):
    """Project contents have changed (given files were added or removed)"""
    
    for fn in files:
      if fn.endswith('settings.py') or fn.endswith('manage.py'):
        self.ScheduleUpdate()
        return
      
  def ScheduleUpdate(self):
    """Avoid constant scanning of project during file discovery"""
    self.__fCachedFiles = None
    if self._timeout_id is not None:
      return
    app = wingapi.gApplication
    self._timeout_id = app.InstallTimeout(1000, self.__CB_DoUpdate)
    
  def __CB_DoUpdate(self):
    app = wingapi.gApplication
    is_django = self._IsDjangoProject()
    app.EnablePlugin(self.plugin_id, is_django)  
    if is_django and callable(self.__fPendingAction):
      action =  self.__fPendingAction
      self.__fPendingAction = None
      action()
    self._timeout_id = None
    return 0

  def _FindKeyFiles(self):
    """Try to find key Django project files in the project.  Returns full path
    to manage.py and settings.py or (None, None) if not found."""
    
    if self.__fCachedFiles is not None:
      return self.__fCachedFiles
    
    app = wingapi.gApplication
    proj = app.GetProject()
    files = proj.GetAllFiles()
    manage_files = []
    settings_files = []
    for fn in files:
      if os.path.basename(fn) == 'manage.py' and not os.path.dirname(fn).endswith('project_template') and os.path.isfile(fn):
        manage_files.append(fn)
      elif os.path.basename(fn) == 'settings.py' and not os.path.dirname(fn).endswith('project_template') and os.path.isfile(fn):
        settings_files.append(fn)

    pairs = []
    for manage_file in manage_files:
      for settings_file in settings_files:
        manage_dir = os.path.dirname(manage_file)
        settings_dir = os.path.dirname(settings_file)
        if manage_dir == settings_dir:
          pairs.append((manage_file, settings_file))
    if len(pairs) > 1:
      app.SetStatusMessage("Warning: Multiple manage.py/settings.py pairs found in project")
    
    if len(pairs) > 0:
      self.__fCachedFiles = pairs[0]
    else:
      self.__fCachedFiles = (None, None)
      
    return self.__fCachedFiles
  
  def _GetDjangoProjectDir(self):
    """Get the full path to the project directory.  The site-name is
    os.path.basename() fo the path."""
    
    manage_file, settings_file = self._FindKeyFiles()
    if manage_file is None:
      return None
    else:
      return os.path.dirname(manage_file)
  
  def _GetDjangoAppDirs(self):
    """Get a list of the app directories in the current project. Returns a
    list of the full path to the app directory. The app name is
    os.path.basename() of each path."""
    
    manage_file, settings_file = self._FindKeyFiles()
    if manage_file is None:
      return None

    dirname = os.path.dirname(manage_file)
    files = os.listdir(dirname)
    appnames = []
    for fn in files:
      dn = os.path.join(dirname, fn)
      if os.path.isdir(dn) and os.path.isfile(os.path.join(dn, 'models.py')) and \
         os.path.isfile(os.path.join(dn, 'views.py')):
        appnames.append(dn)
        
    return appnames
  
  def _IsDjangoProject(self):
    """Try to detect if this is a Django project, based on its contents"""
    
    manage_file, settings_file = self._FindKeyFiles()
    if manage_file is None or settings_file is None:
      return False
    
    return True
  
  def _SetPendingAction(self, cb):
    """Set a callback to invoke when project files have been added so
    that _IsDjangoProject returns true.  Used in bootstrapping a new
    Django project."""
    
    self.__fPendingAction = cb

# This sets this script up as a plugin and sets up determination of when the
# plugin is enabled. Note that users can disable plugins globally or at the
# project level to override the return value of this call.
def _django_activator(plugin_id):
  """Plugin activator for Django.  Note this must call CAPIApplication.EnablePlugin()
  and return True to enable or False to disable initially"""
  _CDjangoPluginActivator._instance = _CDjangoPluginActivator(plugin_id)
  is_django = _CDjangoPluginActivator._instance._IsDjangoProject()
  wingapi.gApplication.EnablePlugin(plugin_id, is_django)
  return is_django

_plugin = (_("Django Extensions"), _django_activator)


