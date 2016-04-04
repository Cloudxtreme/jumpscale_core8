from JumpScale import j


from ActionDecorator import ActionDecorator

class actionrun(ActionDecorator):
    def __init__(self, *args, **kwargs):
        ActionDecorator.__init__(self, *args, **kwargs)
        self.selfobjCode = "cuisine=j.tools.cuisine.getFromId('$id');selfobj=cuisine.builder"

class CuisineBuilder(object):

    def __init__(self, executor, cuisine):
        self.executor = executor
        self.cuisine = cuisine

    def jumpscale_installed(self, die=False):
        rc, out = self.cuisine.executor.execute('which js', die=False)
        if rc == 0:
            return True
        return False

    def all(self, start=False, sandbox=False, stor_addr=None):
        self.cuisine.installerdevelop.pip()
        self.cuisine.installerdevelop.python()
        if not self.jumpscale_installed():
            self.cuisine.installerdevelop.jumpscale8()
        self.cuisine.apps.cuisine.portal.install(start=start)
        self.cuisine.apps.redis.build(start=start, force=True)
        self.cuisine.apps.core.build(start=start)
        self.cuisine.apps.syncthing.build(start=start)
        self.cuisine.apps.controller.build(start=start)
        self.cuisine.apps.fs.build(start=start)
        self.cuisine.apps.stor.build(start=start)
        self.cuisine.apps.etcd.build(start=start)
        self.cuisine.apps.mongodb.build(start=start)
        self.cuisine.apps.caddy.build(start=start)
        # self.cuisine.apps.skydns(start=start)
        self.cuisine.apps.influxdb.build(start=start)
        self.cuisine.apps.weave.build(start=start)
        if sandbox:
            if not stor_addr:
                raise j.exceptions.RuntimeError("Store address should be specified if sandboxing enable.")
            self.sandbox(stor_addr)

    def sandbox(self, stor_addr, python=True):
        """
        stor_addr : addr to the store you want to populate. e.g.: https://stor.jumpscale.org/storx
        python : do you want to sandbox python too ? if you have segfault after trying sandboxing python, re run with python=False
        """
        # jspython is generated during install,need to copy it back into /opt before sandboxing
        self.cuisine.core.file_copy('/usr/local/bin/jspython', '/opt/jumpscale8/bin')

        # clean lib dir to avoid segfault during sandboxing
        self.cuisine.core.dir_remove('%s/*' % self.cuisine.core.dir_paths['libDir'])
        self.cuisine.core.dir_ensure('%s' % self.cuisine.core.dir_paths['libDir'])
        self.cuisine.core.file_link('/usr/local/lib/python3.5/dist-packages/JumpScale', '%s/JumpScale' % self.cuisine.core.dir_paths['libDir'])
        self.cuisine.core.file_link("%s/github/jumpscale/jumpscale_portal8/lib/portal" % self.cuisine.core.dir_paths["codeDir"], "%s/portal" % self.cuisine.core.dir_paths['jsLibDir'])

        # start sandboxing
        cmd = "j.tools.cuisine.local.apps.dedupe(['/opt'], 'js8_opt', '%s', sandbox_python=%s)" % (stor_addr, python)
        self.cuisine.core.run('js "%s"' % cmd)
        url_opt = '%s/static/js8_opt.flist' % stor_addr

        return url_opt

    def _sandbox_python(self, python=True):
        print("START SANDBOX")
        if python:
            paths = []
            paths.append("/usr/lib/python3.5/")
            paths.append("/usr/local/lib/python3.5/dist-packages")
            paths.append("/usr/lib/python3/dist-packages")

            excludeFileRegex=["-tk/", "/lib2to3", "-34m-", ".egg-info"]
            excludeDirRegex=["/JumpScale", "\.dist-info", "config-x86_64-linux-gnu", "pygtk"]

            dest = j.sal.fs.joinPaths(self.cuisine.core.dir_paths['base'], 'lib')

            for path in paths:
                j.tools.sandboxer.copyTo(path, dest, excludeFileRegex=excludeFileRegex, excludeDirRegex=excludeDirRegex)

            if not j.sal.fs.exists("%s/bin/python" % self.cuisine.core.dir_paths['base']):
                j.sal.fs.copyFile("/usr/bin/python3.5", "%s/bin/python" % self.cuisine.core.dir_paths['base'])

        j.tools.sandboxer.sandboxLibs("%s/lib" % self.cuisine.core.dir_paths['base'], recursive=True)
        j.tools.sandboxer.sandboxLibs("%s/bin" % self.cuisine.core.dir_paths['base'], recursive=True)
        print("SANDBOXING DONE, ALL OK IF TILL HERE, A Segfault can happen because we have overwritten ourselves.")

    def dedupe(self, dedupe_path, namespace, store_addr, output_dir='/tmp/sandboxer', sandbox_python=True):
        self.cuisine.core.dir_remove(output_dir)

        if sandbox_python:
            self._sandbox_python()

        if not j.data.types.list.check(dedupe_path):
            dedupe_path = [dedupe_path]

        for path in dedupe_path:
            print("DEDUPE:%s" % path)
            j.tools.sandboxer.dedupe(path, storpath=output_dir, name=namespace, reset=False, append=True, excludeDirs=['/opt/code'])

        store_client = j.clients.storx.get(store_addr)
        files_path = j.sal.fs.joinPaths(output_dir, 'files')
        files = j.sal.fs.listFilesInDir(files_path, recursive=True)
        error_files = []
        for f in files:
            src_hash = j.data.hash.md5(f)
            print('uploading %s' % f)
            uploaded_hash = store_client.putFile(namespace, f)
            if src_hash != uploaded_hash:
                error_files.append(f)
                print("%s hash doesn't match\nsrc     :%32s\nuploaded:%32s" % (f, src_hash, uploaded_hash))

        if len(error_files) == 0:
            print("all uploaded ok")
        else:
            raise RuntimeError('some files didnt upload properly. %s' % ("\n".join(error_files)))

        metadataPath = j.sal.fs.joinPaths(output_dir, "md", "%s.flist" % namespace)
        print('uploading %s' % metadataPath)
        store_client.putStaticFile(namespace+".flist", metadataPath)