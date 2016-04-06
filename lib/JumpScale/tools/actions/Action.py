
from JumpScale import j
import time
import inspect
import traceback
import sys
import colored_traceback
import imp
import importlib

colored_traceback.add_hook(always=True)

import pygments.lexers
from pygments.formatters import get_formatter_by_name


class Action:
    def __init__(self, action=None,runid=0,actionRecover=None,args=(),kwargs={},die=True,stdOutput=True,errorOutput=True,retry=1,\
                serviceObj=None,deps=[],key="",selfGeneratorCode="",force=False,actionshow=True, async=False):
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
        @param serviceObj: service, will be used to get category filled in
        @param isparent, if isparent then when this action changes all actions following will be redone of same runid

        @param selfGeneratorCode is the code which gets evalled to return the object which is given to self, ...

        '''
        self.logger = j.logger.get("j.actions")

        if key=="" and action==None:
            raise j.exceptions.RuntimeError("need to specify key or action")

        self._args=""
        self._kwargs=""
        self._method = None
        self._result=""
        self._stdOutput=stdOutput
        self._errorOutput=errorOutput
        self._state="INIT"

        self.actionshow=actionshow

        #avoid we can write to it
        self._name=""
        self._path=""
        self.calling_path=""
        self.calling_linenr=0
        self._source=""
        self._doc=""

        self._state_show="INIT"
        self._selfobj="**NOTHING**"
        self._key=key
        self._depkeys=[]
        self._deps=[]
        self._actionRecover=""

        self._lastCodeMD5=""
        self._lastArgsMD5=""
        self.stdouterr=""
        self.error=""
        self.loglevel = 5
        self.retry=retry
        self.die=die
        self.force=force
        self.async = async

        self.traceback=""

        self.runid = str(runid)

        if action!=None:

            self.selfGeneratorCode=selfGeneratorCode

            self.args = args
            self.kwargs= kwargs

            self.serviceObj = serviceObj

            self.method=action

            if actionRecover!=None:
                self._actionRecover = actionRecover.key

        if key=="":
            if deps!=None:
                #remove deps which are None
                deps=[dep for dep in deps if dep!=None]

            if deps!=None and deps!=[]:
                #means they are specified
                self._deps=deps
                self._depkeys=[dep.key for dep in deps ]
            #DO NOT WANT THIS BEHAVIOUR ANY LONGER, should not automatically think previously defined actions are required, we need to define
            # elif deps==None:
            #     #need to grab last one if it exists
            #     if j.actions.last!=None:
            #         deps=[j.actions.last]
            #     else:
            #         deps=[]
            #     self._depkeys=[dep.key for dep in deps ]
            #     self._deps=deps
            else:
                if deps==None:
                    deps=[]
                self._deps=deps
                self._depkeys=[dep.key for dep in deps]

            self._load()
        else:
            self._load(True)

        self._parents=[]
        if len(j.actions.stack)>0:
            for actionstack in j.actions.stack:
                if actionstack.key not in self._parents:
                    self._parents.append(actionstack.key)
                    actionstack.addDep(self)

        if self.state=="INIT" and key=="":
            #is first time
            self.save(True)

    @property
    def state(self):
        if j.actions.showonly:
            return self._state_show
        else:
            return self._state

    @state.setter
    def state(self,val):
        if j.actions.showonly:
            self._state_show=val
        else:
            self._state=val

    @property
    def deps(self):
        if self._deps==[]:
            for depkey in self._depkeys:
                action=j.actions.actions[depkey]
                self._deps.append(action)
        return self._deps

    def getDepsAll(self):
        res=self._getDepsAll()
        if self.key in res:
            res.pop(res.index(self.key))
        res=[j.actions.get(key) for key in res]
        return res

    def _getDepsAll(self,res=None):
        if res==None:
            res=[]
        for key in self._depkeys:
            if key not in res:
                res.append(key)
            action=j.actions.get(key)
            res=action._getDepsAll(res)

        return res

    def getWhoDependsOnMe(self):
        res=[]
        for key,action in j.actions.actions.items():
            if self.key in action._getDepsAll():
                res.append(action)
        return res

    def changeStateWhoDependsOnMe(self,state):
        for action in self.getWhoDependsOnMe():
            action.state=state

    def addDep(self,action):
        if action.key not in self._depkeys:
            self._depkeys.append(action.key)
            self.save()

    @property
    def model(self):
        model = {}
        model["_name"] = self.name
        model["_key"] = self.key
        model["_doc"] = self.doc
        model["_path"] = self.path
        model["_state"] = self._state
        model["_lastArgsMD5"] = self._lastArgsMD5
        model["_lastCodeMD5"] = self._lastCodeMD5
        model["_depkeys"]=self._depkeys
        model["stdouterr"]=self.stdouterr
        model["_source"]=self._source
        model["_args"]=self._args
        model["_kwargs"]=self._kwargs
        model["_result"]=self._result
        model["_parents"]=self._parents
        model["error"]=self.error
        model["selfGeneratorCode"]=self.selfGeneratorCode
        model["runid"] = self.runid
        model["_state_show"] = self._state_show
        model["_actionRecover"] = self._actionRecover
        model["traceback"] = self.traceback
        model["die"] = self.die
        model["calling_path"] = self.calling_path
        model["calling_linenr"] = self.calling_linenr
        model["async"] = self.async

        return model

    @property
    def parents(self):
        return [j.actions.get(item) for item in self._parents]

    def _load(self,all=False):
        # print('load key %s' % self.key)
        data = j.core.db.hget("actions.%s" % self.runid, self.key)

        if data != None:
            data2 = j.data.serializer.json.loads(data)

            if all:
                data3=data2
            else:
                toload=["_state","_lastArgsMD5","_lastCodeMD5","_result","traceback","stdouterr", "async"]
                data3={}
                for item in toload:
                    data3[item]=data2[item]

            self.__dict__.update(data3)

            if self._result == "":
                self._result = None

        else:
            if self._key != "":
                raise j.exceptions.NotFound("could not load action:%s, was not in redis & key specified" % self._name)

    @property
    def actionRecover(self):
        if self._actionRecover==None or  self._actionRecover=="":
            return None
        return j.actions.get(self._actionRecover)

    def check(self):
        if j.data.hash.md5_string(self.source) != self._lastCodeMD5:
            self.state = "SOURCECHANGED"
            self.changeStateWhoDependsOnMe("SOURCEPARENTCHANGED")
            self.save()

        if j.data.hash.md5_string(self._args+self._kwargs) != self._lastArgsMD5:
            self.state = "ARGSCHANGED"
            self.changeStateWhoDependsOnMe("ARGSPARENTCHANGED")
            self.save()

    @property
    def method(self):
        if self.source=="":
            raise j.exceptions.RuntimeError("source cannot be empty")
        if self._method == None:
            # j.sal.fs.changeDir(basepath)
            loader = importlib.machinery.SourceFileLoader(self.name,self.sourceToExecutePath )
            handle = loader.load_module(self.name)
            self._method=eval("handle.%s"%self.name)

        return self._method

    @method.setter
    def method(self,val):
        source = "".join(inspect.getsourcelines(val)[0])
        if source != "" and source[-1] != "\n":
            source += "\n"
        if source.strip().startswith("@"):
            #decorator needs to be removed (first line)
            source="\n".join(source.split("\n")[1:])
        self._source=j.data.text.strip(source)
        self._name = source.split("\n")[0].strip().replace("def ", "").split("(")[0].strip()
        self._path = inspect.getsourcefile(val).replace("//", "/")
        self._doc=inspect.getdoc(self.method)
        if self._doc==None:
            self._doc=""
        if self._doc!="" and self._doc[-1]!="\n":
            self._doc+="\n"

    @property
    def sourceToExecute(self):
        s="""
        from JumpScale import j

        args=\"\"\"
        $args
        \"\"\"
        kwargs=\"\"\"
        $kwargs
        \"\"\"

        $source
        """
        #not used for now
        s2="""
        res=$name(*j.data.serializer.json.loads(args),**j.data.serializer.json.loads(kwargs))

        print ("**RESULT**")
        print (j.data.serializer.json.dumps(res,True,True))

        """
        s=j.data.text.strip(s)
        args=j.data.serializer.json.dumps(self.args,sort_keys=True, indent=True)
        kwargs=j.data.serializer.json.dumps(self.kwargs,sort_keys=True, indent=True)
        s=s.replace("$args",args)
        s=s.replace("$kwargs",kwargs)
        # source=""
        # lines=self.source.split("\n")
        # defline=lines[0]
        # end=defline.split("(",1)[1]
        # args=end.split(")",1)[0]
        # lines[0]=defline.replace(args,"*args,**kwargs")
        # source=",".join(lines)

        s=s.replace("$source",self.source)
        s=s.replace("$name",self.name)

        return s

    @property
    def sourceToExecutePath(self):
        path=j.sal.fs.joinPaths(j.dirs.tmpDir,"actions",self.runid,self.name+".py")
        j.do.writeFile(path,self.sourceToExecute)
        return path

    @property
    def depsAreOK(self):
        for action in self.deps:
            if action.state!="OK":
                return False
        return True

    @property
    def readyForExecute(self):
        self.check()
        if self.state !="OK" and self.state != 'ERROR' and self.depsAreOK:
            return True
        return False

    def save(self,checkcode=False):
        if checkcode:
            self._lastArgsMD5 = j.data.hash.md5_string(self._args+self._kwargs)
            self._lastCodeMD5 = j.data.hash.md5_string(self.source)
        j.core.db.hset("actions.%s" % self.runid, self.key, self.modeljson)

    @property
    def key(self):
        if self._key=="":
            extra=""
            key = "%s.%s.%s" % (self.path,self.name,self._args1line)
            # key = "%s.%s.%s" % (self.filename, self.name, self._args1line)
            return key
        else:
            return self._key

    @property
    def filename(self):
        return j.sal.fs.getBaseName(self.path)[:-3]

    @property
    def modeljson(self):
        return j.data.serializer.json.dumps(self.model, True, True)

    @property
    def doc(self):
        return self._doc

    @property
    def source(self):
        return self._source

    @property
    def name(self):
        return self._name

    @property
    def result(self):
        if self._result=="" or self._result==None:
            return None
        return j.data.serializer.json.loads(self._result)

    @result.setter
    def result(self,val):
        if val is None:
            self._result = ""
        else:
            self._result = j.data.serializer.json.dumps(val, True, True)

    @property
    def args(self):
        if self._args == "":
            return ()
        else:
            return j.data.serializer.json.loads(self._args)

    @args.setter
    def args(self,val):
        if val == ():
            self._args = ""
        else:
            self._args = j.data.serializer.json.dumps(val, True, True)

    @property
    def kwargs(self):
        if self._kwargs == "":
            return {}
        else:
            return j.data.serializer.json.loads(self._kwargs)

    @kwargs.setter
    def kwargs(self,val):
        if val == {}:
            self._kwargs = ""
        else:
            self._kwargs = j.data.serializer.json.dumps(val, True, True)

    @property
    def _args1line(self):
        out=""
        for arg in self.args:
            out+="%s,"%arg
        out=out.strip(",")
        out+="|"
        for key,arg in self.kwargs.items():
            out+="%s!%s,"%(key,arg)
        out=out.strip(",")
        args=out.strip()
        if len(args)>60:
            args=j.data.hash.md5_string(args)
        return args

    @property
    def _args10line(self):
        out=""
        for arg in self.args:
            out+="%s,"%arg
        out=out.strip(",")
        if len(self.kwargs.items())>0:
            out+=" | "
            for key,arg in self.kwargs.items():
                out+="%s:%s,"%(key,str(arg).strip())
        out=out.strip()
        out=out.strip(",|")
        out=out.strip()
        out=out.strip(",|")
        args=out.strip()
        if len(args)>120 or args.find("\n")!=-1:
            out=""
            if len(self.args)>0:
                argsdict={}
                counter=0
                for item  in self.args:
                    counter+=1
                    argsdict["arg%s"%counter]=item
                out+=str(j.data.hrd.getHRDFromDict(argsdict))
            if self.kwargs!={}:
                out+=str(j.data.hrd.getHRDFromDict(self.kwargs))
            out=out.replace("\n\n","\n")
            out=out.replace("\n\n","\n")
            out=out.replace("\n\n","\n")
            args="\n%s"%j.data.text.indent(out, nspaces=6, wrap=120, strip=True, indentchar=' ')
        return args

    @property
    def path(self):
        return self._path

    @property
    def selfobj(self):
        if self.selfGeneratorCode!="": #this is the code which needs to generate a selfobj
            try:
                l={}
                exec(self.selfGeneratorCode,globals(),l)
                self._selfobj=l["selfobj"]
            except Exception as e:
                # from pudb import set_trace; set_trace()
                self.error += "SELF OBJ ERROR:\n%s" % e
                self.state = "ERROR"
                self.save()
                self.print()
                raise j.exceptions.RuntimeError("error in selfobj in action:%s\nSelf obj code is:\n%s"%(self,self.selfGeneratorCode))

        return self._selfobj

    def execute(self):

        self.check() #see about changed source code
        j.actions.addToStack(self)

        if self.state == "OK" and self.force==False:
            if self.actionshow:
                self.logger.info("  * %-20s: %-80s (ALREADY DONE)" % (self.name, self._args1line))
            j.actions.delFromStack(self)
            return

        self.logger.info("  * %-20s: %s" % (self.name, self._args10line))

        if self._stdOutput == False:
            j.tools.console.hideOutput()

        if j.actions.showonly==False:
            rcode = 0
            output = ""
            counter=0
            ok=False
            err = ''

            while self.state!="ERROR" and ok==False and counter<self.retry+1:

                try:
                    if self.selfobj!="**NOTHING**":
                        #here we try to reconstruct the cuisine object@
                        self.result = self.method(self.selfobj,*self.args,**self.kwargs)
                    else:
                        self.result = self.method(*self.args,**self.kwargs)

                    ok=True
                    rcode=0
                    self.traceback=""
                except Exception as e:
                    # for line in traceback.format_stack():
                    #     if "/IPython/" in line:
                    #         continue
                    #     if "JumpScale/tools/actions" in line:
                    #         continue
                    #     if "ActionDecorator.py" in line:
                    #         continue
                    #     if "click/core.py" in line:
                    #         continue
                    #     # line=line.strip().strip("' ").strip().replace("File ","")
                    #     self.traceback+="%s\n"%line.strip()
                    # err=""

                    # from pudb import set_trace; set_trace()

                    tb=e.__traceback__
                    value=e
                    type=None

                    tblist=traceback.format_exception(type, value, tb)
                    tblist.pop(1)
                    self.traceback = "".join(tblist)

                    err=""
                    for e_item in e.args:
                        if isinstance(e_item, (set, list, tuple)):
                            e_item = ' '.join(e_item)
                        err+="%s\n"%e_item
                    counter+=1
                    time.sleep(0.1)
                    if self.retry>0:
                        # print("  RETRY, ERROR (%s/%s)" % (counter, self.retry))
                        self.logger.info("  RETRY, ERROR (%s/%s)" % (counter, self.retry))
                    rcode = 1

                    if "**NOSTACK**" in err:
                        self.traceback = ""
                        err=err.replace("**NOSTACK**","")

            #we did the retries, rcode will be >0 if error
            if self._stdOutput == False:
                j.tools.console.enableOutput()
                self.stdouterr += j.tools.console.getOutput()


            if rcode > 0 or self.state=="ERROR":
                if self.die:
                    for action in self.getWhoDependsOnMe():
                        if action.state=="ERRORCHILD":
                            continue #to avoid saving
                        # print ("#####%s"%self)
                        # print (action)
                        action.state="ERRORCHILD"
                        # print (action)
                        action.save()


                if self.actionRecover != None:
                    self.actionRecover.execute()

                if self.state=="ERRORCHILD":
                    j.actions.delFromStack(self)
                    #we are already in error, means error came from child
                    if self.die:
                        raise j.exceptions.RuntimeError("error in action: %s"%self)
                    return


                if err!="":
                    self.error = err

                self.state = "ERROR"
                self.print()
                self.save()

                #we are no longer in action, so remove
                j.actions.delFromStack(self)
                if self.die:
                    # if j.actions.stack==[]:
                    # print("error in action: %s"%self)
                    self.logger.error("error in action: %s"%self)
                    sys.exit(1)
                    # else:
                    #     raise j.exceptions.RuntimeError("error in action: %s"%self)
            else:
                self.state = "OK"


            #actions done so need to make sure current is None again
            j.actions.delFromStack(self)
            self.save(checkcode=True)
        else:
            rcode=0
            self.state="OK"
            self.save()

        return rcode

    def __str__(self):
        msg = "action: %-20s runid:%-15s (%s)\n    %s\n" % (self.name, self.runid, self.state,self._args10line)
        return msg

    @property
    def _stream(self):
        return sys.stderr
        # try:
        #     import colorama
        #     return colorama.AnsiToWin32(sys.stderr)
        # except ImportError:
        #     return sys.stderr

    @property
    def str(self):

    # def _str(self,formatter="term"):

        # if formatter="term":
        #     formatter=pygments.formatters.Terminal256Formatter(style=pygments.styles.get_style_by_name("vim"))

        # lexerpy = pygments.lexers.get_lexer_by_name("py3")#, stripall=True)
        # lexertb = pygments.lexers.get_lexer_by_name("pytb", stripall=True)

        # tb_colored = pygments.highlight(self.sourceToExecute, lexer, formatter)

        msg=""
        if self.state=="ERROR":
            msg += "*ERROR***********************************************************************************\n"
        msg += "action: %-20s runid:%-15s      (%s)\n" % (self.name, self.runid, self.state)
        if self.state=="ERROR":
            msg += "    %s\n"%self.key
            msg += "    path: %s\n" % self.path
        # if self.state=="ERROR":
        #     if self.source != "":
        #         msg += "SOURCE:\n"
        #         msg += j.data.text.indent(self.source) + "\n"
        #     if self.traceback != "":
        #         msg += "TRACEBACK:\n"
        #         msg += j.data.text.indent(self.traceback) + "\n"
        if self.doc != "":
            msg += "DOC:\n"
            msg += j.data.text.indent(self.doc)
            if msg[-1]!="\n":
                msg+="\n"
        # if self._args != "":
        #     msg += "ARGS:\n"
        #     msg += j.data.text.indent(self._args.strip())
        #     if msg[-1]!="\n":
        #         msg+="\n"
        # if self._kwargs != "":
        #     msg += "KWARGS:\n"
        #     msg += j.data.text.indent(self._kwargs.strip())
        #     if msg[-1]!="\n":
        #         msg+="\n"
        if self.stdouterr != "":
            msg += "OUTPUT:\n%s" % j.data.text.indent(self.stdouterr)
            if msg[-1]!="\n":
                msg+="\n"
        if self.result != None:
            msg += "RESULT:\n%s" % j.data.text.indent(str(self.result))
        if self.error != "":
            msg += "ERROR:\n%s" % j.data.text.indent(str(self.error))
            if msg[-1]!="\n":
                msg+="\n"
        if msg[-1]!="\n":
            msg+="\n"
        # if self.state=="ERROR":
        #     msg += "action: %-20s runid:%-15s      (%s)\n" % (self.name, self.runid, self.state)
        #     msg += "***ERROR***\n"
        out=""
        for line in msg.split("\n"):
            if line.strip()=="":
                continue
            out+="%s\n"%line

        if self.state=="ERROR":
            out="\n\n%s"%out
        return out

    def print(self):

        formatter=pygments.formatters.Terminal256Formatter(style=pygments.styles.get_style_by_name("vim"))

        lexer = pygments.lexers.get_lexer_by_name("bash")#, stripall=True)
        colored = pygments.highlight(self.str, lexer, formatter)
        print ("\n")
        self._stream.write(colored)


        if self.traceback!="":
            self.logger.error("\n*SOURCECODE******************************************************************************\n")

            """
            styles:
            'monokai', 'trac', 'borland', 'paraiso-dark', 'tango', 'bw', 'native', 'lovelace', 'algol_nu', 'vim', 'emacs', 'vs',
            'pastie', 'rrt', 'default', 'xcode', 'friendly', 'fruity', 'igor', 'colorful', 'paraiso-light', 'murphy', 'manni', 'autumn', 'perldoc', 'algol'
            """


            lexer = pygments.lexers.get_lexer_by_name("py3")#, stripall=True)
            tb_colored = pygments.highlight(self.sourceToExecute, lexer, formatter)
            self._stream.write(tb_colored)

            self.logger.error("\n*TRACEBACK*********************************************************************************\n")

            lexer = pygments.lexers.get_lexer_by_name("pytb", stripall=True)
            tb_colored = pygments.highlight(self.traceback, lexer, formatter)
            self._stream.write(tb_colored)

        self.logger.error("\n\n******************************************************************************************\n")


    __repr__ = __str__
