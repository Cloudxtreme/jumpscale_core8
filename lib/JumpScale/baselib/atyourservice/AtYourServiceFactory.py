from JumpScale import j
from ServiceTemplate import ServiceTemplate
from ServiceRecipe import ServiceRecipe
from Service import Service, loadmodule
from ServiceKey import ServiceKey
from ActionsBaseNode import ActionsBaseNode
from ActionMethodDecorator import ActionMethodDecorator
from Blueprint import Blueprint

from AtYourServiceSync import AtYourServiceSync
try:
    from AtYourServiceSandboxer import *
except:
    pass
import os


import colored_traceback
colored_traceback.add_hook(always=True)

class AtYourServiceFactory():

    def __init__(self):
        self.__jslocation__ = "j.atyourservice"
        self.logger = j.logger.get("j.atyourservice")

        self._init = False
        self._domains = []
        self.hrd = None
        self._justinstalled = []
        self._type = None
        self._services = {}
        self._templates = []
        self._recipes = []
        self.indocker = False
        self.sync = AtYourServiceSync()
        self._reposDone = {}
        self._todo = []
        self.debug=j.core.db.get("atyourservice.debug")==1
        self._basepath=None
        self._git=None
        self._blueprints=[]
        self._sandboxer=None
        self._roletemplates = dict()
        self._servicesTree = {}

    def reset(self):
        j.dirs._ays = None
        self._services = {}
        self._templates = []
        self._recipes = []
        self._reposDone = {}
        self._todo = []
        self._git=None
        self._blueprints=[]
        self._servicesTree = {}

    def destroy(self):
        j.sal.fs.removeDirTree(j.sal.fs.joinPaths(self.basepath,"recipes"))
        j.sal.fs.removeDirTree(j.sal.fs.joinPaths(self.basepath,"services"))

    @property
    def basepath(self):
        if self._basepath==None:
            self.basepath = j.sal.fs.getcwd()
        return self._basepath

    @basepath.setter
    def basepath(self,val):
        self.reset()

        baseDir=val
        while j.sal.fs.joinPaths(baseDir, ".ays") not in j.sal.fs.listFilesInDir(baseDir, recursive=False):
            baseDir=j.sal.fs.getParent(baseDir)

            baseDir=baseDir.rstrip("/")

            if baseDir.strip()=="":
                if 'darwin' in j.core.platformtype.myplatform.platformtypes:
                    baseDir = "%s/ays/"%j.dirs.cfgDir
                else:
                    baseDir = "/etc/ays/local"
                break

        self._basepath=baseDir
        for item in ["blueprints","recipes","services","servicetemplates"]:
            #make sure basic dirs exist
            j.sal.fs.createDir(j.sal.fs.joinPaths(self._basepath,item))

    @property
    def git(self):
        if self._git==None:
            self._git=j.clients.git.get(basedir=self.basepath)
        return self._git

    @property
    def sandboxer(self):
        if self._sandboxer==None:
            self._sandboxer=AtYourServiceSandboxer()
        return self._sandboxer

    @property
    def type(self):
        if self._type is not None:
            return self._type
        self._type = "n"  # n from normal
        # check if we are in a git directory, if so we will use $thatdir/services as base for the metadata
        if self.basepath is not None:
            self._type = "c"
        return self._type

    @property
    def domains(self):
        self._doinit()
        return self._domains

    @property
    def templates(self):
        self._doinit()
        def load(domain, path, llist):
            for servicepath in j.sal.fs.listDirsInDir(path, recursive=False):
                dirname = j.sal.fs.getBaseName(servicepath)
                # print "dirname:%s"%dirname
                if not (dirname.startswith(".")):
                    load(domain, servicepath, llist)
            # print path
            dirname = j.sal.fs.getBaseName(path)
            if dirname.startswith("_"):
                return
            tocheck = ['schema.hrd', 'service.hrd', 'actions_mgmt.py', 'actions_node.py', 'model.py', 'actions.py']
            exists = [True for aysfile in tocheck if j.sal.fs.exists('%s/%s' % (path, aysfile))]
            if exists:
                templ = ServiceTemplate(path, domain=domain)
                llist.append(templ)

        if not self._templates:
            self._doinit()

            # load local templates
            path = j.sal.fs.joinPaths(self.basepath, "servicetemplates/")
            load("ays", path, self._templates)

            for domain, domainpath in self.domains:
                # print "load template domain:%s"%domainpath
                load(domain, domainpath, self._templates)

        return self._templates

    @property
    def recipes(self):
        self._doinit()
        if not self._recipes:
            self._doinit()
            aysrepopath = self.basepath
            if aysrepopath is not None:
                # load local templates
                domainpath = j.sal.fs.joinPaths(aysrepopath, "%s/recipes/" % aysrepopath)
                d = j.tools.path.get(domainpath)
                for item in d.walkfiles("state.hrd"):
                    recipepath = j.sal.fs.getDirName(item)
                    self._recipes.append(ServiceRecipe(recipepath))
        return self._recipes

    @property
    def services(self):
        self._doinit()
        if self._services == {}:
            for hrd_path in j.sal.fs.listFilesInDir(j.dirs.ays, recursive=True, filter="instance.hrd",
                                                    case_sensitivity='os', followSymlinks=True, listSymlinks=False):
                service_path = j.sal.fs.getDirName(hrd_path)
                service = Service(path=service_path, args=None)
                self._services[service.key.short]=service
        return self._services

    def _nodechildren(self, service, parent=None, producers=[]):
        parent = {} if parent is None else parent
        me = {"name": service.key.short, "children": []}
        parent["children"].append(me)
        details = service.hrd.getHRDAsDict()
        details = {key: value for key, value in details.items() if key not in ['service.domain', 'service.name', 'service.version', 'parent']}
        me["data"] = details
        children = service.listChildren()
        for role, instances in children.items():
            for instance in instances:
                child = j.atyourservice.getService(role=role, instance=instance)
                for _, producerinstances in child.producers.items():
                    for producer in producerinstances:
                        producers.append([child.key.short, producer.key.short])
                self._nodechildren(child, me, producers)
        return parent

    @property
    def servicesTree(self):
        if self._servicesTree:
            return self._servicesTree
        self._doinit()
        producers = []
        parents = {"name": "sudoroot", "children": []}
        for root in j.sal.fs.walk(j.dirs.ays, recurse=1, pattern='*instance.hrd', return_files=1, depth=2):
            servicekey = j.sal.fs.getBaseName(j.sal.fs.getDirName(root))
            service = self.services.get(servicekey)
            for _, producerinstances in service.producers.items():
                for producer in producerinstances:
                    producers.append([child.key.short, producer.key.short])
            parents["children"].append(self._nodechildren(service, {"children": [], "name": servicekey}, producers))
        self._servicesTree['parentchild'] = parents
        self._servicesTree['producerconsumer'] = producers
        return self._servicesTree

    @property
    def blueprints(self):
        """
        """
        if self._blueprints==[]:
            items=j.sal.fs.listFilesInDir(self.basepath+"/blueprints")
            items=[item for item in items if item.find("_archive")==-1]
            items=[item for item in items if item[0]!="_"]
            items.sort()
            for path in items:
                self._blueprints.append(Blueprint(path))
        return self._blueprints

    @property
    def roletemplates(self):
        if self._roletemplates:
            return self._roletemplates
        templatespaths = [j.sal.fs.joinPaths(self.basepath, '_templates')]
        for _, metapath in self._domains:
            templatespaths.append(j.sal.fs.joinPaths(metapath, '_templates'))
        templatespaths.reverse()

        for templatespath in templatespaths:
            if j.sal.fs.exists(templatespath):
                for roletemplate in j.sal.fs.listDirsInDir(templatespath):
                    paths = ['schema_tmpl.hrd', 'actions_tmpl_mgmt.py', 'actions_tmpl_node.py']
                    rtpaths = [path for path in paths if j.sal.fs.exists(j.sal.fs.joinPaths(templatespath, roletemplate, path))]
                    if rtpaths:
                        self._roletemplates[j.sal.fs.getBaseName(roletemplate)] = [j.sal.fs.joinPaths(roletemplate, rtpath) for rtpath in rtpaths]
        return self._roletemplates

    def _doinit(self):
        # if we don't have write permissin on /opt don't try do download service templates
        opt = j.tools.path.get('/opt')
        if not opt.access(os.W_OK):
            self._init = True

        if self._init is False:

            j.actions.setRunId("ays_%s"%j.sal.fs.getBaseName(j.atyourservice.basepath))
            if j.sal.fs.exists(path="/etc/my_init.d"):
                self.indocker=True

            login=j.application.config.get("whoami.git.login").strip()
            passwd=j.application.config.getStr("whoami.git.passwd").strip()

            # always load base domaim
            items=j.application.config.getDictFromPrefix("atyourservice.metadata")
            repos=j.do.getGitReposListLocal()

            for domain in list(items.keys()):
                url=items[domain]['url']
                if url.strip()=="":
                    raise j.exceptions.RuntimeError("url cannot be empty")
                branch=items[domain].get('branch', 'master')
                reponame=url.rpartition("/")[-1]
                if not reponame in list(repos.keys()):
                    # means git has not been pulled yet
                    if login!="":
                        dest=j.do.pullGitRepo(url,dest=None,login=login,passwd=passwd,depth=1,ignorelocalchanges=False,reset=False,branch=branch)
                    else:
                        dest=j.do.pullGitRepo(url,dest=None,depth=1,ignorelocalchanges=False,reset=False,branch=branch)

                repos=j.do.getGitReposListLocal()

                dest=repos[reponame]
                # print "init %s" % domain
                self._domains.append((domain,dest))

        self._init=True

    def init(self,newrun=True):

        self.reset()

        # make sure the recipe's are loaded & initted
        for bp in self.blueprints:
            bp.loadrecipes()

        # start from clean sheet
        self.reset()

        for bp in self.blueprints:
            bp.execute()

        self.logger.debug('init done')

    def createAYSRepo(self, path):
        j.sal.fs.createDir(path)
        j.sal.fs.createEmptyFile(j.sal.fs.joinPaths(path, '.ays'))
        j.sal.fs.createDir(j.sal.fs.joinPaths(path, 'servicetemplates'))
        j.sal.fs.createDir(j.sal.fs.joinPaths(path, 'blueprints'))
        j.sal.process.execute("git init %s" % path, die=True, outputToStdout=False, useShell=False, ignoreErrorOutput=False)
        j.sal.nettools.download('https://raw.githubusercontent.com/github/gitignore/master/Python.gitignore', j.sal.fs.joinPaths(path, '.gitignore'))
        print("AYS Repo created at %s" % path)

    def updateTemplatesRepos(self, repos=[]):
        """
        update the git repo that contains the service templates
        args:
            repos : list of dict of repos to update, if empty, all repos are updated
                    {
                        'url' : 'http://github.com/account/repo',
                        'branch' : 'master'
                    }
        """
        if len(repos) == 0:
            metadata = j.application.config.getDictFromPrefix('atyourservice.metadata')
            repos = list(metadata.values())

        for repo in repos:
            branch = repo['branch'] if 'branch' in repo else 'master'
            j.do.pullGitRepo(url=repo['url'], branch=branch)

    def getActionsBaseClassNode(self):
        return ActionsBaseNode


    def getActionMethodDecorator(self):
        return ActionMethodDecorator

    def getBlueprint(self,path):
        if not j.sal.fs.exists(path):
            path=self.basepath+"/"+path
        return Blueprint(path)

    def getRoleTemplateClass(self, role, ttype):
        if role not in self.roletemplates:
            raise j.exceptions.RuntimeError('Role template %s does not exist' % role)
        roletemplatepaths = self.roletemplates[role]
        for roletemplatepath in roletemplatepaths:
            if ttype in j.sal.fs.getBaseName(roletemplatepath):
                modulename = "JumpScale.atyourservice.roletemplate.%s.%s" % (role, ttype)
                mod = loadmodule(modulename, roletemplatepath)
                return mod.Actions
        return None

    def getRoleTemplateHRD(self, role):
        if role not in self.roletemplates:
            raise j.exceptions.RuntimeError('Role template %s does not exist' % role)
        roletemplatepaths = self.roletemplates[role]
        hrdpaths = [path for path in roletemplatepaths if j.sal.fs.getFileExtension(path) == 'hrd']
        if hrdpaths:
            hrd = j.data.hrd.getSchema(hrdpaths[0])
            for path in hrdpaths[1:]:
                hrdtemp = j.data.hrd.getSchema(path)
                hrd.items.update(hrdtemp.items)
            return hrd.hrdGet()
        return None

    def install(self,printonly=False,remember=True):
        #start from clean sheet
        self.init()
        self.do(action="install",printonly=printonly,remember=remember)

    def apply(self, printonly=False, remember=True):
        # start from clean sheet
        self.init()

        actions = ['install', 'start']

        todo = self.findTodo(action='install')
        while todo != []:
            for i in range(len(todo)):
                service = todo[i]
                for action in actions:
                    service.runAction(action, printonly)
            todo = self.findTodo('install')

    def commit(self, action="unknown", msg="", precheck=False):
        pass
        # if len(self.git.getModifiedFiles(True,ignore=["/alog/"]))>0:
        #     if msg=="":
        #         msg='ays changed, commit changed files for action:%s'%action
        #     print(msg)
        #     repo=self.git.commit(message=msg, addremove=True)
        #     self.alog.newGitCommit(action=action,githash=repo.hexsha)
        # else:
        #     #@todo will create duplicates will have to fix that
        #     #git hash is current state
        #     if not precheck:
        #         #only do this when no precheck, means we are not cleaning up past
        #         self.alog.newGitCommit(action=action,githash="")

    def _getChangedServices(self, action=None):
        changed = list()
        if not action:
            actions = ["install", "stop", "start", "monitor", "halt", "check_up", "check_down",
                       "check_requirements", "cleanup", "data_export", "data_import", "uninstall", "removedata"]
        else:
            actions = [action]

        for _, service in self.services.items():
            if [service for action in actions if service.state.getSet(action).state == 'CHANGED']:
                changed.append(service)
                changed.extend([producer for _, producer in service.producers()])
        return changed

    def do(self, action="install", printonly=False, remember=True, allservices=False, ask=False):
        if not allservices:
            # we need to find change since last time & make sure that
            # find all services with action with this name and put back on init
            # we also need to find all child service and depdendent service of the modified service
            changed = self._getChangedServices(action=action)
            toChange = set(changed)
            for service in changed:
                toChange = toChange.union(self.findConsumersRecursive(service))

            if ask:
                toChange = j.tools.console.askChoiceMultiple(list(toChange), sort=False)

            for service in toChange:
                if action in service.actions:
                    actionobj = service.actions[action]
                    actionobj.setState("CHANGED")

        else:
            todo = [item[1] for item in self.services.items()]
            for service in todo:
                actionobj = service.getAction(action)
                if remember is False or printonly:
                    actionobj._state = "START"
                else:
                    actionobj.setState("START")

        todo = self.findTodo(action=action)

        step = 1
        while todo != []:
            print("execute state changes, nr services to process: %s in step:%s" % (len(todo), step))
            for i in range(len(todo)):
                service = todo[i]
                service.runAction(action, printonly=printonly)
            todo = self.findTodo(action=action)

    def findTodo(self, action="install"):
        todo = list()
        for key, service in self.services.items():
            actionstate = service.state.getSet(action)
            if actionstate.state != "OK":
                producersWaiting = service.getProducersWaiting(action, set())
                if len(producersWaiting) == 0:
                    todo.append(service)
                    if j.atyourservice.debug:
                        print("%s waiting for install" % service)
                elif j.application.debug:
                    print("%s no change in producers" % service)
        return todo

    def checkRevisions(self):
        if len(self.services) == 0:
            self.loadServices()

        for service in self.services:
            service.state.saveRevisions()

    def findTemplates(self, name="", version="", domain="", role='', first=False):
        res = []
        for template in self.templates:
            if not(name == "" or template.name == name):
                # no match continue
                continue
            if not(domain == "" or template.domain == domain):
                # no match continue
                continue
            if not(version == "" or template.version == version):
                # no match continue
                continue
            if not (role == '' or template.role == role):
                # no match continue
                continue
            res.append(template)

        if first:
            if len(res) == 0:
                j.events.inputerror_critical("cannot find service template %s:%s (%s)" % (domain, name, version), "ays.findTemplates")
            return res[0]
        return res

    def findRecipes(self, name="", version="", role='',one=False):
        res = []
        domain="ays"
        for template in self.recipes:
            if not(name == "" or template.name == name):
                # no match continue
                continue
            if not(domain == "" or template.domain == domain):
                # no match continue
                continue
            if not(version == "" or template.version == version):
                # no match continue
                continue
            if not (role == '' or template.role == role):
                # no match continue
                continue
            res.append(template)

        if one:
            if len(res) == 0:
                j.events.inputerror_critical("cannot find ays recipes %s|%s (%s)" % (domain, name, version), "ays.findRecipes")
            if len(res) > 1:
                j.events.inputerror_critical("found 2+ ays recipes %s|%s (%s)" % (domain, name, version), "ays.findRecipes")
            return res[0]

        return res

    def findAYSRepos(self):
        return [j.sal.fs.getDirName(repo) for repo in j.sal.fs.walk(j.dirs.codeDir, 1, '.ays')]

    def findServices(self, name="", instance="",version="", domain="", parent=None, first=False, role="", node=None, include_disabled=False):
        res = []

        for shortkey, service in self.services.items():
            if not(name == "" or service.name == name):
                continue
            if not(domain == "" or service.domain == domain):
                continue
            if not(version == "" or service.version == version):
                continue
            if not(instance == "" or service.instance == instance):
                continue
            if not(parent is None or service.parent == parent):
                continue
            if not(role == "" or role == service.role):
                continue
            if not(node is None or service.isOnNode(node)):
                continue
            res.append(service)
        if first:
            if len(res) == 0:
                j.events.inputerror_critical("cannot find service %s|%s:%s (%s)" % (domain, name, instance, version), "ays.findServices")
            return res[0]
        return res

    def findProducer(self, producercategory, instancename):
        for item in self.findServices(instance=instancename):
            if producercategory in item.categories:
                return item

    def findConsumers(self, target):
        """
        @return set of services that consumes target
        """
        result = set()
        for service in self.findServices():
            if target.isConsumedBy(service):
                result.add(service)
        return result

    def findConsumersRecursive(self, target, out=set()):
        """
        @return set of services that consumes target, recursivlely
        """
        for service in self.findConsumers(target):
            out.add(service)
            self.findConsumersRecursive(service, out)
        return out

    def new(self,  name="", instance="main",version="",domain="",path=None, parent=None, args={},consume=""):
        """
        will create a new service from template

        @param args are the arguments which will overrule questions of the instance.hrd
        @param consume specifies which ays instances will be consumed
                format $role/$domain|$name!$instance,$role2/$domain2|$name2!$instance2

        """
        recipe = self.getRecipe(name,domain,version)
        obj = recipe.newInstance(instance=instance, path=path, parent=parent, args=args, consume=consume)
        return obj

    def remove(self,  name="", instance="",domain="", role=""):
        for service in self.findServices(domain=domain, name=name, instance=instance, role=role):
            if service in self.services:
                self.services.remove(service)
            j.sal.fs.removeDirTree(service.path)

    def getTemplate(self,  name="", version="",domain="", role="", first=True, die=True):
        if first:
            return self.findTemplates(domain=domain, name=name, version=version, role=role, first=first)
        else:
            res = self.findTemplates(domain=domain, name=name, version=version, role=role, first=first)
            if len(res) > 1:
                if die:
                    j.events.inputerror_critical("Cannot get ays template '%s|%s (%s)', found more than 1" % (domain, name, version), "ays.gettemplate")
                else:
                    return
            if len(res) == 0:
                if die:
                    j.events.inputerror_critical("Cannot get ays template '%s|%s (%s)', did not find" % (domain, name, version), "ays.gettemplate")
                else:
                    return
            return res[0]

    def getRecipe(self, name="",version="", domain="", role=""):
        template = self.getTemplate(domain=domain,name=name, version=version, role=role)
        return template.recipe

    def getService(self,  name='', instance='main', role='', die=True):
        """
        Return service indentifier by domain,name and instance
        throw error if service is not found or if more than one service is found
        """
        key = ServiceKey.get(name=name, role=role, instance=instance)
        if key.short in self.services:
            return self.services[key.short]
        if die:
            j.events.inputerror_critical("Cannot get ays service '%s', did not find" % key.short, "ays.getservice")
        else:
            self.logger.error("Cannot get ays service '%s', did not find" % key.short)
            return None

    def parseKey(self, key):
        """
        @return (domain,name,version,instance,role)

        """
        service_key = servicekey.parse(key)
        return self.getService(instance=service_key.instance, role=service_key.role, die=True)

    def __str__(self):
        return self.__repr__()

    def telegramBot(self, token, start=True):
        from JumpScale.baselib.atyourservice.telegrambot.TelegramAYS import TelegramAYS
        bot = TelegramAYS(token)
        if start:
            bot.run()
        return bot

    def start(self):
        from JumpScale.baselib.atyourservice.telegrambot.GeventLoop import AYSExecutor
        self.ays_exec = AYSExecutor(size=1)
        self.ays_exec.start()
