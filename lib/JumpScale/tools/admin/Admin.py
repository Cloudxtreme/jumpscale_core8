from JumpScale import j
import copy

redis=j.clients.redis.get("127.0.0.1", 9999)

from Node import Node

class AdminFactory:
    def __init__(self):
        self.__jslocation__ = "j.tools.admin"

    def get(self,path,args,failWhenNotExist=False):
        return Admin(path,args,failWhenNotExist)

class Admin():

    def __init__(self,path,args,failWhenNotExist=False):
        j.core.admin=self
        self.args=args
        self.hostKeys=[]
        self.gridNameAliases={}
        self.sysadminPasswd=""

        # DO NOT USE CREDIS IN THIS CONTEXT, NOT THREAD SAFE
        self.redis = j.clients.redis.get("127.0.0.1", 9999)

        # self.nodes={}
        if "reset" in self.args.__dict__ and self.args.reset:
            self.deleteScriptRunInfo()

        start=path
        self.startdir=path
        while not j.sal.fs.exists(path="%s/.git"%start):
            start1up=start
            start=j.sal.fs.getParent(start)
            if start.strip("/")=="":
                j.events.inputerror_critical("Cannot find git root directory from %s"%j.sal.fs.getcwd())

        self.root=start
        self.name=j.sal.fs.getDirName("%s/"%start1up,lastOnly=True)
        
        self.git=j.clients.git.getClient(self.root)
        self.git.pull()

        self.tmpdir=j.sal.fs.getTmpDirPath()

        self.load()

    def load(self):
        j.sal.fs.copyDirTree("%s/jumpscripts"%self.root,"%s/jumpscripts"%self.tmpdir)

        self.hrd=j.data.hrd.get(self.startdir,prefixWithName=True)
        self.hrd.applyOnDir(self.tmpdir)

        

        j.core.jumpscripts.load("%s/jumpscripts"%self.tmpdir)


    def getNodes(self):
        return self.hrd.prefix("node",2)

    def run(self):
        # last=self.git.repo.head.log()[-1]
        # last.newhexsha

        for node in self.getNodes():
            print(node)
            data=self.hrd.getDictFromPrefix(node)
            #remove empty records in services installed
            data["servicesinstalled"]=[item for item in data["servicesinstalled"] if item.strip()!=""]
            for toinstall in data["servicestoinstall"]:
                actor,name=toinstall.strip().split("/")
                try:
                    res=j.core.jumpscripts.execute( organization="jumpscale", actor=actor, action=name, args=data)
                except Exception as e:
                    print(e)
                

    def reset(self):
        raise j.exceptions.RuntimeError("not implemented")


    def osis2git(self):
        roles = list()
        if args.roles:
            roles = args.roles.split(",")
        #@todo change to use hostkeys (reem)
        raise j.exceptions.RuntimeError("not implemented")
        nodes = self._getActiveNodes()
        hosts = [node['name'] for node in nodes]
        for node in nodes:
            for role in roles:
                if role not in node['roles']:
                    hosts.remove(node['name'])
                    break
        self.hostKeys = hosts
        self.hostKeys.sort()


    def _getActiveNodes(self):
        ncl = j.data.models.system.Node
        return ncl.find({'active': True})
    
    def raiseError(self,action,msg,e=None):
        #@todo make better
        raise j.exceptions.RuntimeError("%s;%s"%(action,msg))

    def getNode(self,name=""):
        name=name.lower()
        return Node(name)
        

        node=JNode()
        node.cuapi=self.cuapi
        node.args=self.args
        node.model=""
        return node

        if gridname=="":
            if j.sal.nettools.pingMachine(name.strip("/").strip(),1):
                node=JNode()
                node.ip=name
                node.hostname=name
                node.args=self.args
                node.cuapi=self.cuapi
                node.currentScriptRun=None
                node.getScriptRun()
                return node
            else:
                raise j.exceptions.RuntimeError("Could not find node:'%s'"%name)

        
        if self.redis.hexists("admin:nodes","%s:%s"%(gridname,name))==False:
            raise j.exceptions.RuntimeError("could not find node: '%s/%s'"%(gridname,name))
            # node=JNode()
            # node.ip=name
            # node.host=name
        else:
            data=self.redis.hget("admin:nodes","%s:%s"%(gridname,name))
            node=JNode()
            try:
                node.__dict__.update(j.data.serializer.json.loads(data))
            except Exception as e:
                raise j.exceptions.RuntimeError("could not decode node: '%s/%s'"%(gridname,name))
                # node=JNode()
                # self.setNode(node)
        node.args=self.args
        node.gridname=gridname
        node.name=name
        node.cuapi=self.cuapi
        node.currentScriptRun=None
        node._connectCuapi()
        return node 

    def setNode(self,node):
        node2=copy.copy(node.__dict__)
        for key in list(node2.keys()):
            if key[0]=="_":
                node2.pop(key)
        node2.pop("cuapi")
        node2.pop("args")
        node2.pop("currentScriptRun")
        
        self.redis.hset("admin:nodes","%s:%s"%(node.gridname,node.name),json.dumps(node2))
        sr=node.currentScriptRun
        if sr!=None:
            self.redis.hset("admin:scriptruns","%s:%s:%s"%(node.gridname,node.name,sr.runid),json.dumps(sr.__dict__))

    def executeForNode(self,node,jsname,once=True,sshtest=True,**kwargs):
        """
        return node
        """
        sr=node.currentScriptRun
        jsname=jsname.lower()
        now= j.data.time.getTimeEpoch()
        do=True
        if once:
            for item in self.getScriptRunInfo():
                if item.state=="OK" and item.nodename==node.name and item.gridname==node.gridname:
                    do=False
            
        # if self.args.force:
        #     do=True
        if do:
            print("* tcp check ssh")
            if jsname not in j.admin.js:
                self.raiseError("executejs","cannot find js:%s"%jsname)

            if sshtest and not j.sal.nettools.waitConnectionTest(node.ip,22, self.args.timeout):
                self.raiseError("executejs","jscript:%s,COULD NOT check port (ssh)"%jsname)
                return
            try:                
                sr.result=j.admin.js[jsname](node=node,**kwargs)
                node.actionsDone[jsname]=now
                node.lastcheck=now
            except BaseException as e:
                msg="error in execution of %s.Stack:\n%s\nError:\n%s\n"%(jsname,j.errorconditionhandler.parsePythonExceptionObject(e),e)
                sr.state="ERROR"
                sr.error+=msg
                print() 
                print(msg)
                if jsname in node.actionsDone:
                    node.actionsDone.pop(jsname)
            self.setNode(node)
        else:
            print(("No need to execute %s on %s/%s"%(jsname,node.gridname,node.name)))
        return node

    def execute(self,jsname,once=True,reset=False,**kwargs):
        res=[]
        for host in self.hostKeys:
            gridname, _, name = host.partition('__')
            node=self.getNode(gridname,name)
            self.executeForNode(node,jsname,once,**kwargs)


    def sshfs(self,gridname,name):
        node=self.getNode(gridname,name)
        if name!="admin":
            path="/mnt/%s_%s_jsbox"%(node.gridname,node.name)
            j.sal.fs.createDir(path)
            cmd="sshfs %s:/opt/jsbox /mnt/%s_%s_jsbox"%(node.ip,node.gridname,node.name)
            print(cmd)
            j.sal.process.executeWithoutPipe(cmd)

            path="/mnt/%s_%s_jsboxdata"%(node.gridname,node.name)
            j.sal.fs.createDir(path)
            print(cmd)
            cmd="sshfs %s:/opt/jsbox_data /mnt/%s_%s_jsboxdata"%(node.ip,node.gridname,node.name)
            j.sal.process.executeWithoutPipe(cmd)
        else:
            path="/mnt/%s_%s_code"%(node.gridname,node.name)
            j.sal.fs.createDir(path)
            cmd="sshfs %s:%s /mnt/%s_%s_code"%(node.ip,j.dirs.codeDir,node.gridname,node.name)
            print(cmd)
            j.sal.process.executeWithoutPipe(cmd)
            path="/mnt/%s_%s_jumpscale"%(node.gridname,node.name)
            j.sal.fs.createDir(path)
            cmd="sshfs %s:/opt/jumpscale /mnt/%s_%s_jumpscale"%(node.ip,node.gridname,node.name)
            print(cmd)
            j.sal.process.executeWithoutPipe(cmd)

    def sshfsumount(self,gridname="",name=""):
        rc,mount=j.sal.process.execute("mount")
        

        def getMntPath(mntpath):
            for line in mount.split("\n"):
                if line.find("sshfs")!=-1 and line.find(mntpath+" ")!=-1:
                    return line.split(" ")[0]
            return None

        def getMntPaths():
            res=[]
            for line in mount.split("\n"):
                if line.find("sshfs")!=-1:
                    line=line.replace("  "," ")
                    line=line.replace("  "," ")                    
                    res.append(line.split(" ")[2])
            return res


        def do(mntpath):
            mntpath2=getMntPath(mntpath)
            if mntpath2==None:
                return None
                
            cmd="umount %s"%(mntpath2)
            rc,out=j.sal.process.execute(cmd,False)
            if rc>0:
                if out.find("device is busy")!=-1:
                    res=[]
                    print(("MOUNTPOINT %s IS BUSY WILL TRY TO FIND WHAT IS KEEPING IT BUSY"%mntpath))
                    cmd ="lsof -bn -u 0|grep '%s'"%mntpath  #only search for root processes
                    print(cmd)
                    rc,out=j.sal.process.execute(cmd,False)
                    for line in out.split("\n"):
                        if line.find(mntpath)!=-1 and line.lower().find("avoiding")==-1 and line.lower().find("warning")==-1:
                            line=line.replace("  "," ")
                            line=line.replace("  "," ")
                            cmd=line.split(" ")[0]
                            pid=line.split(" ")[1]
                            key="%s (%s)"%(cmd,pid)
                            if key not in res:
                                res.append(key)
                    print("PROCESSES WHICH KEEP MOUNT BUSY:")
                    print(("\n".join(res)))                    
                    return
                raise j.exceptions.RuntimeError("could not umount:%s\n%s"%(mntpath,out))

        if gridname=="" and name=="":
            for mntpath in getMntPaths():
                print(("UMOUNT:%s"%mntpath))
                do(mntpath)
            
        else:
            do("/mnt/%s_%s_jsboxdata"%(gridname,name))
            do("/mnt/%s_%s_jsbox"%(gridname,name))

    def createidentity(self):
        print("MAKE SURE YOU SELECT A GOOD PASSWD, select default destination!")
        do=j.sal.process.executeWithoutPipe
        do("ssh-keygen -t dsa")
        keyloc="/root/.ssh/id_dsa.pub"
        if not j.sal.fs.exists(path=keyloc):
            raise j.exceptions.RuntimeError("cannot find path for key %s, was keygen well executed"%keyloc)
        key=j.sal.fs.fileGetContents(keyloc).strip()
        c=""
        login=j.tools.console.askString("official loginname (e.g. despiegk)")
        c+="id.name=%s\n"%j.tools.console.askString("fullname")
        c+="id.email=%s\n"%j.tools.console.askString("email")
        c+="id.mobile=%s\n"%j.tools.console.askString("mobile")
        c+="id.skype=%s\n"%j.tools.console.askString("skype")

        c+="id.key.dsa.pub=%s\n"%key

        idloc=self._getPath("identities/")
        if login=="":
            raise j.exceptions.RuntimeError("login cannot be empty")
        userloc=j.sal.fs.joinPaths(idloc,login)
        
        j.sal.fs.createDir(userloc)
        hrdloc=j.sal.fs.joinPaths(idloc,login,"id.hrd")
        j.sal.fs.writeFile(filename=hrdloc,contents=c)
        for name in ["id_dsa","id_dsa.pub"]:
            u = j.sal.fs.joinPaths(self._basepath, 'identities','system',name)
            j.sal.fs.copyFile("/root/.ssh/%s"%name,u)



    def _getHostNames(self,hostfilePath,exclude={}):
        """
        gets hostnames from /etc/hosts
        """
        result={}
        for line in j.sal.fs.fileGetContents(hostfilePath).split("\n"):
            # print line
            line=line.strip()
            if line.find("########")==0:
                return result
            if line.strip()!="" and line[0]!="#":
                line2=line.replace("\t"," ")
                splits=line2.split(" ")
                name=splits[-1]
                ip=splits[0]
                if name in result:
                    continue
                if line.find("ip6-localhost")!=-1 or line.find("ip6-loopback")!=-1:
                    continue
                if line.find("ip6-localnet")!=-1 or line.find("ip6-mcastprefix")!=-1:
                    continue
                if line.find("ip6-allnodes")!=-1 or line.find("ip6-allrouters")!=-1:
                    continue                    
                if line.find("following lines are desirable")!=-1 or line.find("localhost")!=-1:
                    continue
                result[name]=ip
        return result

    def applyconfiglocal(self):
        #print "will do local changes e.g. for hostnames ",
        hostfilePath="/etc/hosts"
        out="""
# The following lines are desirable for IPv6 capable hosts
::1          ip6-localhost ip6-loopback
fe00::0      ip6-localnet
ff00::0      ip6-mcastprefix
ff02::1      ip6-allnodes
ff02::2      ip6-allrouters

127.0.0.1    localhost

"""        
        
        existingHostnames=self._getHostNames("/etc/hosts")

        def alias(name):
            name=name.lower()
            if name in self.gridNameAliases:
                return [item.lower() for item in self.gridNameAliases[name]]
            else:
                return []

        newHostnames={}
        for hkey in self.redis.hkeys("admin:nodes"):
            gridname,name=hkey.split(":")
            data=self.redis.hget("admin:nodes","%s:%s"%(gridname,name))
            node=JNode()
            try:
                node.__dict__=j.data.serializer.json.loads(data)
            except Exception as e:
                raise j.exceptions.RuntimeError("could not decode node: '%s/%s'"%(gridname,name))
            n=node.name
            n=n.lower()
            g=node.gridname
            g=g.lower()
            newHostnames["%s.%s"%(n,g)]=node.ip
            for g2 in alias(node.gridname):
                if g2!=g:
                    newHostnames["%s.%s"%(n,g2)]=node.ip

        for hostname,ipaddr in list(existingHostnames.items()):
            if hostname.lower() not in list(newHostnames.keys()):
                out+="%-18s %s\n"%(ipaddr,hostname)

        out+="\n#############################\n\n"

        hkeysNew=list(newHostnames.keys())
        hkeysNew.sort()

        for hostname in hkeysNew:
            ipaddr=newHostnames[hostname]
            if hostname.lower() in list(existingHostnames.keys()):
                raise j.exceptions.RuntimeError("error: found new hostname '%s' which already exists in existing hostsfile."%hostname)
            out+="%-18s %s\n"%(ipaddr,hostname)


        out+="\n"

        j.sal.fs.writeFile(filename=hostfilePath,contents=out)


    def getHostNamesKeys(self,gridNameSearch=""):
        C=j.sal.fs.fileGetContents("%s/admin/active.cfg"%j.dirs.cfgDir)

        keys=[]
        gridname=""
        for line in C.split("\n"):
            # print line
            line=line.strip()
            if line.find("####")==0:
                break
            if line=="" or line[0]=="#":
                continue
            if line.find("*")==0:
                gridname=line[1:].strip()
                continue
            if gridNameSearch=="" or gridname==gridNameSearch:
                name=line
                keys.append("%s__%s"%(gridname,name))
        return keys

    def getScriptRunInfo(self):
        res=[]
        for hkey in self.redis.hkeys("admin:scriptruns"):
            gridname,nodename,jscriptid=hkey.split(":")
            if jscriptid==str(self.runid):
                sr=ScriptRun()
                sr.__dict__=j.data.serializer.json.loads(self.redis.hget("admin:scriptruns",hkey))
                res.append(sr)
        return res

    def deleteScriptRunInfo(self):
        res=[]
        for hkey in self.redis.hkeys("admin:scriptruns"):
            gridname,nodename,runid=hkey.split(":")
            if runid==str(self.runid):
                self.redis.hdel("admin:scriptruns",hkey)

    def printResult(self):
        ok=[]
        nok=[]
        error=""
        result=""
        for sr in self.getScriptRunInfo():
            if sr.state=="OK":
                ok.append("%-10s %-15s"%(sr.gridname,sr.nodename))
                if sr.result!="":
                    result+="#%-15s %-10s############################################################\n"%(sr.gridname,sr.nodename)
                    result+="%s\n\n"%sr.result
            else:
                nok.append("%-10s %-15s"%(sr.gridname,sr.nodename))
                for key,value in list(sr.__dict__.items()):
                    error+="%-15s: %s"%(key,value)
                error+="#######################################################################\n\n"


        j.sal.fs.createDir("%s/admin"%j.dirs.varDir)

        if result!="":
            print("######################## RESULT ##################################")
            print(result)
            j.sal.fs.writeFile(filename="%s/admin/%s.result"%(j.dirs.varDir,sr.runid),contents=result)

        if error!="":
            print("######################## ERROR ##################################")
            print(error)
            j.sal.fs.writeFile(filename="%s/admin/%s.error"%(j.dirs.varDir,sr.runid),contents=error)

        if error!="":
            exitcode = 1
        else:
            exitcode=0

        print("\n######################## OK #####################################")
        ok.sort()
        print(("\n".join(ok)))
        if len(nok)>0:
            print("######################## ERROR ###################################")
            nok.sort()
            print(("\n".join(nok)))

        return exitcode









