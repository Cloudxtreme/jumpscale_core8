
from JumpScale import j





from ActionDecorator import ActionDecorator
class actionrun(ActionDecorator):
    def __init__(self,*args,**kwargs):
        ActionDecorator.__init__(self,*args,**kwargs)
        self.selfobjCode="cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.installerdevelop"


class CuisineInstallerDevelop():

    def __init__(self,executor,cuisine):
        self.executor=executor
        self.cuisine=cuisine

    @actionrun(action=True)
    def python(self):
        C="""
        libpython3.5-dev
        python3.5-dev
        libffi-dev
        gcc
        make
        build-essential
        autoconf
        libtool
        pkg-config
        libpq-dev
        libsqlite3-dev
        #net-tools
        """
        self.cuisine.package.multiInstall(C)

    @actionrun(action=True)
    def pip(self):
        self.cuisine.installer.base()
        self.python()
        C="""
            #important remove olf pkg_resources, will conflict with new pip
            rm -rf /usr/lib/python3/dist-packages/pkg_resources
            cd $tmpDir/
            rm -rf get-pip.py
            wget https://bootstrap.pypa.io/get-pip.py
            """
        C=self.cuisine.core.args_replace(C)
        self.cuisine.core.run_script(C)
        C="cd $tmpDir/;python3.5 get-pip.py"
        C=self.cuisine.core.args_replace(C)
        self.cuisine.core.run(C)


    @actionrun(action=True)
    def jumpscale8(self):
        #make sure base is done & env is clean
        if self.cuisine.installer.jumpscale_installed():
            return
        self.cuisine.installer.base()

        self.python()
        self.pip(action=True)

        #install brotli
        C="""
        cd $tmpDir/
        sudo rm -rf brotli/
        git clone https://github.com/google/brotli.git
        cd $tmpDir/brotli/
        python setup.py install
        cd tests
        make
        cd ..
        cp $tmpDir/brotli/tools/bro /usr/local/bin/
        rm -rf $tmpDir/brotli
        """
        C=self.cuisine.core.args_replace(C)
        self.cuisine.core.run_script(C)

        #python etcd
        C="""
        cd $tmpDir/
        git clone https://github.com/jplana/python-etcd.git
        cd python-etcd
        python3.5 setup.py install
        """
        C=self.cuisine.core.args_replace(C)
        self.cuisine.core.run_script(C)

        #gevent
        C="""
        pip3 install 'cython>=0.23.4' git+git://github.com/gevent/gevent.git#egg=gevent
        """
        self.cuisine.core.run_script(C)

        C="""
        paramiko

        msgpack-python
        redis
        #credis
        aioredis


        mongoengine

        #bcrypt
        blosc
        certifi
        docker-py

        gitlab3
        gitpython
        html2text

        # pysqlite
        click
        influxdb
        ipdb
        ipython --upgrade
        jinja2
        netaddr

        reparted
        pytoml
        pystache
        pymongo
        psycopg2
        pathtools
        psutil

        pytz
        requests
        sqlalchemy
        urllib3
        zmq
        pyyaml
        python-etcd
        websocket
        marisa-trie
        pylzma
        ujson
        watchdog
        pygo
        minio

        # colorlog
        colored-traceback
        #pygments
        tmuxp

        xonsh
        pudb

        traitlets
        python-telegram-bot
        colorlog
        """
        self.cuisine.pip.multiInstall(C,upgrade=True)

        self.cuisine.apps.redis.build()

        """
        install dnspython3
        """
        self.dnspython3()


        if self.cuisine.core.isUbuntu or self.cuisine.core.isArch:
            C='cd $tmpDir/;rm -f install.sh;curl -k https://raw.githubusercontent.com/Jumpscale/jumpscale_core8/master/install/install.sh > install.sh;bash install.sh'
            C=self.cuisine.core.args_replace(C)
            self.cuisine.core.run(C)
        elif self.cuisine.core.isMac:
            cmd = """sudo mkdir -p /opt
            # sudo chown -R despiegk:root /opt
            ruby -e \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)\""""
            self.cuisine.core.run(cmd)
        else:
            raise j.exceptions.RuntimeError("platform not supported yet")


    @actionrun(action=True)
    def dnspython3(self):
        C = """
            cd $tmpDir
            wget http://www.dnspython.org/kits3/1.12.0/dnspython3-1.12.0.tar.gz
            tar -xf dnspython3-1.12.0.tar.gz
            cd dnspython3-1.12.0
            ./setup.py install
            """
        self.cuisine.core.run_script(C)
