
from JumpScale import j
import os
import time

import socket

from ActionDecorator import ActionDecorator
class actionrun(ActionDecorator):
    def __init__(self,*args,**kwargs):
        ActionDecorator.__init__(self,*args,**kwargs)
        self.selfobjCode="cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.installer"


class CuisineInstaller(object):

    def __init__(self,executor,cuisine):
        self.executor=executor
        self.cuisine=cuisine

    @actionrun(action=True)
    def jumpscale_installed(self, die=False):
        rc, out = self.cuisine.core.run('which js', die=False)
        if rc == 0 and out:
            return True
        return False

    @actionrun(action=True)
    def clean(self):
        self.cuisine.core.dir_ensure(self.cuisine.core.dir_paths["tmpDir"])
        if not self.cuisine.core.isMac:
            C = """
                set +ex
                # pkill redis-server #will now kill too many redis'es, should only kill the one not in docker
                # pkill redis #will now kill too many redis'es, should only kill the one not in docker
                umount -fl /optrw
                apt-get remove redis-server -y
                rm -rf /overlay/js_upper
                rm -rf /overlay/js_work
                rm -rf /optrw
                js8 stop
                pskill js8
                umount -f /opt
                """
        else:
            C = """
                set +ex
                js8 stop
                pskill js8
                echo "OK"
                """

        self.cuisine.core.run_script(C,die=False)


    @actionrun(action=True)
    def jumpscale8(self, rw=False, reset=False):
        """
        install jumpscale, will be done as sandbox

        @param rw if True install sandbox in RW mode
        @param reset, remove old code (only used when rw mode)

        """
        if self.jumpscale_installed() and not reset:
            return
        self.clean()
        self.base()


        C = """
            js8 stop
            set -ex
            cd /usr/bin
            rm -f js8
            cd /usr/local/bin
            rm -f js8
            rm -f /usr/local/bin/jspython
            rm -f /usr/local/bin/js
            rm -fr /opt/*
            """
        self.cuisine.core.run_script(C, action=True,force=True)

        if not self.cuisine.core.isUbuntu:
            raise j.exceptions.RuntimeError("not supported yet")

        if reset:
            C = """
                set +ex
                rm -rf /opt
                rm -rf /optrw
                """
            self.cuisine.core.run_script(C, action=True,force=True)
            

        C = """
            wget https://stor.jumpscale.org/storx/static/js8 -O /usr/local/bin/js8
            chmod +x /usr/local/bin/js8
            cd /
            mkdir -p $base
            """
        self.cuisine.core.run_script(C, action=True,force=True)

        """
        install jumpscale8 sandbox in read or readwrite mode
        """
        C = """
            set -ex
            rm -rf /opt
            cd /usr/local/bin
            """
        if rw:
            C += "./js8 -rw init"
        else:
            C += "./js8 init"
        self.cuisine.core.run_script(C, action=True,force=True)

        start = j.data.time.epoch
        timeout = 30
        while start + timeout > j.data.time.epoch:
            if not self.cuisine.core.file_exists('/opt/jumpscale8/bin/jspython'):
                time.sleep(2)
            else:
                self.cuisine.core.file_link('/opt/jumpscale8/bin/jspython', '/usr/local/bin/jspython')
                self.cuisine.core.file_link('/opt/jumpscale8/bin/js', '/usr/local/bin/js')
                self.cuisine.bash.include('/opt/jumpscale8/env.sh')
                break

        print ("* re-login into your shell to have access to js, because otherwise the env arguments are not set properly.")

    @actionrun(action=True)
    def base(self):
        self.clean()

        if self.cuisine.core.isMac:
            C=""
        else:
            C="""
            sudo
            net-tools
            python3
            """

        C+="""
        openssl
        wget
        curl
        git
        mc
        tmux
        """
        out=""
        #make sure all dirs exist
        for key,item in self.cuisine.core.dir_paths.items():
            out+="mkdir -p %s\n"%item
        self.cuisine.core.run_script(out)

        if not self.cuisine.core.isMac:
            self.cuisine.package.install("fuse")

        if self.cuisine.core.isArch:
            self.cuisine.package.install("wpa_actiond") #is for wireless auto start capability

        self.cuisine.package.mdupdate()
        self.cuisine.package.multiInstall(C)
        self.cuisine.package.upgrade()
        self.cuisine.package.clean()


    def __str__(self):
        return "cuisine.installer:%s:%s" % (getattr(self.executor, 'addr', 'local'), getattr(self.executor, 'port', ''))


    __repr__=__str__
