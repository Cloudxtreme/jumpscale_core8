from JumpScale import j

from ServiceKey import ServiceKey

from contextlib import redirect_stdout
import io
import imp
import sys
from Recurring import Recurring
from ServiceState import ServiceState


def loadmodule(name, path):
    parentname = ".".join(name.split(".")[:-1])
    sys.modules[parentname] = __package__
    mod = imp.load_source(name, path)
    return mod

def getProcessDicts(service, args={}):
    counter = 0

    defaults = {"prio": 10, "timeout_start": 10,
                "timeout_start": 10, "startupmanager": "tmux"}
    musthave = ["cmd", "args", "prio", "env", "cwd", "timeout_start",
                "timeout_start", "ports", "startupmanager", "filterstr", "name", "user"]

    procs = service.recipe.hrd.getListFromPrefixEachItemDict("process", musthave=musthave, defaults=defaults, aredict=[
                                                   'env'], arelist=["ports"], areint=["prio", "timeout_start", "timeout_start"])
    for process in procs:
        counter += 1

        process["test"] = 1

        if "name" not in process or process["name"].strip() == "":
            process["name"] = "%s_%s" % (service.name, service.instance)

        if service.recipe.hrd.exists("env.process.%s" % counter):
            process["env"] = service.recipe.hrd.getDict("env.process.%s" % counter)

        if not isinstance(process["env"], dict):
            raise j.exceptions.RuntimeError("process env needs to be dict")

    return procs


class Service:

    def __init__(self, servicerecipe=None, instance=None, path="", args=None, parent=None, originator=None):
        """
        @param consume is in format $role!$instance,$role2!$instance2
        """
        self.logger = j.logger.get('j.atyourservice.service')

        self.originator = originator
        j.logger.get('j.atyourservice.service')

        self._domain = None
        self._name = None
        self._instance = None
        self._version = None

        self._recipe = None

        key_input = None
        if path != "" and j.sal.fs.exists(path):
            key_input = j.sal.fs.getBaseName(path)
            self._rememberActions = True
        else:
            if j.data.types.string.check(servicerecipe):
                raise j.exceptions.RuntimeError("no longer supported, pass servicerecipe")
            assert servicerecipe, "service recipe cannot be None if path not specified"
            assert instance, "instance needs to be specified"
            assert path, "path needs to be specified of service"
            key_input = servicerecipe
            self._recipe = servicerecipe
            self._rememberActions = False

        self.key = ServiceKey.parse(key_input)
        self.key.instance = instance if instance else self.key.instance
        self._domain = self.key.domain
        self._name = self.key.name
        self._instance = self.key.instance
        self._version = self.key.version

        self._parent = ""
        self._parentChain = None
        if parent is not None:
            self.path = j.sal.fs.joinPaths(parent.path, str(parent.key))
            self._parent = str(parent.key)

        self.path = path.rstrip("/")

        self._hrd = None
        self._hrd_hash = None
        self._yaml = None
        self._mongoModel = None

        self._action_methods = None
        self._action_methods_node = None

        self._dnsNames = []

        self.args = args or {}
        self._producers = {}
        self.cmd = None
        self._logPath = None

        if self.path == "" or self.path is None:
            raise j.exceptions.RuntimeError("cannot be empty")

        self._init = False

        self._state = None

        self._executor = None

    @property
    def name(self):
        if self._name is None:
            self._name=self.hrd.get("service.name")
        return self._name

    @property
    def instance(self):
        if self._instance is None:
            self._instance = self.key.instance
        return self._instance

    @property
    def role(self):
        return self.key.role

    @property
    def version(self):
        if self._version is None:
            self._version=self.hrd.get("service.version", '0.1')
        return self._version

    @property
    def domain(self):
        if self._domain is None:
            self._domain=self.hrd.get("service.domain")
        return self._domain

    @property
    def recipe(self):
        if self._recipe is None:
            self._recipe=j.atyourservice.getRecipe(domain=self.domain, name=self.name, version=self.version)
        return self._recipe

    @property
    def dnsNames(self):
        if self._dnsNames == []:
            self._dnsNames = self.hrd.getList("dns")
        return self._dnsNames

    @property
    def parents(self):
        if self._parentChain ==None:
            chain = []
            parent = self.parent
            while parent is not None:
                chain.append(parent)
                parent = parent.parent
            self._parentChain = chain
        return self._parentChain

    @property
    def parent(self):
        if isinstance(self._parent, str):
            if j.sal.fs.exists(j.sal.fs.joinPaths(self.path, "instance.hrd")) and self.hrd.exists("parent"):
                key = ServiceKey.parse(self.hrd.get("parent"))
                self._parent = j.atyourservice.getService(name=key.name, role=key.role, instance=key.instance)
            else:
                self._parent = None
        return self._parent

    @property
    def hrd(self):
        if self._hrd is None:
            hrdpath = j.sal.fs.joinPaths(self.path, "instance.hrd")
            self._hrd = j.data.hrd.get(hrdpath, prefixWithName=False)
        return self._hrd

    @property
    def hrdhash(self):
        if self._hrd_hash is None:
            self._hrd_hash = j.data.hash.md5_string(str(self.hrd))
        return self._hrd_hash

    @property
    def yaml(self):
        if self._yaml is None:
            path = j.sal.fs.joinPaths(self.path, "model.yaml")
            if j.sal.fs.exists(path):
                self._yaml = j.data.serializer.yaml.load(path)
        return self._yaml

    @property
    def mongoModel(self):
        if self._mongoModel is None:
            self._mongoModel = self.recipe.model
            if self.yaml:
                for k, v in self.yaml.items():
                    if k in self._mongoModel:
                        self._mongoModel[k] = v
        return self._mongoModel

    @property
    def state(self):
        if self._state==None:
            self._state=ServiceState(self)
        return self._state

    @property
    def actions(self):
        if self._action_methods is None:
            self.logger.debug("reload mgmt actions for %s" % self)
            action_methods = self._loadActions(self.recipe.path_actions,"mgmt")
            self._action_methods = action_methods
        return self._action_methods

    def _getActionMethodMgmt(self, action):
        try:
            method = eval("self.action_methods_mgmt.%s" % action)
        except Exception as e:
            if str(e).find("has no attribute") != -1:
                return None
            raise j.exceptions.RuntimeError(e)
        return method

    def _getActionMethodNode(self, action):
        try:
            method = eval("self.action_methods_node.%s" % action)
        except Exception as e:
            if str(e).find("has no attribute") != -1:
                return None
            raise j.exceptions.RuntimeError(e)
        return method

    def _loadActions(self, path, ttype):
        if j.sal.fs.exists(path+'c'):
            j.sal.fs.remove(path+'c')
        if j.sal.fs.exists(path):
            j.sal.fs.createDir(j.sal.fs.getDirName(path))
            path2 = j.sal.fs.joinPaths(self.path, j.sal.fs.getBaseName(path))
            # need to create a copy of the recipe mgmt or node action class
            j.sal.fs.copyFile(path, path2)
            if self.hrd is not None:
                self.hrd.applyOnFile(path2)
            j.application.config.applyOnFile(path2)
        else:
            j.events.opserror_critical(msg="can't find %s." % path, category="ays loadActions")

        modulename = "JumpScale.atyourservice.%s.%s.%s.%s" % (self.domain, self.name, self.instance, ttype)
        mod = loadmodule(modulename, path2)
        # is only there temporary don't want to keep it there
        actions = mod.Actions()
        return actions

    def cleanOnRepo(self):
        j.sal.fs.removeDirTree(j.do.joinPaths(self.path, "__pycache__"))
        j.sal.fs.remove(j.sal.fs.joinPaths(self.path, "actions_node.py"))

    @property
    def producers(self):
        if self._producers is None or self._producers == {}:
            self._producers={}
            for role, items in self.hrd.getDictFromPrefix("producer").items():
                producerSet = set()
                for item in items:
                    key = ServiceKey.parse(item)
                    service = j.atyourservice.getService(name=key.name, instance=key.instance)
                    producerSet.add(service)

                self._producers[role] = list(producerSet)

            if self.parent is not None:
                self._producers[self.parent.role] = [self.parent]

        return self._producers

    @property
    def executor(self):
        if self._executor is None:
            self._executor = self._getExecutor()
        return self._executor

    def save(self):
        self.state.save()

    def init(self, yaml=None):
        def _initParent():
            parent = self.recipe.schema.parentSchemaItemGet()

            if parent != None:
                # parent exists
                name = parent.parent
                role = name

                if '.' in name:
                    role = name.split('.', 1)[0]

                if role in self.args:
                    # has been speficied or empty
                    rolearg = self.args[role].strip()
                else:
                    rolearg = ""

                if rolearg == "":
                    if role != name:
                        ays_s = j.atyourservice.findServices(name=name)
                    else:
                        ays_s = j.atyourservice.findServices(role=role)

                    if len(ays_s) == 1:
                        # we found 1 service of required role, will take that one
                        aysi = ays_s[0]
                        rolearg = aysi.instance
                        self.args[role] = rolearg
                    elif len(ays_s) > 1:
                        raise j.exceptions.RuntimeError("Found more than one parent candidate with role '%s' for service '%s" % (role, self))
                    else:
                        if parent.auto:
                            ays_s = [j.atyourservice.new(name=parent.parent, instance='main', version='', domain='', path=None, parent=None, args={}, consume='')]
                            rolearg = "main"
                        else:
                            raise j.exceptions.RuntimeError("Cannot find parent with role '%s' for service '%s, there is none, please make sure the service exists."%(role, self))

                self._parent = ays_s[0]
                self.path = j.sal.fs.joinPaths(self.parent.path, str(self))

            j.sal.fs.createDir(self.path)


        if self._init is False:
            self.logger.info('INIT service: %s' % self)

            self._hrd_hash = None

            # make sure yaml is written again, which means changes will be detected
            if yaml is not None:
                yamlpath = j.sal.fs.joinPaths(self.path, "model.yaml")
                if not j.sal.fs.exists(yamlpath):
                    j.sal.fs.touch(yamlpath)
                j.data.serializer.yaml.dump(yamlpath, yaml)

            # see if we can find parent if specified (potentially based on role)
            if not self.parent:
                _initParent()

            # run the args manipulation action as an action
            self.args = self.actions.input(self.name, self.role, self.instance, self.args)

            hrdpath = j.sal.fs.joinPaths(self.path, "instance.hrd")

            self._manipulateArgs()

            # if no schema.hrd exists in servicetemplate, raw yaml will be used as datasource
            # we just create en empty instance.hrd
            self._hrd = self.recipe.schema.hrdGet(hrd=self.hrd, args=self.args, path=hrdpath)

            if self.recipe.hrd is not None:
                # apply values from recipe hrd to this hrd
                self.hrd.applyTemplate(self.recipe.hrd)
            self.hrd.prefixWithName = False
            self.hrd.set("service.name", self.name)
            self.hrd.set("service.version", self.version)
            self.hrd.set("service.domain", self.domain)
            self.hrd.set("service.role", self.role)
            self.hrd.set("service.instance", self.instance)

            if self.parent is not None:
                self.hrd.set("parent", self.parent.key.__str__())
                self.consume(self.parent)

            self._manipulateHRD()

            self._action_methods = None  # to make sure we reload the actions

            self.actions.init()

            for item in self.hrd.prefix("recurring"):
                recurringName = item.split(".")[1]
                recurringPeriod = self.hrd.getStr(item).strip("\"")
                self.state.addRecurring(recurringName, recurringPeriod)

            for key, _ in self.recipe.actionmethods.items():
                self.state.getSet(key)

            self.state.save()
            self.cleanOnRepo()

        self._init = True

    def _manipulateArgs(self):

        def exists(args, name):
            x = name not in args or args[name] is None or args[name] == ""
            return not x

        # fill in node.tcp.address
        if self.name.startswith("node"):
            # set service name & ip addr
            if not exists(self.args, 'node.tcp.addr') or self.args['node.tcp.addr'].find('@ask')!=-1:
                if "ip" in self.args:
                    self.args['node.tcp.addr'] = self.args["ip"]

            if not exists(self.args, 'node.name'):
                self.args['node.name'] = self.instance

    def _manipulateHRD(self):
        # manipulate the HRD's to mention the consume's to producers
        consumes = self.recipe.schema.consumeSchemaItemsGet()

        if consumes:
            for consumeitem in consumes:
                # parent exists
                name = consumeitem.consume_link
                role = name.split('.')[0]
                consumename = consumeitem.name

                instancenames = []
                if consumename in self.args:
                    instancenames = self.args[consumename]

                ays_s = list()
                if role != name:
                    candidates = j.atyourservice.findServices(name=consumeitem.consume_link)
                else:
                    candidates = j.atyourservice.findServices(role=consumeitem.consume_link)
                if candidates:
                    if instancenames:
                        ays_s = [candidate for candidate in candidates if candidate.instance in instancenames]
                    else:
                        ays_s = candidates

                # autoconsume
                if len(candidates) < int(consumeitem.consume_nr_min) and consumeitem.auto:
                    for instance in range(len(candidates), int(consumeitem.consume_nr_min)):
                        consumable = j.atyourservice.new(name=consumeitem.consume_link, instance='auto_%i' % instance, parent=self.parent)
                        ays_s.append(consumable)

                if len(ays_s) > int(consumeitem.consume_nr_max):
                    raise j.exceptions.RuntimeError("Found too many services with role '%s' which we are relying upon for service '%s, max:'%s'" % (role, self, consumeitem.consume_nr_max))
                if len(ays_s) < int(consumeitem.consume_nr_min):
                    msg = "Found not enough services with role '%s' which we are relying upon for service '%s, min:'%s'" % (role, self, consumeitem.consume_nr_min)
                    if len(ays_s) > 0:
                        msg += "Require following instances:%s" % self.args[consumename]
                    raise j.exceptions.RuntimeError(msg)

                for ays in ays_s:
                    if role not in self.producers:
                        self._producers[role] = []
                    if ays not in self._producers[role]:
                        self._producers[role].append(ays)

            for key, services in self._producers.items():
                producers = []
                for service in services:
                    if service.key not in producers:
                        producers.append(service.key.__str__())

                self.hrd.set("producer.%s" % key, producers)

    def consume(self, input):
        """
        @input is comma separate list of ayskeys or a Service object or list of Service object

        ayskeys in format $domain|$name:$instance@role ($version)

        example
        ```
        @input $domain|$name!$instance,$name2!$instance2,$name2,$role4
        ```

        """
        if input is not None and input is not '':
            toConsume = set()
            if j.data.types.string.check(input):
                entities = input.split(",")
                for entry in entities:
                    service = j.atyourservice.getServiceFromKey(entry.strip())
                    toConsume.add(service)

            elif j.data.types.list.check(input):
                for service in input:
                    toConsume.add(service)

            elif isinstance(input, Service):
                toConsume.add(input)
            else:
                j.events.inputerror_critical("Type of input to consume not valid. Only support list, string or Service object", category='AYS.consume', msgpub='Type of input to consume not valid. Only support list, string or Service object')

            for service in toConsume:
                if service.role not in self._producers:
                    self._producers[service.role] = [service]
                else:
                    prodSet = set(self._producers[service.role])
                    prodSet.add(service)
                    self._producers[service.role] = list(prodSet)

            for role, services in self._producers.items():
                producers = set()
                for service in services:
                    producers.add(str(service.key))
                self.hrd.set("producer.%s" % role, list(producers))

            # walk over the producers
            # for producer in toConsume:
            method = self._getActionMethodMgmt("consume")
            if method:
                # j.atyourservice.alog.setNewAction(self.role, self.instance, "mgmt","consume")
                self.runAction('consume')
                # self.action_methods.consume(producer)
                # j.atyourservice.alog.setNewAction(self.role, self.instance, "mgmt","consume","OK")

    def getProducersRecursive(self, producers=set(), callers=set()):
        for role, producers2 in self.producers.items():
            for producer in producers2:
                producers.add(producer)
                producers = producer.getProducersRecursive(producers, callers=callers)
        return producers.symmetric_difference(callers)

    def printProducersRecursive(self,prefix=""):
        for role, producers2 in self.producers.items():
            # print ("%s%s"%(prefix,role))
            for producer in producers2:
                print ("%s- %s"%(prefix,producer))
                producer.printProducersRecursive(prefix+"  ")


    def getProducersWaiting(self, action="install",producersChanged=set()):
        """
        return list of producers which are waiting to be executing the action
        """
        for producer in self.getProducersRecursive(set(), set()):
            actionrunobj = producer.state.getSet(action)
            if actionrunobj.state != "OK":
                producersChanged.add(producer)
        return producersChanged

    def getNode(self):
        for parent in self.parents:
            if 'ssh' == parent.role:
                return parent
        return None

    def isOnNode(self, node=None):
        mynode = self.getNode()
        if mynode is None:
            return False
        return mynode.key == node.key

    def getTCPPorts(self, processes=None, *args, **kwargs):
        ports = set()
        if processes is None:
            processes = self.getProcessDicts()
        for process in self.getProcessDicts():
            for item in process.get("ports", []):
                if isinstance(item, str):
                    moreports = item.split(";")
                elif isinstance(item, int):
                    moreports = [item]
                for port in moreports:
                    if isinstance(port, int) or port.isdigit():
                        ports.add(int(port))
        return list(ports)

    def getPriority(self):
        processes = self.getProcessDicts()
        if processes:
            return processes[0].get('prio', 100)
        return 199

    def getProcessDicts(self, args={}):
        return getProcessDicts(self, args={})

    def _downloadFromNode(self):
        # if 'os' not in self.producers or self.executor is None:
        if not self.parent or self.parent.role != 'ssh':
            return

        hrd_root = "/etc/ays/local/"
        remotePath = j.sal.fs.joinPaths(hrd_root, j.sal.fs.getBaseName(self.path), 'instance.hrd')
        dest = self.path.rstrip("/")+"/"+"instance.hrd"
        self.logger.info("downloading %s '%s'->'%s'" % (self.key, remotePath, self.path))
        self.executor.download(remotePath, self.path)

    def _getExecutor(self):
        executor = None
        for parent in self.parents:
            if hasattr(parent.actions, 'getExecutor'):
                executor = parent.actions.getExecutor()
                return executor
        return j.tools.executor.getLocal()

    def listChildren(self):
        childDirs = j.sal.fs.listDirsInDir(self.path)
        childs = {}
        for path in childDirs:
            if path.endswith('__pycache__'):
                continue
            child = j.sal.fs.getBaseName(path)
            name, instance = child.split("!")
            if name not in childs:
                childs[name] = []
            childs[name].append(instance)
        return childs

    def isConsumedBy(self, service):
        if self.role in service.producers:
            for s in service.producers[self.role]:
                if s.key == self.key:
                    return True
        return False

    def getProducers(self, producercategory):
        import ipdb; ipdb.set_trace()
        if producercategory not in self.producers:
            raise j.exceptions.Input("cannot find producer with category:%s"%producercategory, "ays.getProducer")
        instances = self.producers[producercategory]
        return instances

    def __eq__(self, service):
        if not service:
            return False
        if isinstance(service, str):
            return str(self.key) == service
        return service.role == self.role and self.instance == service.instance

    def __hash__(self):
        return hash((self.domain, self.name, self.instance, self.role, self.version))

    def __repr__(self):
        return self.key.__str__()

    def __str__(self):
        return self.__repr__()

    def runAction(self, action, printonly=False):
        if printonly:
            # TODO printonyl
            return
        getattr(self.actions, action)()

    def _getDisabledProducers(self):
        producers = dict()
        for key, items in self.hrd.getDictFromPrefix("producer").items():
            producers[key] = [j.atyourservice.getServiceFromKey(item.strip(), include_disabled=True) for item in items]
        return producers

    def _getConsumers(self, include_disabled=False):
        consumers = list()
        services = j.atyourservice.findServices(include_disabled=True, first=False)
        for service in services:
            producers = service._getDisabledProducers() if include_disabled else service.producers
            if self.role in producers and self in producers[self.role]:
                consumers.append(service)
        return consumers

    def disable(self):
        self.stop()
        for consumer in self._getConsumers():
            candidates = j.atyourservice.findServices(role=self.role, first=False)
            if len(candidates) > 1:
                # Other candidates available. Should link consumer to new candidate
                candidates.remove(self)
                candidate = candidates[0]
                producers = consumer.hrd.getList('producer.%s' % self.role, [])
                producers.remove(self.key)
                producers.append(candidate.key)
                consumer.hrd.set('producer.%s' % self.role, producers)
            else:
                # No other candidates already installed. Disable consumer as well.
                consumer.disable()

        self.logger.info("disable instance %s" % self.instance)
        self.state.hrd.set('disabled', True)

    def _canBeEnabled(self):
        for role, producers in list(self.producers.items()):
            for producer in producers:
                if producer.state.hrd.getBool('disabled', False):
                    return False
        return True

    def enable(self):
        # Check that all dependencies are enabled
        if not self._canBeEnabled():
            self.logger.warning("%s cannot be enabled because one or more of its producers is disabled" % self)
            return

        self.state.hrd.set('disabled', False)
        self.logger.info("Enable instance %s" % self.instance)
        for consumer in self._getConsumers(include_disabled=True):
            consumer.enable()
            consumer.start()
