from servers.key_value_store.store import KeyValueStoreBase
from JumpScale import j


import time

def chunks(l, n):
    for i in range(0, len(l), n):
        yield l[i:i+n]

class RedisKeyValueStore(KeyValueStoreBase):
    osis = dict()

    def __init__(self,namespace="",host='localhost',port=7771,db=0,password='', serializers=[],masterdb=None, changelog=True):

        self.redisclient=j.clients.redis.get(host, port,password=password)
        self.redisclient.port=port
        self.redisclient.host=host
        self._changelog = changelog
        self.namespace = namespace
        KeyValueStoreBase.__init__(self, serializers)

        self.hasmaster = bool(masterdb)
        self.writedb=masterdb or self

        self.lastchangeIdKey="changelog:lastid"
        self.nodelastchangeIdkey = "changelog:%s:lastid" % j.application.whoAmI.gid
        if self.redisclient.get(self.nodelastchangeIdkey)==None:
            self.writedb.redisclient.set(self.nodelastchangeIdkey,0)
        self.lastchangeId=int(self.redisclient.get(self.nodelastchangeIdkey) or 0)

    def deleteChangeLog(self):
        rediscl = self.writedb.redisclient
        rediscl.delete(self.lastchangeIdKey)

        keys = rediscl.keys("changelog:*")
        for chunk in chunks(keys, 100):
            rediscl.delete(*chunk)

    def increment(self, key):
        return self.writedb.redisclient.incr(key)

    def checkChangeLog(self):
        """
        @param reset, will just ignore the changelog
        @param delete, means even delete the changelog on master
        """
        if self.redisclient.get("changelog:lastid")==None:
            return
        lastid=int(self.redisclient.get("changelog:lastid"))
        result=[]
        if lastid>self.lastchangeId:
            try:
                for t in range(self.lastchangeId+1,lastid+1):
                    self.lastchangeId = t
                    key="changelog:data:%s"%t
                    counter=1
                    haskey = self.redisclient.exists(key)
                    while not haskey:
                        time.sleep(0.05)
                        if counter>10:
                            j.events.bug_warning("replication error, did not find key %s"%key, 'osis')
                            break
                        counter+=1
                        haskey = self.redisclient.exists(key)
                    if not haskey:
                        continue

                    epoch,category,key,gid,action=self.redisclient.get(key).split(":",4)
                    if int(gid) == j.application.whoAmI.gid:
                        continue
                    osis=self.osis[category]
                    if action == 'M':
                        counter=1
                        key2 = self._getCategoryKey(category, key)
                        haskey = self.redisclient.exists(key2)
                        while not haskey:
                            time.sleep(0.05)
                            if counter>100:
                                j.events.bug_warning("replication error, did not find key %s"%key2, 'osis')
                                break
                            counter+=1
                            haskey = self.redisclient.exists(key2)
                        else:
                            obj=osis.get(key)
                            if hasattr(obj, 'getDictForIndex'):
                                obj = obj.getDictForIndex()
                            osis.index(obj)
                    elif action == 'D':
                        osis.deleteIndex(key)
            finally:
                self.lastchangeId=lastid
                self.writedb.redisclient.set(self.nodelastchangeIdkey, lastid)
        return result

    def addToChangeLog(self,category,key,action="M"):
        if self._changelog and self.hasmaster:
            t=self.writedb.redisclient.incr(self.lastchangeIdKey)
            self.writedb.redisclient.set("changelog:data:%s"%t,"%s:%s:%s:%s:%s"%(int(time.time()),category,key,j.application.whoAmI.gid, action))

    def get(self, category, key):
        categoryKey = self._getCategoryKey(category, key)
        value = self.redisclient.get(categoryKey)
        return self.unserialize(value)

    def set(self, category, key, value,expire=0):
        """
        @param expire is in seconds when value will expire
        """
        if self.hasmaster:
            self.writedb.set(category,key,value)
            self.addToChangeLog(category, key) #notify system for change
        else:
            value = self.serialize(value)
            categoryKey = self._getCategoryKey(category, key)
            self.redisclient.set(categoryKey, value)

    def delete(self, category, key):
        if self.hasmaster:
            self.writedb.delete(category,key)
            self.addToChangeLog(category, key,action='D')
        else:
            categoryKey = self._getCategoryKey(category, key)
            # self._assertExists(categoryKey)
            self.redisclient.delete(categoryKey)

    def exists(self, category, key):
        categoryKey = self._getCategoryKey(category, key)
        return self.redisclient.exists(categoryKey)

    def list(self, category, prefix):
        prefix = "%s:" % category
        lprefix = len(prefix)
        fullkeys = self.redisclient.keys("%s*" % prefix)
        keys = list()
        for key in fullkeys:
            keys.append(key[lprefix:])
        return keys

    def listCategories(self):
        return list(self.categories.keys())

    def _getCategoryKey(self, category, key):
        return '%s:%s' % (category, key)

    def _stripCategory(self, keys, category):
        prefix = category + "."
        nChars = len(prefix)
        return [key[nChars:] for key in keys]

    def _categoryExists(self, category):
        categoryKey = self._getCategoryKey(category, "")
        return bool(self._client.prefix(categoryKey, 1))
