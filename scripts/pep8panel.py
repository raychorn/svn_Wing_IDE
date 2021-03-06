"""
PEP8 integration for Wing IDE.

Copyright (c) 2009 Stefan Tjarks <stefan@tjarks.de>

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

Version 0.1 (2009-10-8)

* First release

Version 0.2 (2009-10-8)

* Filter *.py files if a package is scanned
* Show only filenames on package scan
* Fixed wrong file path in panel. Jumping to line in file should work now.

Version 0.3 (2009-10-16)

* Add support for MS Windows.

Version 0.4 (2009-10-22)

* Optional autoload support. Saved file will be check automatically.

Version 0.4.1 (2010-02-23)

* Got my hands on a Windows 7 box. Adjusted the configuration section.
"""
# ------------------------------ CONFIGURATION -----------------------------------------------------
#
# Commands and arguments. Default set for *unix based systems. For Windows adjust as follow
#
#    PEP8_COMMAND = r"C:\Python26\python.exe"
#
# and add the pep8 script as the first argument in PEP8_ARGS
#
#    PEP_ARGS = [r"C:\Python26\Scripts\pep8-script.py", ...]
#

PEP8_COMMAND = 'J:/_utils/pep8/pep8.exe'
PEP8_ARGS = ['--repeat', '--statistics'] # add args but don't remove those two!
AUTORELOAD = False # Set to True to activate autoreloading

# ------------------------------ /CONFIGURATION ----------------------------------------------------

PEP08PANEL_VERSION = "0.4.1"

import os
import sys
import wingapi
import time
import re
_AI = wingapi.CArgInfo

# Scripts can be internationalized with gettext.    Strings to be translated
# are sent to _() as in the code below.
import gettext
_ = gettext.translation('scripts_pep8panel', fallback = 1).ugettext

# This special attribute is used so that the script manager can translate
# also docstrings for the commands found here
_i18n_module = 'scripts_pep8panel'

######################################################################
# Utilities

gMessageCategories = [
    ("errors", _("Errors"), _("Errors that must be fixed")),
    ("warnings", _("Warnings"), _("Warnings that could indicate problems")),
    ("statistics", _("Statistics"), _("Count errors and warnings")),
]

gTheView = None # Will be set later

######################################################################
# Configuration file support

kStatisticParseExpr = re.compile("(^[\d]+)\s+(.+$)")
kParseableResultParseExpr = re.compile("(^.+):(\d+):(\d+):\s*(.+$)")

######################################################################
# Commands

def pep8_execute():
    """Execute pep8 for the current editor"""
    filenames = _get_selected_python_files()
    _pep8_execute(filenames)


def _IsAvailable_pep8_execute():
    python_files = _get_selected_python_files()
    return len(python_files) > 0

pep8_execute.available = _IsAvailable_pep8_execute


def pep8_package_execute():
    """Execute pep8 on all files in the package to which the
    file in the current editor belongs"""

    packages = _get_selected_packages()
    _pep8_execute(packages)


def _IsAvailable_pep8_package_execute():
    packages = _get_selected_packages()
    return len(packages) > 0

pep8_package_execute.available = _IsAvailable_pep8_package_execute

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


def pep8_show_docs():
    """Show the Wing IDE documentation section for the PEP 8 integration"""
    wingapi.gApplication.ExecuteCommand('show-document', section='edit/pep8')


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
    print 'DEBUG: filenames=%s' % (filenames)
    if not filenames:
        return []
    python_files = []
    for filename in filenames:
        mimetype = _GetMimeType(filename)
        print 'DEBUG: mimetype=%s' % (mimetype)
        if (mimetype == 'text/x-python'):
            python_files.append(filename)
    return python_files


def _pep8_execute(filenames):
    if gTheView is None or not os.path.exists(PEP8_COMMAND):
        # Panel is not visible or PEP8 isn't available.
        return

    view = gTheView
    app = wingapi.gApplication

    is_dir = os.path.isdir(filenames[0])
    if is_dir and '--filename=*.py' not in PEP8_ARGS:
        PEP8_ARGS.append("--filename=*.py")

    # Guess at run directory
    rundir = os.path.dirname(filenames[0])
    if len(filenames) == 1:
        if os.path.isdir(filenames[0]):
            base_msg = _("Updating for package %s") % os.path.basename(filenames[0])
        else:
            base_msg = _("Updating for %s") % os.path.basename(filenames[0])
    else:
        base_msg = _("Updating for %i items") % len(filenames)

    # Completion routine that updates the tree when pep8 is finished running
    def _update_tree(result):
        resultLines = result.split('\n')
        tree_contents = [[], [], []]
        for line in resultLines:
            if 'win32' in sys.platform:
                parts = line.rsplit(':', 2)
            else:
                parts = line.split(':')
            # pep errors/warnings
            if len(parts) >= 3:
                matchobj = kParseableResultParseExpr.match(line)
                if matchobj is not None:
                    msg_descr = matchobj.group(4).strip()
                    msg_type = msg_descr[0]
                    line = os.path.basename(matchobj.group(2)).strip()
                    msg_filename = os.path.basename(matchobj.group(1).strip())
                    msg_line = msg_filename + ": " + line if is_dir else line
                    if msg_type == 'E':
                        msg_index = 0
                    else:
                        msg_index = 1
                    fullpath = matchobj.group(1).strip()
                    tree_contents[msg_index].append(
                        ((msg_line, msg_descr, fullpath, line), ))
            else:
                # statistic output
                matchobj = kStatisticParseExpr.match(line)
                if matchobj is not None:
                    msg_count = matchobj.group(1).strip()
                    msg_text = matchobj.group(2).strip()
                    tree_contents[2].append(
                        ((msg_count, msg_text, None, None), ))

        view.set_tree_contents(tree_contents)

    # Show pending execution message in tree column title
    view._ShowStatusMessage(base_msg)

    def arg_split(args, sep):
        cur_part = ''
        retval = []
        in_quote = None
        for c in args:
            if not in_quote:
                if c in '\'"':
                    in_quote = c
                    cur_part += c
                elif c == sep:
                    if cur_part:
                        retval.append(cur_part)
                    cur_part = ''
                else:
                    cur_part += c
            elif in_quote == c:
                in_quote = None
                cur_part += c
            else:
                cur_part += c
        if cur_part:
            retval.append(cur_part)
        return retval

    # Execute pep8 asyncronously
    cmd = PEP8_COMMAND
    args = []
    args.extend(arg_split(' '.join(PEP8_ARGS), ' '))
    import config
    for filename in filenames:
        args.append(filename.encode(config.kFileSystemEncoding))
    args = tuple(args)
    env = app.GetProject().GetEnvironment(filenames[0], set_pypath=True)
    start_time = time.time()
    timeout = 10
    handler = app.AsyncExecuteCommandLineE(cmd, rundir, env, *args)
    last_dot = [int(start_time)]
    dots = []

    def poll():
        if handler.Iterate():
            view._ShowStatusMessage('')
            stdout, stderr, err, status = handler.Terminate()
            if err:
                app.ShowMessageDialog(_("PEP8 Failed"), _("Error executing "\
                    "PEP8:    Command failed with error=%i; stderr:\n%s") % (err, stderr))
            else:
                #if len(stderr.strip()) > 0:
                    #print "pep8 stderr:\n", stderr.rstrip()
                #print "pep8 stdout:\n", stdout.rstrip()
                _update_tree(stdout)
            return False
        elif time.time() > start_time + timeout:
            view._ShowStatusMessage('')
            stdout, stderr, err, status = handler.Terminate()
            app.ShowMessageDialog(_("PEP8 Timed Out"), _("PEP8 timed out:    "\
                "Command did not complete within timeout of %i seconds.    "\
                "Right click on the PEP8 tool to configure this value.    "\
                "Output from PEP8:\n\n%s") % (timeout, stderr + stdout))
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


# Do an automatical run on document save.
def _connect_to_presave(doc):
    def _on_presave(filename, encoding):
        # Avoid operation when saving a copy to another location
        if filename is not None:
            return
        # Get editor and do action
        ed = wingapi.gApplication.OpenEditor(doc.GetFilename())
        if ed is not None:
            _pep8_execute([doc.GetFilename()])
    connect_id = doc.Connect('presave', _on_presave)

def _init():
    wingapi.gApplication.Connect('document-open', _connect_to_presave)
    for doc in wingapi.gApplication.GetOpenDocuments():
        _connect_to_presave(doc)

if AUTORELOAD:
    _init()


def _GetMimeType(filename):
    loc = location.CreateFromName(filename)
    return wingapi.gApplication.fSingletons.fFileAttribMgr.GetProbableMimeType(loc)

# Note that panel IDs must be globally unique so all user-provided panels
# MUST add a random uniquifier after '#'.    The panel can still be referred
# to by the portion of the name before '#' and Wing will warn when there
# are multiple panel definitions with the same base name (in which case
# Wing-defined panels win over user-defined panels and otherwise the
# last user-defined panel type wins when referred to w/o the uniquifier).
_kPanelID = 'pep8panel#02EFSTJK9X24'


class _CPep8PanelDefn(dockview.CPanelDefn):
    """Panel definition for the project manager"""

    def __init__(self, singletons):
        self.fSingletons = singletons
        dockview.CPanelDefn.__init__(self, self.fSingletons.fPanelMgr,
                                    _kPanelID, 'tall', 0)
        winmgr.CWindowConfig(self.fSingletons.fWinMgr, 'panel:%s' % _kPanelID,
                                                 size=(350, 1000))

    def _CreateView(self):
        return _CPep8View(self.fSingletons)

    def _GetLabel(self, panel_instance):
        """Get display label to use for the given panel instance"""

        return _('PEP 8')

    def _GetTitle(self, panel_instance):
        """Get full title for the given panel instance"""

        return _('PEP 8 Panel')


class _CPep8ViewCommands(commandmgr.CClassCommandMap):

    kDomain = 'user'
    kPackage = 'pep8panel'

    def __init__(self, singletons, view):
        commandmgr.CClassCommandMap.__init__(self, i18n_module=_i18n_module)
        assert isinstance(view, _CPep8View)

        self.fSingletons = singletons
        self.__fView = view


class _CPep8View(wingview.CViewController):
    """A single template manager view"""

    def __init__(self, singletons):
        """ Constructor """
        global gTheView

        # Init inherited
        wingview.CViewController.__init__(self, ())

        # External managers
        self.fSingletons = singletons

        self.__fCmdMap = _CPep8ViewCommands(self.fSingletons, self)

        self.fTrees = {}
        self.fLabels = {}

        self.__CreateGui()

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
            idx += 1

    ##########################################################################
    # Inherited calls from wingview.CViewController
    ##########################################################################

    def GetDisplayTitle(self):
        """ Returns the title of this view suitable for display. """

        return _("PEP 8 Panel")

    def GetCommandMap(self):
        """ Get the command map object for this view. """

        return self.__fCmdMap

    def BecomeActive(self):
        pass

    ##########################################################################
    # Popup menu and actions
    ##########################################################################

    def __CreateGui(self):
        notebook = wgtk.Notebook()

        for catkey, label, tooltip in gMessageCategories:
            tree = wgtk.SimpleTree([wgtk.gobject.TYPE_STRING] * 4,
                    [wgtk.CellRendererText(), wgtk.CellRendererText(),
                       wgtk.CellRendererText(), wgtk.CellRendererText()],
                    [_("Line"), _("Message"), _("Full Path"), _("Line Number")])
            tree.unset_flags(wgtk.CAN_FOCUS)
            tree.set_property('headers-visible', True)

            cols = tree.get_columns()
            cols[2].set_visible(False)
            cols[3].set_visible(False)

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

        # silly but convinent way to change title
        cols[0].set_title(_('Count'))

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
            (update_label, 'pep8-execute', {'uscoremagic': False}),
            (update_label2, 'pep8-package-execute', {'uscoremagic': False}),
            #None,
            #(_("Show PEP8 Tool Documentation"), 'pep8-show-docs'),
        ]

        # Create menu
        defnlist = guimgr.menus.GetMenuDefnList(kPopupDefn,
            self.fSingletons.fGuiMgr, self.__fCmdMap, is_popup=1, static=1)
        menu = guimgr.menus.CMenu(_("PEP8"), self.fSingletons.fGuiMgr,
                                        defnlist, can_tearoff=0, is_popup=1)
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
            filename = selected[0][2]
            line = int(selected[0][3])
            if event.button == 1 and event.type == wgtk.gdk.BUTTON_PRESS:
                doc = app.OpenEditor(filename)
                doc.ScrollToLine(lineno=line-1, pos='center', select=1)

    def __PopupMenu(self, event, pos):
        """Callback to display the popup menu"""

        menu = self.__CreatePopup()
        menu.Popup(event, pos=pos)

    def _ShowStatusMessage(self, msg):
        for tree, sview in self.fTrees.values():
            column = tree.get_column(1)
            if msg:
                column.set_title(_("Message: %s") % msg.replace('_', '__'))
            else:
                column.set_title(_("Message"))

# Register this panel type:    Note that this needs to be at the
# very end of the module so that all the classes defined here
# are already available
_CPep8PanelDefn(wingapi.gApplication.fSingletons)