from JumpScale import j


from MonitorTools import *


class NodeBase(MonitorTools):
    def __init__(self,ipaddr,sshport=22,role=None,name=""):
        """
        existing roles
        - vnas
        - monitor
        - host

        """
        if j.tools.perftesttools.monitorNodeIp==None:
            raise j.exceptions.RuntimeError("please do j.tools.perftesttools.init() before calling this")

        self.influx_host = j.tools.perftesttools.monitorNodeIp
        self.influx_port = 8086
        self.influx_login = 'root'
        self.influx_password = 'root'

        self.redis_host = j.tools.perftesttools.monitorNodeIp
        self.redis_port = 9999
        self.redis_login = 'root'
        self.redis_password = 'root'

        self._redis = None


        self.key=j.tools.perftesttools.sshkey
        self.name=name

        self.ipaddr=ipaddr
        self.sshport = sshport

        self.debug=False

        print("ssh init %s"%self)
        self.ssh = j.remote.cuisine.connect(ipaddr, sshport)
        if self.key and self.key != '':
            self.fabric.env["key"] = self.key
        print("OK")

        self.role=role

    @property
    def redis(self):
        if self._redis is not None:
            return self._redis
        print("connect redis: %s:%s"%(j.tools.perftesttools.monitorNodeIp, 9999))
        self._redis = j.clients.redis.get(self.redis_host, self.redis_port)


    def setInfluxdb(self, host, port, login='root', password='root'):
        self.influx_host = host
        self.influx_port = port
        self.influx_login = login
        self.influx_password = password

    def setRedis(self, host, port, login='root', password='root'):
        self.redis_host = host
        self.redis_port = port
        self.redis_login = login
        self.redis_password = password


    def startMonitor(self,cpu=1,disks=[],net=1):
        if not j.data.types.list.check(disks):
            disks = [disks]
        disks=[str(disk) for disk in disks]
        self.prepareTmux("mon%s"%self.role,["monitor"])
        env={}
        if j.tools.perftesttools.monitorNodeIp==None:
            raise j.exceptions.RuntimeError("please do j.tools.perftesttools.init() before calling this")
        env["redishost"] = self.redis_host
        env["redisport"] = self.redis_port
        env["cpu"] = cpu
        env["disks"] = ",".join(disks)
        env["net"] = net
        env["nodename"] = self.name
        self.executeInScreen("monitor", "js 'j.tools.perftesttools.monitor()'", env=env)

    def execute(self,cmd, env={},dieOnError=True,report=True):
        if report:
            print(cmd)

        if not dieOnError:
            with warn_only():
                res = self.ssh.run(cmd)
        else:
            res = self.ssh.run(cmd)

        return res

    def prepareTmux(self,session,screens=["default"],kill=True):
        print("prepare tmux:%s %s %s"%(session,screens,kill))
        if len(screens)<1:
            raise j.exceptions.RuntimeError("there needs to be at least 1 screen specified")
        if kill:
            self.execute("tmux kill-session -t %s"%session, dieOnError=False)

        self.execute("tmux new-session -d -s %s -n %s"%(session,screens[0]), dieOnError=True)

        screens.pop(0)

        for screen in screens:
            print("init tmux screen:%s"%screen)
            self.execute("tmux new-window -t '%s' -n '%s'" %(session,screen))

    def executeInScreen(self,screenname,cmd,env={},session=""):
        """
        gets executed in right screen for the disk
        """
        envstr="export "
        if env!={}:
            #prepare export arguments
            for key,val in env.items():
                envstr+="export %s=%s;"%(key,val)
            envstr=envstr.strip(";")
        cmd1="cd /tmp;%s;%s"%(envstr,cmd)
        cmd1=cmd1.replace("'","\"")
        windowcmd=""
        if session!="":
            windowcmd="tmux select-window -t \"%s\";"%session
        cmd2="%stmux send-keys -t '%s' '%s\n'"%(windowcmd,screenname,cmd1)
        # print cmd2
        print("execute:'%s' on %s in screen:%s/%s"%(cmd1,self,session,screenname))
        self.execute(cmd2,report=False)

    def __str__(self):
        return "node:%s"%self.ipaddr

    def __repr__(self):
        return self.__str__()
