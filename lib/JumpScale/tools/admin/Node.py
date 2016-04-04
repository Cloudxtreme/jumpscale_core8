from JumpScale import j
import time

redis=j.clients.redis.get("127.0.0.1", 9999)

class Node():
    def __init__(self,name,args={}):
        self.model=j.core.admin.hrd.getDictFromPrefix("node.%s"%name)
        self.ssh=None
        self.args=args

    def executeCmds(self,cmds,die=True,insandbox=False):
        scriptRun=self.getScriptRun()
        out=scriptRun.out
        for line in cmds.split("\n"):
            if line.strip()!="" and line[0]!="#":
                self.log("execcmd",line)
                if insandbox:
                    line2="source /opt/jsbox/activate;%s"%line 
                else:
                    line2=line               
                try:                    
                    out+="%s\n"%self.ssh.run(line2)
                except BaseException as e:
                    if die:
                        self.raiseError("execcmd","error execute:%s"%line,e)

    def killProcess(self,filterstr,die=True):
        found=self.getPids(filterstr)
        for item in found:
            self.log("killprocess","kill:%s"%item)
            try:
                self.ssh.run("kill -9 %s"%item)
            except Exception as e:
                if die:
                    self.raiseError("killprocess","kill:%s"%item,e)

    def getPids(self,filterstr,die=True):
        self.log("getpids","")
        with hide('output'):
            try:
                out=self.ssh.run("ps ax")
            except Exception as e:
                if die:
                    self.raiseError("getpids","ps ax",e)
        found=[]
        for line in out.split("\n"):
            if line.strip()!="":
                if line.find(filterstr)!=-1:
                    line=line.strip()
                    found.append(int(line.split(" ")[0]))   
        return found

    def deployssh(self):
        self.connectSSH()
        keyloc="/root/.ssh/id_dsa.pub"
        
        if not j.sal.fs.exists(path=keyloc):
            if j.tools.console.askYesNo("do you want to generate new local ssh key, if you have one please put it there manually!"):
                do=j.sal.process.executeWithoutPipe
                do("ssh-keygen -t dsa")
            else:
                j.application.stop()
        key=j.sal.fs.fileGetContents(keyloc)
        self.ssh.ssh.authorize("root",key)

    def aysStop(self,name,filterstr,die=True):
        self.log("ays stop","%s (%s)"%(name,filterstr))
        try:
            self.ssh.run("source /opt/jsbox/activate;ays stop -n %s"%name)
        except Exception as e:
            if die:
                self.raiseError("ays stop","%s"%name,e)
        
        found=self.getPids(filterstr)
        if len(found)>0:
            for item in found:
                try:
                    self.ssh.run("kill -9 %s"%item)            
                except:
                    pass

    def aysStart(self,name,filterstr,nrtimes=1,retry=1):
        found=self.getPids(filterstr)
        self.log("ays start","%s (%s)"%(name,filterstr))
        for i in range(retry):
            if len(found)==nrtimes:
                return
            scriptRun=self.getScriptRun()
            try:
                self.ssh.run("source /opt/jsbox/activate;ays start -n %s"%name)  
            except Exception as e:
                if die:
                    self.raiseError("ays start","%s"%name,e)                          
            time.sleep(1)
            found=self.getPids(filterstr)
        if len(found)<nrtimes:
            self.raiseError("ays start","could not Start %s"%name)

    def serviceStop(self,name,filterstr):
        self.log("servicestop","%s (%s)"%(name,filterstr))
        try:
            self.ssh.run("sudo stop %s"%name)
        except:
            pass
        found=self.getPids(filterstr)
        scriptRun=self.getScriptRun()
        if len(found)>0:
            for item in found:
                try:
                    self.ssh.run("kill -9 %s"%item)            
                except:
                    pass
        found=self.getPids(filterstr)
        if len(found)>0:
            self.raiseError("servicestop","could not serviceStop %s"%name)

    def serviceStart(self,name,filterstr,die=True):
        self.log("servicestart","%s (%s)"%(name,filterstr))
        found=self.getPids(filterstr)
        if len(found)==0:
            try:
                self.ssh.run("sudo start %s"%name)          
            except:
                pass            
        found=self.getPids(filterstr)
        if len(found)==0 and die:
            self.raiseError("servicestart","could not serviceStart %s"%name)            

    def serviceReStart(self,name,filterstr):
        self.serviceStop(name,filterstr)
        self.serviceStart(name,filterstr)

    def raiseError(self,action,msg,e=None):
        scriptRun=self.getScriptRun()
        scriptRun.state="ERROR"
        if e!=None:
            msg="Stack:\n%s\nError:\n%s\n"%(j.errorconditionhandler.parsePythonExceptionObject(e),e)
            scriptRun.state="ERROR"
            scriptRun.error+=msg

        for line in msg.split("\n"):
            toadd="%-10s: %s\n" % (action,line)
            scriptRun.error+=toadd
            print(("**ERROR** %-10s:%s"%(self.name,toadd)))
        self.lastcheck=0
        j.admin.setNode(self)
        j.admin.setNode(self)
        raise j.exceptions.RuntimeError("**ERROR**")

    def log(self,action,msg):
        out=""
        for line in msg.split("\n"):
            toadd="%-10s: %s\n" % (action,line)
            print(("%-10s:%s"%(self.name,toadd)))
            out+=toadd

    def setpasswd(self,passwd):
        #this will make sure new password is set
        self.log("setpasswd","")
        cl=j.tools.expect.new("sh")
        if self.args.seedpasswd=="":
           self.args.seedpasswd=self.findpasswd()
        try:
            cl.login(remote=self.name,passwd=passwd,seedpasswd=None)
        except Exception as e:
            self.raiseError("setpasswd","Could not set root passwd.")

    def findpasswd(self):
        self.log("findpasswd","find passwd for superadmin")
        cl=j.tools.expect.new("sh")
        for passwd in j.admin.rootpasswds:
            try:            
                pass
                cl.login(remote=self.name,passwd=passwd,seedpasswd=None)
            except Exception as e:
                self.raiseError("findpasswd","could not login using:%s"%passwd,e)
                continue
            self.passwd=passwd
            j.admin.setNode(self)
        return "unknown"

    def check(self):
        j.data.time.getTimeEpoch()

    def connectSSH(self):
        ip=self.model["ip"]
        port=self.model["port"]
        passwd=self.model["passwd"]
        self.ssh=j.remote.cuisine.connect(ip,port,passwd)

        # if j.sal.nettools.pingMachine(self.args.remote,1):
        #     self.ip=self.args.remote
        # else:
        #     j.events.opserror_critical("Could not ping node:'%s'"% self.args.remote)

        return self.ssh

    def uploadFromcfgDir(self,ttype,dest,additionalArgs={}):
        dest=j.dirs.replaceTxtDirVars(dest)
        cfgDir=j.sal.fs.joinPaths(self._basepath, "cfgs/%s/%s"%(j.admin.args.cfgname,ttype))

        additionalArgs["hostname"]=self.name

        cuapi=self.ssh
        if j.sal.fs.exists(path=cfgDir):
            self.log("uploadcfg","upload from %s to %s"%(ttype,dest))

            tmpcfgDir=j.sal.fs.getTmpDirPath()
            j.sal.fs.copyDirTree(cfgDir,tmpcfgDir)
            j.dirs.replaceFilesDirVars(tmpcfgDir)
            j.application.config.applyOnDir(tmpcfgDir,additionalArgs=additionalArgs)

            items=j.sal.fs.listFilesInDir(tmpcfgDir,True)
            done=[]
            for item in items:
                partpath=j.sal.fs.pathRemoveDirPart(item,tmpcfgDir)
                partpathdir=j.sal.fs.getDirName(partpath).rstrip("/")
                if partpathdir not in done:
                    cuapi.dir_ensure("%s/%s"%(dest,partpathdir), True)
                    done.append(partpathdir)
                try:            
                    cuapi.file_upload("%s/%s"%(dest,partpath),item)#,True,True)  
                except Exception as e:
                    j.sal.fs.removeDirTree(tmpcfgDir)
                    self.raiseError("uploadcfg","could not upload file %s to %s"%(ttype,dest))
            j.sal.fs.removeDirTree(tmpcfgDir)

    def upload(self,source,dest):
        args=j.admin.args
        if not j.sal.fs.exists(path=source):
            self.raiseError("upload","could not find path:%s"%source)
        self.log("upload","upload %s to %s"%(source,dest))
        # from IPython import embed
        # print "DEBUG NOW implement upload in Admin"  #@todo
        # embed()
    
        for item in items:
            partpath=j.sal.fs.pathRemoveDirPart(item,cfgDir)
            partpathdir=j.sal.fs.getDirName(partpath).rstrip("/")
            if partpathdir not in done:
                print((cuapi.dir_ensure("%s/%s"%(dest,partpathdir), True)))
                done.append(partpathdir)            
            cuapi.file_upload("%s/%s"%(dest,partpath),item)#,True,True)                       

    def __repr__(self):
        roles=",".join(self.roles)
        return ("%-10s %-10s %-50s %-15s %-10s %s"%(self.gridname,self.name,roles,self.ip,self.host,self.enabled))

    __str__=__repr__
