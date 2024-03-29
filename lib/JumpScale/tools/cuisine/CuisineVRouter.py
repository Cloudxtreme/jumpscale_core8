
from JumpScale import j
import os
import time

import socket

from ActionDecorator import ActionDecorator
class actionrun(ActionDecorator):
    def __init__(self,*args,**kwargs):
        ActionDecorator.__init__(self,*args,**kwargs)
        self.selfobjCode="cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.vrouter"


class CuisineVRouter(object):

    def __init__(self,executor,cuisine):
        self.executor=executor
        self.cuisine=cuisine


    @actionrun(action=True)
    def accesspoint(self,passphrase,name="",dns="8.8.8.8",interface="wlan0"):
        """
        create an accesspoint
        """

        #create_ap --no-virt -m bridge wlan1 eth0 kds10 kds007kds
        #sysctl -w net.ipv4.ip_forward=1
        #iptables -t nat -I POSTROUTING -o wlan0 -j MASQUERADE

        # cmd1='dnsmasq -d'
        if name!="":
            hostname=name
        else:
            hostname=self.cuisine.core.run("hostname")
        #--dhcp-dns 192.168.0.149
        cpath=self.cuisine.core.run("which create_ap")
        cmd2='%s %s eth0 gig_%s %s -d'%(cpath,interface,hostname,passphrase)

        giturl="https://github.com/oblique/create_ap"
        self.cuisine.pullGitRepo(url=giturl,dest=None,login=None,passwd=None,depth=1,\
            ignorelocalchanges=True,reset=True,branch=None,revision=None, ssh=False)

        self.cuisine.core.run("cp /opt/code/create_ap/create_ap /usr/local/bin/")

        START1="""
        [Unit]
        Description=Create AP Service
        Wants=network-online.target
        After=network-online.target

        [Service]
        Type=simple
        ExecStart=$cmd
        KillSignal=SIGINT
        Restart=always
        RestartSec=5

        [Install]
        WantedBy=multi-user.target
        """
        pm = self.cuisine.processmanager.get("systemd")
        pm.ensure("ap",cmd2,descr="accesspoint for local admin",systemdunit=START1)



    def __str__(self):
        return "cuisine.vrouter:%s:%s" % (getattr(self.executor, 'addr', 'local'), getattr(self.executor, 'port', ''))


    __repr__=__str__
