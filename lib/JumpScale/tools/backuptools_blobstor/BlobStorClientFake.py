from JumpScale import j
import lzma
import os
import requests
from weed.master import WeedMaster

    
# import 

class BlobStorClientFake:
    """
    client to blobstormaster
    """

    def __init__(self, master='',domain='',namespace=''):
        self.master=master
        self.domain=domain
        self.namespace=namespace
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

        self.redis = j.clients.redis.get('localhost', 9999)
        #weedfs_host = j.application.config.get('weedfs.host', default='127.0.0.1')
        #weedfs_port = j.application.config.get('weedfs.port', default=9333)
        self.weed_master = WeedMaster()

    def _normalize(self, path):
        path=path.replace("'","\\'")
        path=path.replace("[","\\[")
        path=path.replace("]","\\]")
        return path


    def set(self,key, data,repoid=0,sync=True,timeout=60,serialization=""):
        """
        """
        assign_key = self.weed_master.get_assign_key()
        volume_id, _ = assign_key['fid'].split(',')
        file_id = ','.join([volume_id, key])
        files = {'file': (key, data)}
        r = requests.post('http://%s/%s' % (assign_key['publicUrl'], file_id), files=files)
        return file_id

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
        pass

    def existsBatch(self,keys,repoid=0,replicaCheck=False):
        #do multiple times exists
        for key in keys:
            #...
            pass
            #self.exists...

    def _exists(self,key,parent,repoid=0,replicaCheck=False):
        """
        Checks if the blobstor contains an entry for the given key
        @param key: key to Check
        @replicaCheck if True will check that there are enough replicas (not implemented)
        the normal check is just against the metadata stor on the server, so can be data is lost
        """
        for l in (k for k in self.redis.keys('files:*') if parent != k.split(':')[1]):
            if key in self.redis.lrange(l, 0, -1):
                return True
        return False

    def exists(self, key):
        '''Checks if a file or dir exists'''
        for l in (k for k in self.redis.keys('files:*')):
            if key == l.split(':')[1]:
                return True
        return False

    def getMD(self,key):
        #not sure what this is
        pass

    def delete(self,key, repoid=0,force=False):
        #mark in table in ledis
        ##as hset: bloblstor:todelete:$repoid:$key and inside the webdisk key
        ##this will allow us to delete later
        #delete in ledis, do not delete in weedfs
        pass


    def deleteNamespace(self):
        pass

    def _dump2stor(self, data,key="",repoid=0,compress=None,parent=None):
        if len(data)==0:
            return ""
        if key=="":
            key = j.data.hash.sha1_string(data)
        if compress==True or (len(data)>self._compressMin and self.compress):
            compress=self.compress
            # print "compress"
            print(".")
            data=lzma.compress(data)
            serialization="L"
        else:
            serialization=""
        file_id = None
        if not self._exists(key, parent):
            file_id = self.set(key=key, data=data,repoid=repoid,serialization=serialization,sync=False)
        else:
            print(('Chunk %s already exists on weedfs' % key))
        if parent and file_id:
            self.redis.rpush('files:%s' % parent, file_id)
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
        tarpath = "/tmp/%s.tar" % key
        self.downloadFile(key, tarpath)
        j.sal.fs.removeDirTree(dest)
        j.sal.fs.createDir(dest)
        cmd = "cd %s; tar xf %s" % (dest, tarpath)
        j.sal.process.execute(cmd)
        j.sal.fs.remove(tarpath)

    def uploadFile(self,path,key="",repoid=0,compress=None):        
        if key=="":
            key=j.data.hash.md5(path)
        if not self.exists(key):
            for data in self._read_file(path):
                self._dump2stor(data,repoid=repoid,compress=compress,parent=key)
        else:
            print(('Key: %s already exists' % key))
        return key

    def downloadFile(self,key,dest,link=False,repoid=0, chmod=0,chownuid=0,chowngid=0,sync=False,size=0):
        chunks_keys = self.redis.lrange('files:%s' % key, 0, -1)
        j.sal.fs.touch(dest)
        for chunk_key in chunks_keys:
            wv = self.weed_master.get_volume(chunk_key)
            chunk_data = wv.get_file(chunk_key)
            j.sal.fs.writeFile(dest, chunk_data, True)
            
    def _downloadFilePhase2(self,blob,dest,key,chmod,chownuid,chowngid,link,serialization):
        if key=="":
            return
        if blob==None:
            raise j.exceptions.RuntimeError("Cannot find blob with key:%s"%key)
                
        if self.cachepath!="":
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
        if chmod!=0:
            os.chmod(dest,chmod)
        if chownuid!=0:
            os.chown(dest,chownuid,chowngid)       

    def _link(self, src, dest):
        if dest=="":
            raise j.exceptions.RuntimeError("dest cannot be empty")
        os.link(src, dest)

