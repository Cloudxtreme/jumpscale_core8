from JumpScale import j

from JSLogger import JSLogger
from Filter import ModuleFilter

import logging
import logging.handlers
from colorlog import ColoredFormatter
import os


FILE_FORMAT = '%(asctime)s - %(pathname)s:%(lineno)d - %(levelname)-8s - %(message)s'
CONSOLE_FORMAT = '%(cyan)s[%(asctime)s]%(reset)s - %(pathname)30s:%(lineno)-4d - %(log_color)s%(levelname)-8s%(reset)s - %(message)s'

# Modes
PRODUCTION = 0  # use NullHander, let the application configure the logging
DEV = 10  # use predefine handlers for console and file.

_mode_to_name = {
    PRODUCTION: "PRODUCTION",
    DEV: "DEV"
}
_name_to_mode = {
    "PRODUCTION": PRODUCTION,
    "DEV": DEV
}

class LoggerFactory:

    def __init__(self):
        self.__jslocation__ = "j.logger"
        self.root_logger_name = 'j'
        self.handlers = {
            "console": self.__consoleHandler(),
            "file": self.__fileRotateHandler(),
        }

        # Modes
        self.PRODUCTION = PRODUCTION
        self.DEV = DEV

        self._logger = logging.getLogger(self.root_logger_name)
        self._logger.addHandler(logging.NullHandler())

    def init(self, mode, level, filter=[]):
        self.set_mode(mode.upper())
        self.set_level(level)
        if filter:
            self.handlers['console'].addFilter(ModuleFilter(filter))

    def get(self, name=None, enable_only_me=False):
        """
        Return a logger with the given name. Name will be prepend with 'j.' so
        every logger return by this function is a child of the jumpscale root logger 'j'

        Usage:
            self.logger = j.logger.get(__name__)
        in library module always pass __name__ as argument.
        """
        if not name:
            path, ln, name, info = logging.root.findCaller()
            if path.startswith(j.dirs.libDir):
                path = path.lstrip(j.dirs.libDir)
                name = path.replace(os.sep, '.')
        if not name.startswith(self.root_logger_name):
            name = "%s.%s" % (self.root_logger_name, name)
        logger = logging.getLogger(name)
        if enable_only_me:
            logger.enable_only_me()
        return logger

    def set_mode(self, mode):
        if j.data.types.string.check(mode):
            if mode in _name_to_mode:
                mode = _name_to_mode[mode]
            else:
                raise j.exceptions.Input("mode %s doesn't exist" % mode)

        if mode == self.PRODUCTION:
            self._enable_production_mode()
        elif mode == self.DEV:
            self._enable_dev_mode()

    def set_level(self, level):
        self.handlers['console'].setLevel(level)

    def log(self, msg=None, level=logging.INFO, category="j"):
        logger = j.logger.get(category)
        logger.log(level, msg)

    def _enable_production_mode(self):
        self._logger.handlers = []
        self._logger.addHandler(logging.NullHandler())
        self._logger.propagate = True

    def _enable_dev_mode(self):
        logging.setLoggerClass(JSLogger)
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        logging.lastResort = None
        for h in self.handlers.values():
            self._logger.addHandler(h)

    def __fileRotateHandler(self, name='jumpscale'):
        if not j.do.exists("%s/log/" % j.do.VARDIR):
            j.do.createDir("%s/log/" % j.do.VARDIR)
        filename = "%s/log/%s.log" % (j.do.VARDIR,name)
        formatter = logging.Formatter(FILE_FORMAT)
        fh = logging.handlers.TimedRotatingFileHandler(filename, when='D', interval=1, backupCount=7, encoding=None, delay=False, utc=False, atTime=None)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        return fh

    def __consoleHandler(self):
        formatter = LimitFormater(
            fmt=CONSOLE_FORMAT,
            datefmt="%a%d %H:%M",
            reset=True,
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'red,bg_white',
            },
            secondary_log_colors={},
            style='%',
            lenght=37
        )
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        return ch

    def __redisHandler(self, redis_client=None):
            if redis_client is None:
                self.redis_client = j.core.db


class LimitFormater(ColoredFormatter):
    def __init__(self, fmt, datefmt, reset, log_colors, secondary_log_colors, style, lenght):
        super(LimitFormater, self).__init__(
            fmt=fmt,
            datefmt=datefmt,
            reset=reset,
            log_colors=log_colors,
            secondary_log_colors=secondary_log_colors,
            style=style)
        self.lenght = lenght

    def format(self, record):
        if len(record.pathname) > self.lenght:
            record.pathname = "..." + record.pathname[-self.lenght:]
        return super(LimitFormater, self).format(record)
