from JumpScale import j


from ActionDecorator import ActionDecorator


"""
please ensure that the start and build methods are separate and
the build doesnt place anyfile outside opt as it will be used in aysfs mounted system
"""

class actionrun(ActionDecorator):
    def __init__(self, *args, **kwargs):
        ActionDecorator.__init__(self, *args, **kwargs)
        self.selfobjCode = "cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.apps.redis"


class Redis():
    
    def __init__(self, executor, cuisine):
        self.executor = executor
        self.cuisine = cuisine

    @actionrun(action=True)
    def build(self,name="main",ip="localhost", port=6379, maxram=200, appendonly=True,snapshot=False,slave=(),ismaster=False,passwd=None,unixsocket=True,start=True):
        self.cuisine.installer.base()
        if not self.cuisine.core.isMac:

            C="""
            #!/bin/bash
            set -ex

            # groupadd -r redis && useradd -r -g redis redis

            mkdir -p $tmpDir/build/redis
            cd $tmpDir/build/redis
            wget http://download.redis.io/releases/redis-3.0.6.tar.gz
            tar xzf redis-3.0.6.tar.gz
            cd redis-3.0.6
            make

            rm -f /usr/local/bin/redis-server
            rm -f /usr/local/bin/redis-cli

            """
            C=self.cuisine.bash.replaceEnvironInText(C)
            C=self.cuisine.core.args_replace(C)
            self.cuisine.core.run_script(C,profile=True)
            #move action
            C="""
            set -ex
            mkdir -p $base/bin/
            cp -f $tmpDir/build/redis/redis-3.0.6/src/redis-server $base/bin/
            cp -f $tmpDir/build/redis/redis-3.0.6/src/redis-cli $base/bin/

            rm -rf $base/apps/redis
            """
            C=self.cuisine.bash.replaceEnvironInText(C)
            C=self.cuisine.core.args_replace(C)
            self.cuisine.core.run_script(C, profile=True)
        else:
            if self.cuisine.core.command_check("redis-server")==False:
                self.cuisine.package.install("redis")
            cmd=self.cuisine.core.command_location("redis-server")
            dest="%s/redis-server"%self.cuisine.core.dir_paths["binDir"]
            if cmd!=dest:
                self.cuisine.core.file_copy(cmd,dest)

        self.cuisine.bash.addPath(j.sal.fs.joinPaths(self.cuisine.core.dir_paths["base"], "bin"), action=True)

        j.clients.redis.executor=self.executor
        j.clients.redis.cuisine=self.cuisine
        j.clients.redis.configureInstance(name, ip, port, maxram=maxram, appendonly=appendonly, \
            snapshot=snapshot, slave=slave, ismaster=ismaster, passwd=passwd, unixsocket=False)

        if start:
            self.start(name)

    def start(self, name="main"):
        dpath,cpath=j.clients.redis._getPaths(name)
        cmd="$binDir/redis-server %s"%cpath
        self.cuisine.processmanager.ensure(name="redis_%s" % name,cmd=cmd,env={},path='$binDir')