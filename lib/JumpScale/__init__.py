
import sys
import os
import importlib
import importlib.machinery
import inspect

if sys.platform.startswith("darwin"):
    os.environ['JSBASE'] = '/Users/Shared/jumpscale/'
    if 'APPDATA' not in os.environ:
        os.environ['APPDATA'] = '/Users/Shared/jumpscale/var'
    if 'TMP' not in os.environ:
        os.environ['TMP'] = os.environ['TMPDIR'] + "jumpscale/"

    for p in ["/Users/Shared/jumpscale/lib", "/Users/Shared/jumpscale/lib/lib-dynload/", "/Users/Shared/jumpscale/bin", "/Users/Shared/jumpscale/lib/python.zip", "/Users/Shared/jumpscale/lib/plat-x86_64-linux-gnu"]:
        if p not in sys.path:
            sys.path.append(p)
    basevar = "/Users/Shared/jumpscalevar"

if 'VIRTUAL_ENV' in os.environ and 'JSBASE' not in os.environ:
    os.environ['JSBASE'] = os.environ['VIRTUAL_ENV']
    base = "/opt/jumpscale8"
    basevar = "/optvar"
elif 'JSBASE' in os.environ:
    base = os.environ['JSBASE']
    basevar = "/optvar"
else:
    base = "/opt/jumpscale8"
    basevar = "/optvar"

sys.path.insert(0, "/opt/jumpscale8/lib")


class Loader(object):

    def __init__(self, name, extrasname=None, module=None, extrasmodule=None):
        self.__doc__ = name
        self.__extrasdoc = extrasname if isinstance(extrasname, str) else extrasname.__package__
        self._module = module
        self._extrasmodule = extrasmodule
        if inspect.ismodule(module):
            self._file = inspect.getfile(module)
        else:
            self._file = None

        if inspect.ismodule(extrasmodule):
            self._extrasfile = inspect.getfile(extrasmodule)
        else:
            self._extrasfile = None

        if not self._file and not self._extrasfile:
            self._file = __file__
            self._extrasfile = extrasname.__file__ if extrasname else None

        self._dir = os.path.dirname(self._file) if self._file else None
        self._extrasdir = os.path.dirname(self._extrasfile) if self._extrasfile else None

    def __getattr__(self, attr):
        if self._module and hasattr(self._module, attr):
            return getattr(self._module, attr)
        elif self._extrasmodule and hasattr(self._extrasmodule, attr):
            return getattr(self._extrasmodule, attr)

        modulename = None
        extrasname = None
        module = None
        extrasmodule = None

        try:
            modulename = "%s.%s" % (self.__doc__, attr)
            module = importlib.import_module(modulename)
        except ImportError:
            pass

        try:
            extrasname = "%s.%s" % (self.__extrasdoc, attr)
            extrasmodule = importlib.import_module(extrasname)
        except ImportError:
            pass

        if not extrasmodule and not module:
            raise AttributeError("Could not load attr %s" % attr)
        attribute = Loader(modulename, extrasname, module, extrasmodule)
        setattr(self, attr, attribute)
        return attribute

    def __dir__(self):
        members = list()
        extramembers = list()
        if self._extrasmodule:
            extramembers += [x[0] for x in inspect.getmembers(self._extrasmodule, inspect.isfunction)]
        if self._module:
            members += [x[0] for x in inspect.getmembers(self._module, inspect.isfunction)]

        if not members and self._dir:
            for filename in os.listdir(self._dir):
                if os.path.isdir(os.path.join(self._dir, filename)):
                    members.append(filename)

        if not extramembers and self._extrasdir:
            for filename in os.listdir(self._extrasdir):
                if os.path.isdir(os.path.join(self._extrasdir, filename)):
                    extramembers.append(filename)
        members.extend(extramembers)
        return members

    def __str__(self):
        return "loader: %s" % self.__doc__

    __repr__ = __str__

locationbases = {}
import JumpScaleExtras
j = Loader(__package__, JumpScaleExtras)

from .InstallTools import InstallTools, Installer
j.do = InstallTools()
j.do.installer = Installer()

from .core.core.Application import Application
j.application = Application()

sys.path.append('/opt/jumpscale8/lib/JumpScale')
