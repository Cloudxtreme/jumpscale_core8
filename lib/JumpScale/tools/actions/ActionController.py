
# import sys
# import inspect
# import textwrap
# import operator

from JumpScale import j
from Action import *
import traceback

class ActionController(object):
    '''Manager controlling actions'''
    def __init__(self, _output=None, _width=70):
        self.__jslocation__ = "j.actions"
        self.logger = j.logger.get("j.actions")
        # self._actions = list()
        # self._width = _width
        self.rememberDone = False
        self._actions = {}
        self.lastOnes=[]
        self.last = None
        self._runid = j.core.db.get("actions.runid").decode() if j.core.db.exists("actions.runid") else None
        showonly = j.core.db.hget("actions.showonly", self._runid)
        if showonly is None:
            self._showonly = False
        else:
            self._showonly = showonly.decode() == "1"

    def setRunId(self, runid,reset=False):
        self._runid = str(runid)
        j.core.db.set("actions.runid", self._runid.encode())
        if reset:
            j.core.db.delete("actions.%s"%self.runid)

    def load_action(self, runid, key):
        if runid.startswith('actions.'):
            runid = runid[len('actions.'):]
        return Action(runid=runid, key=key)

    @property
    def showonly(self):
        return self._showonly

    @showonly.setter
    def showonly(self,val):
        if val=="1" or val==1 or val:
            j.core.db.hset("actions.showonly",self._runid,"1".encode())
            self._showonly=True
        else:
            j.core.db.hset("actions.showonly",self._runid,"0".encode())
            self._showonly=False

    @property
    def runid(self):
        runid = j.core.db.get('actions.runid')
        if not runid:
        # if self._runid=="" or self._runid==None:
            raise j.exceptions.RuntimeError("runid cannot be empty, please set with j.actions.setRunID(...)")
        return str(runid.decode())
        # return str(self._runid)

    def get(self,actionkey):
        return self.actions[actionkey]


    def reset(self, all=False, item=None):
        if all is True:
            for item in j.core.db.keys("actions.*"):
                item = item.decode().split(".", 1)[1]
                self.logger.info("delete:%s" % item)
                self.reset(item=item)
        else:
            self._actions = {}
            if item is None:
                j.core.db.delete("actions.%s"%self.runid)
            else:
                j.core.db.delete("actions.%s"%item)

    def resetAll(self):
        self.reset(True)

    def setState(self,state="INIT"):
        for key,action in self.actions.items():
            action.state=state
            action.save()

    def selectAction(self):
        return j.tools.console.askChoice(j.actions.actions)

    def add(self, action,actionRecover=None,args=(),kwargs={},die=True,stdOutput=False,errorOutput=True,retry=0,serviceObj=None,deps=None,executeNow=True,selfGeneratorCode="",force=True,showout=None,actionshow=True):
        '''
        self.doc is in doc string of method
        specify recover actions in the description

        name is name of method

        @param name if you want to overrule the name

        @param id is unique id which allows finding back of action
        @param loglevel: Message level
        @param action: python function to execute
        @param actionRecover: link to other action (same as this object but will be used to recover the situation)
        @param args is dict with arguments
        @param serviceObj: service, will be used to get category filled in e.g. selfGeneratorCode='selfobj=None'
            needs to be done selfobj=....  ... is whatever code which fill filling selfobj
        '''

        # from pudb import set_trace; set_trace()

        if showout==True:
            stdOutput=True
        if showout==False:
            stdOutput=False

        l=traceback.format_stack()
        tbline=l[-2].split("\n")[0].replace("'","")
        fpath,linenr,remaining=tbline.split(",",2)
        fpath=fpath.split("\"")[1].strip()
        linenr=int(linenr.split(" ")[-1])


        if j.data.types.dict.check(args):
            raise j.exceptions.RuntimeError("cannot create action: args should be a list, kwargs a dict, input error")

        action=Action(action,runid=self.runid,actionRecover=actionRecover,args=args,kwargs=kwargs,die=die,stdOutput=stdOutput,errorOutput=errorOutput,\
            retry=retry,serviceObj=serviceObj,deps=deps,selfGeneratorCode=selfGeneratorCode,force=force,actionshow=actionshow)

        action.calling_linenr=linenr
        action.calling_path=fpath


        while len(self.lastOnes)>100:
            self.lastOnes.pop()
        self.lastOnes.append(action)

        self._actions[action.key]=action
        self.last=action
        if executeNow:
            # print ("ACTION ADD:%s"%action.key)
            action.execute()
        else:
            action.save(True)
        return action

    def addToStack(self,action):
        if action not in self.stack:
            self.stack.append(action)

    def delFromStack(self,action):
        if action in self.stack:
            self.stack.pop(self.stack.index(action))

    @property
    def stack(self):
        val=j.core.db.hget("actions.stack",self.runid)
        if val==None:
            val2=[]
        else:
            val2=j.data.serializer.json.loads(val)
        return val2

    @stack.setter
    def stack(self,val):
        val2=j.data.serializer.json.dumps(val)
        j.core.db.hset("actions.stack",self.runid,val2)

    def start(self, action,actionRecover=None,args={},die=True,stdOutput=False,errorOutput=True,retry=1,serviceObj=None,deps=[]):
        """
        same as add method but will execute immediately
        """
        self.add(action,actionRecover=actionRecover,args=args,die=die,stdOutput=stdOutput,errorOutput=errorOutput,retry=retry,serviceObj=serviceObj,deps=deps,executeNow=True)

    def gettodo(self):
        todo=[]
        for key,action in self.actions.items():
            if action.readyForExecute:
                todo.append(action)
        return todo

    def run(self, agentcontroller=False):
        todo = self.gettodo()
        step = 0
        while todo:
            step += 1
            self.logger.info("STEP:%s" % step)
            for action in todo:
                action.execute()
                if action.state == "ERROR":
                    raise j.exceptions.RuntimeError("cannot execute run:%s, failed action." % (action.runid))
            todo = self.gettodo()

    @property
    def actions(self):
        # if self._actions == {}:
        if not self._runid:
            return {}

        for key in j.core.db.hkeys("actions.%s" % self.runid):
            a = Action(runid=self.runid, key=key)
            self._actions[a.key] = a

        # return self._actions

    # def showAll(self):
    #     self.showonly=True

    #     self.showonly=False



    # def showCompleted(self):
    #     pass

    # def hasRunningActions(self):
    #     '''Check whether actions are currently running

    #     @returns: Whether actions are runnin
    #     @rtype: bool
    #     '''
    #     return bool(self._actions)
