from JumpScale import j


from ActionDecorator import ActionDecorator


"""
please ensure that the start and build methods are separate and
the build doesnt place anyfile outside opt as it will be used in aysfs mounted system
"""

class actionrun(ActionDecorator):
    def __init__(self, *args, **kwargs):
        ActionDecorator.__init__(self, *args, **kwargs)
        self.selfobjCode = "cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.apps.controller"


class Controller():

    def __init__(self, executor, cuisine):
        self.executor = executor
        self.cuisine = cuisine

    @actionrun(action=True)
    def build(self, start=True):
        """
        config: https://github.com/g8os/controller.git
        """
        #deps
        self.cuisine.apps.installdeps()
        self.cuisine.apps.redis.build(start=False)
        self.cuisine.apps.mongodb.build(start=False)
        self.cuisine.apps.syncthing.build(start=False)


        self.cuisine.processmanager.remove("agentcontroller8")
        pm = self.cuisine.processmanager.get("tmux")
        pm.stop("syncthing")

        self.cuisine.core.dir_ensure("$tmplsDir/cfg/controller", recursive=True)

        #get repo
        url = "github.com/g8os/controller"
        self.cuisine.golang.godep(url)

        sourcepath = "$goDir/src/github.com/g8os/controller"

        #do the actual building
        self.cuisine.core.run("cd %s && go build ." % sourcepath, profile=True)

        #move binary
        self.cuisine.core.file_move("%s/controller" % sourcepath, "$binDir/controller")



        #file copy
        self.cuisine.core.dir_remove("$tmplsDir/cfg/controller/extensions")
        self.cuisine.core.file_copy("%s/github/jumpscale/jumpscale_core8/apps/agentcontroller/jumpscripts/jumpscale" % self.cuisine.core.dir_paths["codeDir"], "$tmplsDir/cfg/controller/jumpscripts/", recursive=True)
        self.cuisine.core.file_copy("%s/extensions" % sourcepath, "$tmplsDir/cfg/controller/extensions", recursive=True)

        if start:
            self.start()

    def start(self):
        import re
        import hashlib
        import time
        self.cuisine.core.dir_ensure("$cfgDir/controller/")
        self.cuisine.core.file_copy("$tmplsDir/cfg/controller", "$cfgDir/", recursive=True)

        # edit config
        sourcepath = "$goDir/src/github.com/g8os/controller"
        C = self.cuisine.core.file_read("%s/agentcontroller.toml" % sourcepath)
        cfg = j.data.serializer.toml.loads(C)

        cfgDir = self.cuisine.core.dir_paths['cfgDir']
        cfg["events"]["python_path"] = self.cuisine.core.joinpaths(cfgDir, "/controller/extensions:/opt/jumpscale8/lib")
        cfg["processor"]["python_path"] = self.cuisine.core.joinpaths(cfgDir, "/controller/extensions:/opt/jumpscale8/lib")
        cfg["jumpscripts"]["python_path"] = self.cuisine.core.joinpaths(cfgDir, "/controller/extensions:/opt/jumpscale8/lib")
        cfg["jumpscripts"]["settings"]["jumpscripts_path"] = self.cuisine.core.joinpaths(cfgDir, "/controller/jumpscripts")
        C = j.data.serializer.toml.dumps(cfg)

        self.cuisine.core.file_write('$cfgDir/controller/agentcontroller.toml', C, replaceArgs=True)

        # expose syncthing and get api key
        sync_cfg = self.cuisine.core.file_read("$tmplsDir/cfg/syncthing/config.xml")
        sync_conn = re.search(r'<address>([0-9.]+):([0-9]+)</', sync_cfg)
        apikey = re.search(r'<apikey>([\w\-]+)</apikey>', sync_cfg).group(1)
        sync_cfg = sync_cfg.replace(sync_conn.group(1), "0.0.0.0")
        sync_cfg = sync_cfg.replace(sync_conn.group(2), "18384")
        self.cuisine.core.file_write("$cfgDir/syncthing/config.xml", sync_cfg)

        # add jumpscripts file
        self.cuisine.apps.syncthing.start()

        if not self.cuisine.core.executor.type == 'local':
            synccl = j.clients.syncthing.get(addr=self.executor.addr, sshport=self.executor.port, port=18384, apikey=apikey)
        else:
            synccl = j.clients.syncthing.get(addr="localhost", port=18384, apikey=apikey)

        jumpscripts_path = self.cuisine.core.args_replace("$cfgDir/controller/jumpscripts")
        timeout = 60
        start = time.time()
        syn_id = None
        while time.time() < (start + timeout) and syn_id is None:
            try:
                syn_id = synccl.id_get()
            except RuntimeError:
                print("restablishing connection to syncthing")

        if syn_id is None:
            raise RuntimeError('Syncthing is not responding. Exiting.')

        jumpscripts_id = "jumpscripts-%s" % hashlib.md5(syn_id.encode()).hexdigest()
        synccl.config_add_folder(jumpscripts_id, jumpscripts_path)

        # start
        self.cuisine.apps.mongodb.start()
        self.cuisine.apps.redis.start()
        env = {}
        env["TMPDIR"] = self.cuisine.core.dir_paths["tmpDir"]
        cmd = "$binDir/controller -c $cfgDir/controller/agentcontroller.toml"
        pm = self.cuisine.processmanager.get("tmux")
        pm.ensure("controller", cmd=cmd, path="$cfgDir/controller/", env=env)
