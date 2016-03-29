#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import requests

import time
import pprint
from JumpScale import j

class Syncthing:
    def __init__(self):
        self.__jslocation__ = "j.clients.syncthing"

    def get(self,addr="localhost",port=22001,sshport=22,rootpasswd="js111js",apikey="js111js"):
        return SyncthingClient(addr,port,sshport,rootpasswd,apikey)

class SyncthingClient:

    def __init__(self, addr="localhost",port=22001,sshport=22,rootpasswd="js111js",apikey="js111js"):
        self._session = requests.session()
        addr=addr.lower()
        if addr=="127.0.0.1":
            addr="localhost"
        self.addr=addr
        self.sshport=sshport
        self.rootpasswd=rootpasswd
        self.port=port
        #@todo need to be https
        self.syncthing_url = 'http://%s:%s/rest' % (self.addr,self.port)
        self.syncthing_apikey = apikey
        self._config=None

    def executeBashScript(self,cmds,die=True):
        print("execute cmd on %s"%self.addr)
        print(cmds)
        if self.addr=="localhost":
            return j.tools.cuisine.local.core.run_script(content=cmds, die=die)
        else:
            executor = j.tools.cuisine.get(j.tools.executor.getSSHBased(addr=self.addr, port=self.sshport))
            return executor.cuisine.core.run_script(content=cmds, die=die)

    def install(self,name=""):
        C="""
        set -ex
        tmux kill-session -t sync > /dev/null 2>&1;tmux new-session -d -s sync -n sync
        if [ "$(uname)" == "Darwin" ]; then
            # Do something under Mac OS X platform
            echo 'install brew'
            set +ex
            ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
            brew install curl
            brew install python
            brew install git
            brew install wget
            set -ex
            cd $TMPDIR
            wget https://github.com/syncthing/syncthing/releases/download/v0.11.25/syncthing-macosx-amd64-v0.11.25.tar.gz -O syncthing.tar.gz
            tar -xf syncthing.tar.gz
            cd syncthing-macosx-amd64-v0.11.25
            cp syncthing /usr/local/bin/

        elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
            dist=''
            dist=`grep DISTRIB_ID /etc/*-release | awk -F '=' '{print $2}'`
            if [ "$dist" == "Ubuntu" ]; then
                echo "found ubuntu"
                apt-get install wget curl git ssh python2.7 python -y
            fi
            cd /tmp
            wget https://github.com/syncthing/syncthing/releases/download/v0.11.25/syncthing-linux-amd64-v0.11.25.tar.gz -O syncthing.tar.gz
            tar -xf syncthing.tar.gz
            cd syncthing-linux-amd64-v0.11.25
            cp syncthing /usr/local/bin/

        elif [ "$(expr substr $(uname -s) 1 10)" == "MINGW32_NT" ]; then
            # Do something under Windows NT platform
            echo 'windows'
            echo "CODE NOT COMPLETE FOR WINDOWS IN install.sh"
            exit
        fi

        tmux send-keys -t sync "syncthing -gui-authentication=admin:$rootpasswd -gui-apikey=$apikey -gui-address=0.0.0.0:22001" C-m



        """
        C=C.replace("$rootpasswd",self.rootpasswd)
        C=C.replace("$apikey",self.syncthing_apikey)
        res=self.executeBashScript(C)

        print("check if we can find syncthing on right port: %s:%s"%(self.addr,self.port))
        if j.sal.nettools.waitConnectionTest(self.addr,self.port,timeout=10)==False:
            raise j.exceptions.RuntimeError("Could not find syncthing on %s:%s, tcp port test"%(self.addr,self.port))

        print(self.status_get())


    def restart(self):
        print("set config")
        pprint.pprint( self._config)
        self.config_set()
        print("restart")

        res= self.api_call("system/restart",get=False)
        print("wait for connection")
        time.sleep(0.5)
        j.sal.nettools.waitConnectionTest(self.addr,self.port,timeout=2)
        print("connection reestablished")

    def status_get(self):
        return self.api_call("system/status")


    def config_get(self,reload=False):
        if self._config!=None and reload==False:
            return self._config
        self._config=self.api_call("system/config")
        return self._config

    def config_set(self):
        self.api_call("system/config",get=False,data=self._config)

    def config_get_folders(self):
        config=self.config_get()
        return config["folders"]

    def config_get_devices(self):
        config=self.config_get()
        return config["devices"]

    def config_exists_folder(self,name):
        name=name.lower()
        for folder in self.config_get_folders():
            if folder["id"].lower()==name:
                return True
        return False

    def config_exists_device(self,name):
        name=name.lower()
        for device in self.config_get_devices():
            if device["name"].lower()==name:
                return True
        return False

    def id_get(self):
        return self.status_get()["myID"]

    def config_delete_folder(self,name):
        config=self.config_get()
        if self.config_exists_folder(name):
            #remove the folder
            x=len(self._config["folders"])
            res=[]
            for folder in self._config["folders"]:
                if not folder["id"].lower()==name:
                    res.append(folder)
            self._config["folders"]=res
            if len(res)!=x:
                print('deleted folder:%s'%name)
                # self.config_set()

    def config_delete_device(self,name):
        config=self.config_get()
        if self.config_exists_device(name):
            #remove the folder
            x=len(self._config["devices"])
            res=[]
            for folder in self._config["devices"]:
                if not folder["name"].lower()==name:
                    res.append(folder)
            self._config["devices"]=res
            if len(res)!=x:
                print('deleted devices:%s'%name)
                # self.config_set()

    def config_delete_all_folders(self):
        config=self.config_get()
        #remove the folder
        self._config["folders"]=[]
        print('deleted all folder')
        # self.config_set()

    def config_delete_all_devices(self):
        config=self.config_get()
        #remove the folder
        self._config["devices"]=[]
        print('deleted all devices')
        # self.config_set()

    def config_add_device(self,name,deviceid,replace=True,introducer=False,compression='always'):
        print("add device:%s"%name)
        name=name.lower()
        config=self.config_get()
        if self.config_exists_device(name):
            if replace:
                #remove the device
                res=[]
                for device in self._config["devices"]:
                    if not device["name"].lower()==name:
                        res.append(device)
                self._config["devices"]=res
            else:
                raise j.exceptions.RuntimeError("Cannot add device %s, exists"%name)

        device={ 'addresses': ['dynamic'],
            'certName': '',
            'compression': compression,
            'deviceID': deviceid,
            'introducer': introducer,
            'name': name}

        config["devices"].append(device)

        print("device set:%s"%name)

        # self.config_set()
        return device

    def config_add_folder(self,name,path,replace=True,ignorePerms=False,readOnly=False,rescanIntervalS=10,devices=[]):
        name=name.lower()
        config=self.config_get()
        if self.config_exists_folder(name):
            if replace:
                #remove the folder
                res=[]
                for folder in self._config["folders"]:
                    if not folder["id"].lower()==name:
                        res.append(folder)
                self._config["folders"]=res
            else:
                raise j.exceptions.RuntimeError("Cannot add folder %s, exists"%name)

        if self.id_get() not in devices:
            devices.append(self.id_get())

        if devices!=[]:
            devices=[{'deviceID': item} for item in devices]

        folder={'autoNormalize': False,
            'copiers': 0,
            'devices': devices,
            'hashers': 0,
            'id': name,
            'ignoreDelete': False,
            'ignorePerms': ignorePerms,
            'invalid': '',
            'minDiskFreePct': 5,
            'order': 'random',
            'path': path,
            'pullers': 0,
            'readOnly': readOnly,
            'rescanIntervalS': rescanIntervalS,
            'versioning': {'params': {}, 'type': ''}}
        config["folders"].append(folder)

        print("folder set:%s"%name)

        self.executeBashScript("mkdir -p %s"%path)
        self.restart()
        # self.config_set()
        return folder


    def api_call(self, endpoint, request_body=False, get=True,data=None):
        """
        @param data is dict which can be serialized using json (do not serialize yet)
        """

        endpoint=endpoint.strip("/")
        endpoint="/%s"%endpoint


        url = '%s%s' % (self.syncthing_url, endpoint)

        headers = {'Content-Type': 'application/json', 'User-Agent': 'Syncthing Python client', 'X-API-Key': self.syncthing_apikey}

        if request_body:
            keys = list(request_body.keys())

            key = keys[0]
            keys.remove(key)

            url += '?%s=%s' % (key, request_body[key])

            for key in keys:
                url += '&%s=%s' % (key, request_body[key])

        timeout = 10
        start = time.time()
        ok = False
        while time.time() < (start + timeout) and ok is False:
            try:
                if get:
                    r = self._session.get(url, headers=headers, timeout=2)
                else:
                    r = self._session.post(url, headers=headers,json=data, timeout=2)
                ok = True
            except Exception as e:
                time.sleep(0.5)

        if r.ok is False:
            print("%s"%(url))
            print(endpoint)
            print(request_body)
            raise j.exceptions.RuntimeError("Error in rest call: %s"%r)

        if get and endpoint != '/system/version':
            return r.json()

        print("OK")

        return r.content
