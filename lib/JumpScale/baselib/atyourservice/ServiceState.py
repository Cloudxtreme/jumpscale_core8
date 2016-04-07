from JumpScale import j


class StateItem():
    def __init__(self, states,name,state="INIT",period=0,last=0,actionmethod_hash="",hrd_hash=""):
        self.states = states
        self.name = name
        self._period = period
        self._last = last
        self._state= state #INIT,ERROR,OK,DISABLED,DO,CHANGED  DO means: execute the action method as fast as you can, init means it has not been started yet ever
        self._action = None #is key of action
        self._actionmethod_hash=actionmethod_hash
        self._hrd_hash=hrd_hash
        self.changed=False

    def __repr__(self):
        if self.last != 0:
            return str("| %-20s | %-10s | %-10s | %-30s |\n" % (self.name,self.state,self.period,j.data.time.epoch2HRDateTime(self.last)))
        else:
            return str("| %-20s | %-10s | %-10s | %-30s |\n" % (self.name,self.state,self.period,""))

    def check(self):
        if self.periodSec>0:
            now=j.data.time.getTimeEpoch()
            if self.last<now-self.periodSec:
                #need to execute
                self.service._executeOnNode("execute",cmd=self.name)


    @property
    def period(self):
        return self._period

    @period.setter
    def period(self,val):
        if val!=self._period:
            self._period=val
            if self.period==None or self.period==0:
                self.periodSec =0
            else:
                self.periodSec = j.data.time.getDeltaTime(self.period)
            self.changed=True

    @property
    def last(self):
        return self._last

    @last.setter
    def last(self,val):
        if val!=self._last:
            self._last=val
            self.changed=True

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self,val):
        if val not in ["INIT","ERROR","OK","DISABLED","DO","CHANGED"]:
            raise j.exceptions.RuntimeError("state can only be INIT,ERROR,OK,DISABLED,DO,CHANGED")
        if val!=self._state:
            self._state=val
            self.changed=True

    @property
    def actionmethod_hash(self):
        return self._actionmethod_hash

    @actionmethod_hash.setter
    def actionmethod_hash(self,val):
        if val!=self._actionmethod_hash:
            self._actionmethod_hash=val
            self.changed=True

    @property
    def hrd_hash(self):
        return self._hrd_hash

    @hrd_hash.setter
    def hrd_hash(self,val):
        if val!=self._hrd_hash:
            self._hrd_hash=val
            self.changed=True

    @property
    def action(self):
        from IPython import embed
        print ("DEBUG NOW action get state item")
        embed()

    @property
    def model(self):
        data={}
        data["state"]=self.state
        data["period"]=self.period
        data["last"]=self.last
        data["hrd_hash"]=self.hrd_hash
        data["actionmethod_hash"]=self.actionmethod_hash
        return data

    def __str__(self):
        return self.__repr__()


class ServiceState():
    def __init__(self, service):
        self.service = service
        self.logger = j.logger.get('j.atyourservice.state.%s' % service.key.short)

        if self.service.path == "" or self.service.path is None:
            raise j.exceptions.RuntimeError("path cannot be empty")

        self.path = j.sal.fs.joinPaths(self.service.path, "state.md")
        self.items={}
        self._read()

    def reload(self):
        self._read()

    def getSet(self,methodname,state="INIT"):
        if not methodname in self.items:
            self.items[methodname]=StateItem(self,methodname,state=state)
        return self.items[methodname]

    def set(self,methodname,state):
        state=StateItem(self,methodname,state=state)
        self.items[methodname]=state

    def addRecurring(self, name, period):
        stateitem=self.getSet(name)
        stateitem.period=period

    def check(self):
        """
        walks over the recurring items and if too old will execute
        """
        for key, obj in self.items.items():
            obj.check()

    def _read(self):
        pastHeader = False
        out=""
        if j.sal.fs.exists(path=self.path):

            for line in j.sal.fs.fileGetContents(self.path).split("\n"):
                if pastHeader and line.find("```") != -1:
                    break

                if not pastHeader and line.find("```") != -1:
                    pastHeader = True
                    continue

                if pastHeader:
                    out+="%s\n"%line

            obj=j.data.serializer.json.loads(out)

            for key,val in obj.items():
                self.items[key]=StateItem(self,key,state=val["state"],period=val["period"],last=val["last"],\
                    actionmethod_hash=val["actionmethod_hash"],hrd_hash=val["hrd_hash"])

        else:
            self.items = {}


    @property
    def model(self):
        ddict={}
        for key, obj in self.items.items():
            ddict[key]=obj.model
        return ddict

    @property
    def wiki(self):
        out=""
        out = "## actionmethods\n\n"
        out += "| %-20s | %-10s | %-10s | %-30s |\n" % ("name", "state","period", "last")
        out += "| %-20s | %-10s | %-10s | %-30s |\n" % ("---", "---","---", "---")
        for key, obj in self.items.items():
            out += "%s" % obj
        return out

    def save(self):
        changed=False
        for key, obj in self.items.items():
            if obj.changed:
                changed=True
                break

        if changed==False:
            return

        self.logger.debug(" - write state: %s" % self.service)
        out=str(self.wiki)
        out+="\n\n```\n"
        out+=j.data.serializer.json.dumps(self.model,True,True)
        out+="\n```\n"
        j.sal.fs.writeFile(filename=self.path, contents=out)

    def __repr__(self):
        return str(self.wiki)

    def __str__(self):
        return self.__repr__()
