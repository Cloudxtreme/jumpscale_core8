from JumpScale import j
import lzma
import os

from weed.volume import WeedVolume
import requests
import ExtraTools

class BlobStorClientFake:
    """
    client to blobstormaster
    """

    def __init__(self, master, domain, namespace, host='localhost', port=9400):
        self.logger = j.logget.get('j.tools.backup_blobstor.client_fake')
        self.master=master
        self.domain=domain
        self.namespace=namespace
        self.host = host
        self.port = port
        # self.rmsize=len(self.nsobj["routeMap"])
        # self.queue=[]
        # self.queuedatasize=0
        # self.maxqueuedatasize=1*1024*1024 #1MB
        self._MB4=4*1024*1024
        self._compressMin=32*1024
        self.compress=True
        self.cachepath=""
        # self.lastjid=0

        self._downloadbatch={}
        self._downloadbatchSize=0

        self.results={}

        self.errors=[]
        self.redis = j.clients.redis.get(port=9999)

    def _normalize(self, path):
        path=path.replace("'","\\'")
        path=path.replace("[","\\[")
        path=path.replace("]","\\]")
        return path


    def set(self, key, data,repoid=0,sync=True,timeout=60,serialization=""):
        """
        """
        #use ledis & weedfs
        #key is md5, use ledis to have link between md5 & key on weedfs
        wv = WeedVolume(self.host, self.port)
        key = ExtraTools.ByteProcessor.hashMd5(data)
        url = wv.url_base + '/%s' % key
        files = {'file': (key, data)}
        try:
            r = requests.post(url, files=files)
        except Exception as e:
            self.logger.debug("Could not post file. Exception is: %s" % e)
            return None
        # weed-fs returns a 200 but the content may contain an error
        result = j.data.serializer.json.loads(r.content)
        if r.status_code == 200:
            if 'error' in result:
                self.logger.warn(result['error'])
            else:
                self.logger.debug(result)

        return result

    def sync(self):
        """
        """
        pass
        #nothing todo

    def get(self, key,repoid=0,timeout=60,sync=True):
        """
        get the block back
        """
        #use ledis & weedfs
        #key is md5, use ledis to have link between md5 & key on weedfs
        wv = WeedVolume(self.host, self.port)
        chunks_md5sum = self.redis.lrange('files.%s' % key, 1, -1)
        for chunk_md5sum in chunks_md5sum:
            #get file is not really working
            wv.get_file(chunk_md5sum)

    def existsBatch(self,keys,repoid=0,replicaCheck=False):
        #do multiple times exists
        for key in keys:
            #...
            pass
            #self.exists...

    def exists(self,key,repoid=0,replicaCheck=False):
        """
        Checks if the blobstor contains an entry for the given key
        @param key: key to Check
        @replicaCheck if True will check that there are enough replicas (not implemented)
        the normal check is just against the metadata stor on the server, so can be data is lost
        """
        #check against ledis


    def getMD(self,key):
        pass
        #not sure what this is

    def delete(self,key, repoid=0,force=False):
        pass
        #mark in table in ledis
        ##as hset: bloblstor:todelete:$repoid:$key and inside the webdisk key
        ##this will allow us to delete later
        #delete in ledis, do not delete in weedfs


    def deleteNamespace(self):
        pass

    def _dump2stor(self, data,key="",repoid=0,compress=None):
        if len(data)==0:
            return ""
        if key=="":
            key = j.data.hash.md5_string(data)
        if compress==True or (len(data)>self._compressMin and self.compress):
            compress=self.compress
            # print "compress"
            print ".",
            data=lzma.compress(data)
            serialization="L"
        else:
            serialization=""
        self.set(key=key, data=data,repoid=repoid,serialization=serialization,sync=False)
        return key

    def _read_file(self,path, block_size=0):
        if block_size==0:
            block_size=self._MB4
        with open(path, 'rb') as f:
            while True:
                piece = f.read(block_size)
                if piece:
                    yield piece
                else:
                    return

    def uploadDir(self,dirpath,compress=False):
        name="backup_md_%s"%j.data.idgenerator.generateRandomInt(1,100000)
        tarpath="/tmp/%s.tar"%name
        if compress:
            cmd="cd %s;tar czf %s ."%(dirpath,tarpath)
        else:
            cmd="cd %s;tar cf %s ."%(dirpath,tarpath)
        j.sal.process.execute(cmd)
        key=self.uploadFile(tarpath,compress=False)
        j.sal.fs.remove(tarpath)
        return key

    def downloadDir(self,key,dest,repoid=0,compress=None):
        j.sal.fs.removeDirTree(dest)
        j.sal.fs.createDir(dest)
        name="backup_md_%s"%j.data.idgenerator.generateRandomInt(1,100000)
        tarpath="/tmp/%s.tar"%name
        self.downloadFile(key,tarpath,False,repoid=repoid)
        if compress:
            cmd="cd %s;tar xzf %s"%(dest,tarpath)
        else:
            cmd="cd %s;tar xf %s"%(dest,tarpath)
        j.sal.process.execute(cmd)
        j.sal.fs.remove(tarpath)

    def uploadFile(self,path,key="",repoid=0,compress=None):
        if key=="":
            key=j.data.hash.md5(path)
        self.redis.rpush('files.%s' % key, j.sal.fs.getBaseName(path))
        if j.sal.fs.statPath(path).st_size>self._MB4:
            #hashes=[]
            # print "upload file (>4MB) %s"%(path)
            for data in self._read_file(path):
                self._dump2stor(data,repoid=repoid,compress=compress)
                self.redis.rpush('files.%s' % key, ExtraTools.ByteProcessor.hashMd5(data))
                #hashes.append(self._dump2stor(data,repoid=repoid,compress=compress))
            # if len(hashes)>1:
            #     out = "##HASHLIST##\n"
            #     hashparts = "\n".join(hashes)
            #     out += hashparts
            #     # Store in blobstor
            #     # out_hash = self._dump2stor(out,key=md5) #hashlist is stored on md5 location of file
            #     self.set(key=key, data=out,repoid=repoid)
            # else:
            #     raise j.exceptions.RuntimeError("hashist needs to be more than 1.")
        else:
            # print "upload file (<4MB) %s"%(path)
            for data in self._read_file(path):
                self._dump2stor(data,key=key,repoid=repoid,compress=compress)
                self.redis.rpush('files.%s' % key, ExtraTools.ByteProcessor.hashMd5(data))
        return key

    def downloadFile(self,key,dest,link=False,repoid=0, chmod=0,chownuid=0,chowngid=0,sync=False,size=0):

        if self.cachepath != "":
            blob_path = self._getBlobCachePath(key)
            if j.sal.fs.exists(blob_path):
                # Blob exists in cache, we can get it from there!
                print "Blob FOUND in cache: %s" % blob_path
                if link:
                    self._link(blob_path,dest)
                else:
                    j.sal.fs.copyFile(blob_path, dest)
                    os.chmod(dest, chmod)
                    os.chown(dest, chownuid, chowngid)
                return

        if self._downloadbatchSize>self.maxqueuedatasize or len(self._downloadbatch)>200:
            self.downloadBatch()

        #now normally on server we should have results ready

        if size != 0 and sync==False:
            jid=self.get( key,repoid=repoid,sync=False)
            # print [jid,key,dest,link,repoid,chmod,chownuid,chowngid]
            self._downloadbatch[jid]=(jid,key,dest,link,repoid,chmod,chownuid,chowngid)
            self._downloadbatchSize+=int(size)
        else:
            # Get blob from blobstor2
            if key != "":
                key,serialization,blob = self.get( key,repoid=repoid,sync=True)
                self._downloadFilePhase2(blob,dest,key,chmod,chownuid,chowngid,link,serialization)


    # def downloadBatch(self):
    #     self._send()
    #     jids=self._downloadbatch.keys()
    #     self.blobstor._cmdchannel.send_multipart([msgpack.dumps([[0,"getresults",{},jids]]),"S",str(60),self.blobstor.sessionkey])
    #     res= self.blobstor._cmdchannel.recv_multipart()

    #     for item in res:
    #         if item=="":
    #             continue
    #         else:
    #             jid,rcode,result=msgpack.loads(item)
    #             if rcode==0:
    #                 jid,key,dest,link,repoid,chmod,chownuid,chowngid=self._downloadbatch[jid]
    #                 key2=result[0]
    #                 if key2 != key:
    #                     raise j.exceptions.RuntimeError("Keys need to be the same")
    #                 blob=result[2]
    #                 serialization=result[1]

    #                 self._downloadFilePhase2(blob,dest,key,chmod,chownuid,chowngid,link,serialization)
    #             else:
    #                 ##TODO
    #                 pass

    #     self._downloadbatchSize=0
    #     self._downloadbatch={}

    def _downloadFilePhase2(self,blob,dest,key,chmod,chownuid,chowngid,link,serialization):
        if key=="":
            return
        if blob==None:
            raise j.exceptions.RuntimeError("Cannot find blob with key:%s"%key)

        if self.cachepath != "":
            blob_path = self._getBlobCachePath(key)
            self._restoreBlobToDest(blob_path, blob, chmod=chmod,chownuid=chownuid,chowngid=chowngid,serialization=serialization)
            j.sal.fs.createDir(j.sal.fs.getDirName(dest))

            if link:
                self._link(blob_path,dest)
            else:
                j.sal.fs.copyFile(blob_path, dest)
                os.chmod(dest, chmod)
                os.chown(dest, chownuid, chowngid)
        else:
            self._restoreBlobToDest(dest, blob, chmod=chmod,chownuid=chownuid,chowngid=chowngid,serialization=serialization)


    def _getBlobCachePath(self, key):
        """
        Get the blob path in Cache dir
        """
        # Get the Intermediate path of a certain blob
        storpath = j.sal.fs.joinPaths(self.cachepath, key[0:2], key[2:4], key)
        return storpath


    def _restoreBlobToDest(self, dest, blob, chmod=0,chownuid=0,chowngid=0,serialization=""):
        """
        Write blob to destination
        """
        check="##HASHLIST##"
        j.sal.fs.createDir(j.sal.fs.getDirName(dest))
        if blob.find(check)==0:
            # found hashlist
            # print "FOUND HASHLIST %s" % blob
            hashlist = blob[len(check) + 1:]
            j.sal.fs.writeFile(dest,"")
            for hashitem in hashlist.split("\n"):
                if hashitem.strip() != "":
                    key,serialization,blob_block = self.get(hashitem)
                    if serialization=="L":
                         blob_block= lzma.decompress(blob_block)
                    j.sal.fs.writeFile(dest, blob_block, append=True)
        else:
            # content is there
            if serialization=="L":
                blob = lzma.decompress(blob)
            j.sal.fs.writeFile(dest, blob)

        # chmod/chown
        if chmod != 0:
            os.chmod(dest,chmod)
        if chownuid != 0:
            os.chown(dest,chownuid,chowngid)

    def _link(self, src, dest):
        if dest=="":
            raise j.exceptions.RuntimeError("dest cannot be empty")
        os.link(src, dest)
