""" This is an example script file that illustrates the features available
for extension authors.  It is normally disabled entirely and not loaded
into Wing IDE, but illustrates all of the usage cases the script manager
supports.  For real, working, useful examples of scripts see the other
files in this directory.

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

# Scripts can safely import from the following sub-systems:
# 
#  - Any Python 2.2 standard library module
#  - wingapi, the formal API to IDE functionality
# 
# Also available but subject to change:
#
#  - wingutils, useful low level utilities
#  - guiutils, for common dialogs and building GUI elements
#  - all other modules in the IDE
# 
# Scripts that reach beyond the documented API should check the 
# values returned by wingapi.gApplication.GetProductInfo() to 
# determine when running under a potentially unsupported
# version of Wing.
# 
# In general, writing more complex scripts requires running Wing
# from sources, so that it can be debugged with itself.

import wingapi

import os
import sys
from wingutils import datatype
from guiutils import formbuilder
from guiutils import dialogs
from guimgr import messages

# This causes Wing to ignore this script file entirely -- it just
# illustrates usage and the scripts themselves don't do anything
_ignore_scripts = 1

# Scripts can be internationalized and localized with gettext.  Strings 
# to be translated are sent to _() as in the code below.
import gettext
_ = gettext.translation('scripts_example', fallback = 1).ugettext
# This special attribute is used so that the script manager can translate
# also docstrings for the commands found here
_i18n_module = 'scripts_example'

# Recommended for readability
_AI = wingapi.CArgInfo

# Raising an exception at the top level prevents this module from being
# loaded at all
version, build, code, name, date = wingapi.gApplication.GetProductInfo()
if code < 0x00000002:
  print _("Module doesn't work in Wing IDE Personal")
  raise NotImplementedError

# These top-level attributes are used as defaults if they are omitted
# in the command definitions below.  The values in this example are
# the same as the internal defaults that are used if these top-level
# attributes are also omitted.
_arginfo = {}
_arginfo['filename'] = _AI(_("File or directory"),
                           datatype.CType(''), 
                           formbuilder.CFileSelectorGui(),
                           label=_("Update"))
_available = lambda: 1
_contexts = lambda: [wingapi.kContextNewMenu(_("Scripts")),]


#########################################################################  
# Commands
#########################################################################  

#-----------------------------------------------------------------------

# This is the command itself. Special args are indicated by using the
# constants from wingapi (such as kFilename here). For all other args, if
# no default arg values are given, Wing will automatically try to collect
# the arg values from the user. If any one arg is missing a value, all
# args will be included in the form presented to the user, with the
# omission only of args with valid special values.
# Note: Commands don't support * or ** args or nested lists in args.
def cvs_update(filenames=wingapi.kArgFilename):
  """ Update the given file or directory from CVS.  Returns the
  output of the CVS command. """

  for filename in filenames:

    if os.path.isdir(filename):
      dirname = filename
      cmd = 'cvs update'
    else:
      dirname = os.path.dirname(filename)
      cmd = 'cvs update %s' % os.path.basename(filename)
  
    #result = __run_in_dir(cmd, dirname)
    print cmd
  
# This gives additional data for the function args. If no meta data is
# given, the default is to assume args are short strings (except any
# special name args). Each dict key must correspond with an arg name and
# each entry is a wingapi.CArgInfo instance or a callable that returns a
# wingapi.CArgInfo instance.  The arginfo attrib as a whole may also be
# a callable that returns the dict.
cvs_update.arginfo = {}
cvs_update.arginfo['filenames'] = _AI(_("File or directory to update"), 
                                      datatype.CType(''), 
                                      formbuilder.CFileSelectorGui(),
                                      label=_("_Update"))

# Determines when the command is available for invocation. If omitted,
# the command is always available.  May also be set to a constant value.
def _cvs_update_available(filename=wingapi.kArgFilename):
  return filename is not None
cvs_update.available = _cvs_update_available
cvs_update.label = 'Update'

# Flags that affect how this command is made available in Wing's user
# interface.  When omitted, the command is only available by name from the
# master command list and the keyboard navigator (which includes all
# commands by default)
cvs_update.contexts = [wingapi.kContextEditor(), 
                       wingapi.kContextProject(),
                       wingapi.kContextNewMenu(_("_CVS"))]

#-----------------------------------------------------------------------

def test(filename, comment=_("None")):
  print _("Testing!")
  print _("Filename"), filename
  print _("Comment"), comment

  buttons = (dialogs.CButtonSpec(_('OK'), None),)
  dlg = messages.CMessageDialog(wingapi.gApplication.fSingletons, _("Test result"), 
                               _("File %s: %s") % (filename, comment), [], buttons)

# Note that arginfo can also be a callable that returns the arg info
# (useful if the info changes at runtime; tho it doesn't in this example)
def _test_arginfo(app=wingapi.kArgApplication):
  arginfo = {'filename': _AI(_("File or directory to test"), datatype.CType(''), 
                             formbuilder.CFileSelectorGui()),
             'comment': _AI(_("Comment for this test"), datatype.CType(''), 
                            formbuilder.CLargeTextGui())}
  return arginfo
test.arginfo = _test_arginfo

test.label = _("Test Command")
test.contexts = [wingapi.kContextNewMenu(_("Scripts"), 1),]

#-----------------------------------------------------------------------

def ctest(filename, comment=_("None")):
  print _("CTesting!")
  print _("CFilename"), filename
  print _("CComment"), comment

  buttons = (dialogs.CButtonSpec(_("OK"), None),)
  dlg = messages.CMessageDialog(wingapi.gApplication.fSingletons, _("CTest result"), 
                               _("CFile %s: %s") % (filename, comment), [], buttons)

# Note that arginfo can also be a callable that returns the arg info
# (useful if the info changes at runtime; tho it doesn't in this example)
def _ctest_arginfo(app=wingapi.kArgApplication):
  def x():
    return _("File or directory to ctest")
  def y():
    return datatype.CType('')
  def z():
    return _AI(lambda: _("Comment for this ctest"), y, 
               lambda: formbuilder.CLargeTextGui())
  arginfo = {'filename': _AI(x, lambda: datatype.CType(''), 
                             lambda: formbuilder.CFileSelectorGui(), label=x),
             'comment': z,}
  return arginfo
ctest.arginfo = _ctest_arginfo

ctest.label = lambda: _("Test Command with Callables")
ctest.contexts = lambda: [wingapi.kContextNewMenu(_("Scripts"), 1),]

ctest.available = lambda: 1
ctest.doc = lambda: _("This is the doc string via callable")


#-----------------------------------------------------------------------
def idle():
  print _("Idling around Wing IDE")
  return 1


#########################################################################  
# Utilities
#########################################################################  

def __run_in_dir(cmd, dirname = None):
  """ Run the cmd in given directory. """
  
  if dirname != None:
    curr_dir = os.getcwd()
    os.chdir(dirname)
    
  output = os.popen(cmd)

  if dirname != None:
    os.chdir(curr_dir)

  result = output.readlines()
  output.close()
  
  return result


#########################################################################  
# Initialization
#########################################################################  

# Example:  Install a script to be called every five seconds
app = wingapi.gApplication
app.InstallTimeout(5000, idle)
