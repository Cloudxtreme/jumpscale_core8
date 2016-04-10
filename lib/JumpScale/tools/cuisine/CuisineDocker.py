
from JumpScale import j
# import os

# import socket

from ActionDecorator import ActionDecorator


class actionrun(ActionDecorator):

    def __init__(self, *args, **kwargs):
        ActionDecorator.__init__(self, *args, **kwargs)
        self.selfobjCode = "cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.docker"


class CuisineDocker():

    def __init__(self, executor, cuisine):
        self.executor = executor
        self.cuisine = cuisine

    @actionrun(action=True,force=False)
    def install(self):
        if self.cuisine.core.isUbuntu:
            if not self.cuisine.core.command_check('docker'):
                C = """
                wget -qO- https://get.docker.com/ | sh
                """
                self.cuisine.core.run_script(C)
            if not self.cuisine.core.command_check('docker-compose'):
                C = """
                curl -L https://github.com/docker/compose/releases/download/1.6.2/docker-compose-`uname -s`-`uname -m` > /usr/local/bin/docker-compose
                chmod +x /usr/local/bin/docker-compose
                """
                self.cuisine.core.run_script(C)
        if self.cuisine.core.isArch:
            self.cuisine.package.install("docker")
            self.cuisine.package.install("docker-compose")

    def archBuild(self):  # @todo (*2*)
        C = """
        FROM base/archlinux:latest

        MAINTAINER "Matthias Adler" <macedigital@gmail.com> / kristof de spiegeleer

        RUN pacman -S --debug --noconfirm archlinux-keyring

        RUN pacman -S --needed --noconfirm git iproute2 iputils procps-ng tar which licenses util-linux
        RUN pacman -S --noconfirm curl wget ssh  mc


        # remove unneeded pkgs, update and clean cache
        # RUN pacman -Rss --noconfirm cronie device-mapper dhcpcd diffutils file nano vi texinfo usbutils gcc pinentry; \

        # RUN pacman -Syu --force --noconfirm; pacman -Scc --noconfirm

        # remove man pages and locale data
        RUN rm -rf /archlinux/usr/share/locale && rm -rf /archlinux/usr/share/man

        # clean unneeded services
        RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == systemd-tmpfiles-setup.service ] || rm -f $i; done); \
        rm -f /lib/systemd/system/multi-user.target.wants/*;\
        rm -f /lib/systemd/system/graphical.target.wants/*; \
        rm -f /etc/systemd/system/*.wants/*;\
        rm -f /lib/systemd/system/local-fs.target.wants/*; \
        rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
        rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
        rm -f /lib/systemd/system/basic.target.wants/*;\
        rm -f /lib/systemd/system/anaconda.target.wants/*;

        # switch default target from graphical to multi-user
        RUN systemctl set-default multi-user.target

        # systemd inside a container
        ENV container docker
        VOLUME [ "/sys/fs/cgroup" ]

        CMD ["/usr/sbin/init"]

        """
        self.cuisine.core.run("rm -rf $tmpDir/docker;mkdir $tmpDir/docker")
        self.cuisine.core.file_write("$tmpDir/docker/Dockerfile", C)

        C = """
        set -ex
        cd $tmpDir/docker
        docker build -t arch .
        """
        self.cuisine.core.run_script(C)

    @actionrun(action=True)
    def ubuntuBuild(self, push=False):

        dest = self.cuisine.git.pullRepo('https://github.com/Jumpscale/dockers.git', ssh=False)
        path = self.cuisine.core.joinpaths(dest, 'js8/x86_64/2_ubuntu1510')

        C = """
        set -ex
        cd %s
        docker build -t jumpscale/ubuntu1510 --no-cache .
        """ % path
        self.cuisine.core.run_script(C)

        if push:
            C = """
            set -ex
            cd %s
            docker push jumpscale/ubuntu1510
            """ % path
            self.cuisine.core.run_script(C)

    def enableSSH(self, conn_str):
        c2 = j.tools.cuisine.get(conn_str)
        # change passwd
        c2.user.passwd("root", j.data.idgenerator.generateGUID())

        # to make sure we execute all actions again (because is new action)
        j.actions.reset(item=c2.runid)

        return conn_str

    @actionrun(action=True, force=True)
    def ubuntu(self, name="ubuntu1", image='jumpscale/ubuntu1510', ports=None, volumes=None, pubkey=None, aydofs=False):
        """
        will return connection string which can be used for getting a cuisine connection as follows:
            j.cuisine.get(connstr)
        @param ports e.g. 2022,2023
        @param volumes e.g. format: "/var/insidemachine:/var/inhost # /var/1:/var/1
        @param ports e.g. format "22:8022 80:8080"  the first arg e.g. 22 is the port in the container

        """
        cmd = "jsdocker create --name {name} --image {image}".format(name=name, image=image)
        if pubkey:
            cmd += " --pubkey '%s'" % pubkey
        if ports:
            cmd += " --ports '%s'" % ports
        if volumes:
            cmd += " --volumes '%s'" % volumes
        if aydofs:
            cmd += " --aysfs"
        self.cuisine.core.run(cmd, profile=True)
        cmd = "jsdocker list --name {name} --parsable".format(name=name)
        out = self.cuisine.core.run(cmd, profile=True)
        info = j.data.serializer.json.loads(out)

        port = info[0]["port"]
        if 'host' in info[0]:
            host = info[0]['host']
            return "%s:%s" % (host, port)
        else:
            return "%s:%s" % (self.executor.addr, port)

    @actionrun(action=True)
    def ubuntuSystemd(self, name="ubuntu1"):
        """
        start ubuntu 15.10 which is using systemd  #@todo (*2*)
        will have to do same tricks as with arch below
        """
        pass

    @actionrun(action=True)
    def archSystemd(self, name="arch1"):
        """
        start arch which is using systemd  #@todo (*2*) there is an issue with tty, cannot install anything (see in arch builder)
        """
        if not self.cuisine.core.isArch:
            raise j.exceptions.RuntimeError("not supported")

        C = """

        set -ex
        mkdir -p /tmp2/
        chmod 600 /tmp2
        mkdir -p /tmp2/cgroup
        mkdir -p /tmp2/cgroup/systemd
        mount --bind /sys/fs/cgroup/systemd /tmp2/cgroup/systemd
        """
        self.cuisine.core.run_script(C)

        C = """
        set +ex
        docker kill $name
        docker rm $name

        set -ex
        mkdir -p /tmp2/$name/run
        mount -t tmpfs tmpfs /tmp2/$name/run

        mkdir -p /tmp2/$name/run/lock
        mount -t tmpfs tmpfs /tmp2/$name/run/lock

        """
        C = C.replace("$name", name)
        print(C)
        self.cuisine.core.run_script(C)

        # self.cuisine.core.run("docker run -d --name %s -v /tmp2/cgroup:/sys/fs/cgroup:ro -v /tmp2/%s/run:/run:rw tozd/ubuntu-systemd"%(name,name))
        self.cuisine.core.run("docker run -d --name %s -v /tmp2/cgroup:/sys/fs/cgroup:ro -v /tmp2/%s/run:/run:rw arch" % (name, name))
