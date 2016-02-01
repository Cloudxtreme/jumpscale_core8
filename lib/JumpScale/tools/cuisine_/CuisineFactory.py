from JumpScale import j

from Cuisine2 import *

class OurCuisineFactory:
    def __init__(self):
        self.__jslocation__ = "j.tools.cuisine"
        self._local=None


    @property
    def local(self):
        if self._local==None:
            self._local=OurCuisine(j.tools.executor.getLocal())
        return self._local

    def get(self,executor=None):
        """
        example:
        executor=j.tools.executor.getSSHBased(addr='localhost', port=22,login="root",passwd="1234",pushkey="ovh_install")
        cuisine=j.tools.cuisine.get(executor)

        or if used without executor then will be the local one

        """
        executor=j.tools.executor.get(executor)
        return OurCuisine(executor)

    def getFromId(self,cuisineid):
        executor=j.tools.executor.get(cuisineid)
        cuisine=j.tools.cuisine.get(executor)
        return cuisine



