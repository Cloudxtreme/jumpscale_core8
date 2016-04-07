from JumpScale import j
from ServiceTemplate import ServiceTemplate
from Service import Service, loadmodule
from inspect import getmembers, isfunction, isclass, getsource

class ActionMethod():

    def __init__(self,recipe,name,content):
        self.name=name
        self.recipe=recipe
        self._check(content)
        self.hrdArgKeys=[] #names of arguments as used in hrd which are used in this action method
        if content=="":
            self.hash=""
        else:
            self.hash=j.data.hash.md5_string(content)

    def _check(self,content):
        #for now we don't do a check, later want to make sure we don't call other services, now we just put impact on all hrd schema arguments
        self.recipe.schema
        #for now we take all arguments, later we need to be more specific
        self.hrdArgKeys=[item for item in self.recipe.schema.items.keys()]

    def __repr__(self):
        return "%s:%s"%(self.name,self.hash)

    __str__=__repr__



class ServiceRecipe(ServiceTemplate):

    def __init__(self, path="",template=None,aysrepopath=""):
        self.logger = j.logger.get('j.atyourservice.recipe')
        self.key = template.key

        aysrepopath = j.atyourservice.basepath
        if not aysrepopath:
            raise j.exceptions.RuntimeError("A service instance can only be used when used from a ays repo")

        if path != "":
            if not j.sal.fs.exists(path):
                raise j.exceptions.RuntimeError("Could not find path for recipe")
            self.path = path
            name = self.state.hrd.get("template.name")
            domain = self.state.hrd.get("template.domain")
            version = self.state.hrd.get("template.version")
            self.template = j.atyourservice.getTemplate(domain=domain, name=name, version=version)
        else:
            self.path = j.sal.fs.joinPaths(aysrepopath,"recipes", template.name)
            self.name = template.name
            self.template = template

        self.version = self.template.version
        self.domain = self.template.domain

        # copy the files
        if not j.sal.fs.exists(path=self.path):
            firstime = True
            j.sal.fs.createDir(self.path)
        else:
            firstime = False

        self.actionmethods={}

        self._init()

        if j.sal.fs.exists(self.template.path_hrd_template):
            j.sal.fs.copyFile(self.template.path_hrd_template, self.path_hrd_template)
        if j.sal.fs.exists(self.template.path_hrd_schema):
            j.sal.fs.copyFile(self.template.path_hrd_schema, self.path_hrd_schema)
        if j.sal.fs.exists(self.template.path_actions_node):
            j.sal.fs.copyFile(self.template.path_actions_node, self.path_actions_node)
        if j.sal.fs.exists(self.template.path_mongo_model):
            j.sal.fs.copyFile(self.template.path_mongo_model, self.path_mongo_model)

        self._copyActions()

    def _checkdef(self, actionmethod, content, decorator=True):
        a = ActionMethod(self, actionmethod, content)
        self.actionmethods[actionmethod] = a
        async = ''
        if actionmethod != 'init':
            async = 'async=True'
        if actionmethod == 'input':
            self._out += '\n    def input(self,name,role,instance,serviceargs):\n        return serviceargs\n\n'
        elif not decorator and content:
            self._out += content
        elif content:
            self._out += '\n    @actionmethod(%s)\n%s' % (async, content)
        else:
            self._out += "\n    @actionmethod(%s)\n    def %s(self):\n        return True\n\n" % (async, actionmethod)

    def _copyActions(self):
        self._out = """
        from JumpScale import j
        ActionMethodDecorator=j.atyourservice.getActionMethodDecorator()
        class actionmethod(ActionMethodDecorator):
            def __init__(self,*args,**kwargs):
                ActionMethodDecorator.__init__(self,*args,**kwargs)
                self.selfobjCode="service=j.atyourservice.getService(name='$(service.name)', role='$(service.role)', instance='$(service.instance)', die=True);selfobj=service.actions;selfobj.service=service"
        class Actions():
        """
        actionmethodsRequired = ["input", "init", "install", "stop", "start", "monitor", "halt", "check_up", "check_down",
                                 "check_requirements", "cleanup", "data_export", "data_import", "uninstall", "removedata"]
        self._out = j.data.text.strip(self._out)

        if j.sal.fs.exists(self.template.path_actions):
            actions = loadmodule('temp.actions', self.template.path_actions)
            classes_list = [cls for cls in getmembers(actions) if isclass(cls[1])]
            if classes_list:
                for func in getmembers(classes_list[0][1]):
                    if isfunction(func[1]):
                        decorator = True if func[0] in actionmethodsRequired else False
                        self._checkdef(func[0], getsource(func[1]), decorator)
                # [self._checkdef(func[0], getsource(func[1])) for func in getmembers(classes_list[0][1]) if isfunction(func[1])]
                #self._checkdef(prop[0], getsource(prop[1]), property=True)
                # props = [prop for prop in getmembers(classes_list[0][1]) if isinstance(prop[1], property)]
        for method in actionmethodsRequired:
            if method not in self.actionmethods:
                self._checkdef(method, "")  # remember action

        j.sal.fs.writeFile(filename=self.path_actions, contents=self._out)

    def newInstance(self, instance="main", role='', args={}, path='', parent=None, consume="",originator=None,yaml=None):
        """
        """

        if parent is not None and instance == "main":
            instance = parent.instance

        instance = instance.lower()

        services = j.atyourservice.findServices(name=self.name, instance=instance)
        self.key.instance = instance

        if services:
            self.logger.warning("NEWINSTANCE: Service instance %s exists." % self.key)
            service = services[0]
            service.args.update(args or {})  # needed to get the new args in
            service._recipe = self
            service.init()

        else:
            if path:
                fullpath = path
            elif parent is not None:
                fullpath = j.sal.fs.joinPaths(parent.path, str(self.key))
            else:
                ppath = j.sal.fs.joinPaths(j.atyourservice.basepath, "services")
                fullpath = j.sal.fs.joinPaths(ppath, str(self.key))

            if j.sal.fs.isDir(fullpath):
                j.events.opserror_critical(msg='Service with same role ("%s") and of same instance ("%s") is already installed.\nPlease remove dir:%s it could be this is broken install.' % (self.role, instance, fullpath))

            service = Service(self, instance=instance, args=args, path=fullpath, parent=parent, originator=originator)

            j.atyourservice._services[service.key.short] = service

            if not j.sal.fs.exists(self.template.path_hrd_schema):
                service.init(yaml=yaml)
            else:
                service.init()

            service.consume(consume)

        return service

    def downloadfiles(self):
        """
        this method download any required files for this recipe as defined in the template.hrd
        Use this method when building a service to have all the files ready to sandboxing

        @return list of tuples containing the source and destination of the files defined in the recipeitem
                [(src, dest)]
        """
        dirList = []
        # download
        for recipeitem in self.hrd_template.getListFromPrefix("web.export"):
            if "dest" not in recipeitem:
                j.events.opserror_critical(msg="could not find dest in hrditem for %s %s" % (recipeitem, self), category="ays.servicetemplate")

            fullurl = "%s/%s" % (recipeitem['url'],
                                 recipeitem['source'].lstrip('/'))
            dest = recipeitem['dest']
            dest = j.application.config.applyOnContent(dest)
            destdir = j.sal.fs.getDirName(dest)
            j.sal.fs.createDir(destdir)
            # validate md5sum
            if recipeitem.get('checkmd5', 'false').lower() == 'true' and j.sal.fs.exists(dest):
                remotemd5 = j.sal.nettools.download(
                    '%s.md5sum' % fullurl, '-').split()[0]
                localmd5 = j.data.hash.md5(dest)
                if remotemd5 != localmd5:
                    j.sal.fs.remove(dest)
                else:
                    continue
            elif j.sal.fs.exists(dest):
                j.sal.fs.remove(dest)
            j.sal.nettools.download(fullurl, dest)

        for recipeitem in self.hrd_template.getListFromPrefix("git.export"):
            if "platform" in recipeitem:
                if not j.core.platformtype.myplatform.checkMatch(recipeitem["platform"]):
                    continue

            # pull the required repo
            dest0 = j.atyourservice._getRepo(recipeitem['url'], recipeitem=recipeitem)
            src = "%s/%s" % (dest0, recipeitem['source'])
            src = src.replace("//", "/")
            if "dest" not in recipeitem:
                j.events.opserror_critical(msg="could not find dest in hrditem for %s %s" % (recipeitem, self), category="ays.servicetemplate")
            dest = recipeitem['dest']

            dest = j.application.config.applyOnContent(dest)
            src = j.application.config.applyOnContent(src)

            if "link" in recipeitem and str(recipeitem["link"]).lower() == 'true':
                # means we need to only list files & one by one link them
                link = True
            else:
                link = False

            if src[-1] == "*":
                src = src.replace("*", "")
                if "nodirs" in recipeitem and str(recipeitem["nodirs"]).lower() == 'true':
                    # means we need to only list files & one by one link them
                    nodirs = True
                else:
                    nodirs = False

                items = j.sal.fs.listFilesInDir(
                    path=src, recursive=False, followSymlinks=False, listSymlinks=False)
                if nodirs is False:
                    items += j.sal.fs.listDirsInDir(
                        path=src, recursive=False, dirNameOnly=False, findDirectorySymlinks=False)

                items = [(item, "%s/%s" % (dest, j.sal.fs.getshortkey(item)), link)
                         for item in items]
            else:
                items = [(src, dest, link)]

            out = []
            for src, dest, link in items:
                delete = recipeitem.get('overwrite', 'true').lower() == "true"
                if dest.strip() == "":
                    raise j.exceptions.RuntimeError(
                        "a dest in coderecipe cannot be empty for %s" % self)
                if dest[0] != "/":
                    dest = "/%s" % dest
                else:
                    if link:
                        if not j.sal.fs.exists(dest):
                            j.sal.fs.createDir(j.sal.fs.getParent(dest))
                            j.sal.fs.symlink(src, dest)
                        elif delete:
                            j.sal.fs.remove(dest)
                            j.sal.fs.symlink(src, dest)
                    else:
                        print(("copy: %s->%s" % (src, dest)))
                        if j.sal.fs.isDir(src):
                            j.sal.fs.createDir(j.sal.fs.getParent(dest))
                            j.sal.fs.copyDirTree(
                                src, dest, eraseDestination=False, overwriteFiles=delete)
                        else:
                            j.sal.fs.copyFile(
                                src, dest, True, overwriteFile=delete)
                out.append((src, dest))
                dirList.extend(out)

        return dirList

    def listInstances(self):
        """
        return a list of instance name for this template
        """
        services = j.atyourservice.findServices(domain=self.domain, name=self.name)
        return [service.instance for service in services]

    def upload2AYSfs(self, path):
        """
        tell the ays filesystem about this directory which will be uploaded to ays filesystem
        """
        j.tools.sandboxer.dedupe(path, storpath="/tmp/aysfs", name="md", reset=False, append=True)

    def __repr__(self):
        return "Recipe: %-15s (%s)" % (self.name,self.template.version)
