from JumpScale import j
from ExecutorBase import ExecutorBase


class ExecutorLocal(ExecutorBase):

    def __init__(self, dest_prefixes={}, debug=False, checkok=False):
        ExecutorBase.__init__(
            self, dest_prefixes=dest_prefixes, debug=debug, checkok=debug)
        self.logger = j.logger.get("j.tools.executor.local")
        self.type="local"
        self.id = 'localhost'
        self.addr = 'localhost'

    def execute(self, cmds, die=True, checkok=None, async=False,showout=True, combinestdr=True,timeout=0, env={}):
        if env:
            self.env.update(env)
        # cmds = self._transformCmds(cmds, die, checkok=checkok)
        if cmds.find('\n') == -1:
            if self.debug:
                print("EXECUTOR:%s"%cmds)
            return j.do.execute(cmds, die=die, async=async,showout=showout, outputStderr=showout)
        if self.debug:
            print("EXECUTOR:\n%s\n"%cmds)

        return j.sal.process.execute(command=cmds, die=die)

    def executeInteractive(self, cmds, die=True, checkok=None):
        cmds = self._transformCmds(cmds, die, checkok=checkok)
        return j.sal.process.executeWithoutPipe(cmds)

    def upload(self, source, dest, dest_prefix="", recursive=True):
        if dest_prefix != "":
            dest = j.sal.fs.joinPaths(dest_prefix, dest)
        j.sal.fs.copyDirTree(source, dest, keepsymlinks=True, deletefirst=False,
                      overwriteFiles=True, ignoredir=[".egg-info", ".dist-info"], ignorefiles=[".egg-info"], rsync=True,
                      ssh=False, recursive=recursive)

    def download(self, source, dest, source_prefix=""):
        if source_prefix != "":
            source = j.sal.fs.joinPaths(source_prefix, source)
        j.sal.fs.copyDirTree(source, dest, keepsymlinks=True, deletefirst=False,
                      overwriteFiles=True, ignoredir=[".egg-info", ".dist-info"], ignorefiles=[".egg-info"], rsync=True,
                      ssh=False)
