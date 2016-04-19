from JumpScale import j
fs=j.sal.fs
from nose.tools import assert_equal, assert_not_equal, assert_raises, raises, assert_in, assert_not_in
import os
import os.path as path


def touchone(f):
    open(f, 'w').close()

def touchmany(fs):
    list(map(touchone,fs))

def removeone(f):
    if path.exists(f):
        os.remove(f)

def removemany(fs):
    list(map(os.remove, fs))

def getcwdfpath(f):
    return os.getcwd()+f

def tmpify(f):
    return '/tmp/'+f


def getfilesindir(f):
    return list(filter(path.isfile, [f+os.sep+x for x in os.listdir(f)]) )


def getdirsindir(f):
    return list(filter(path.isdir, [f+os.sep+x for x in os.listdir(f)]) )

def getallindir(f):
    return list([x for x in os.listdir(f) if path.isfile(f+os.sep+x) or path.isdir(f+os.sep+x)])

class TestFS(object):
    FILES=['f1.py', 'f2.py', 'f3.py']
    FILE='/tmp/hello.py'
    #create 2 files in the start.
    def setUp(self):
        touchmany(TestFS.FILES)
        txt="""
a=1
b=2
name='someone'

def inc(x):
    return x+1

        """
        with open(TestFS.FILE, 'w') as f:
            f.write(txt)


    #delete the 2 files created.
    def tearDown(self):
        removemany(TestFS.FILES)
        removeone(TestFS.FILE)

    def test_getBaseName(self):
        assert_equal(path.basename(TestFS.FILE), fs.getBaseName(TestFS.FILE))

    def test_getDirnName(self):
        #assert_equal(path.dirname(TestFS.FILE)+os.sep, fs.getDirName(TestFS.FILE))
        assert_equal(path.normpath(path.dirname(TestFS.FILE)), path.normpath(fs.getDirName(TestFS.FILE)))

    def test_getFileExtension(self):
        #assert_equal(path.splitext(FILE)[1], fs.getFileExtension(FILE))
        assert_in(fs.getFileExtension(TestFS.FILE), path.splitext(TestFS.FILE)[1]) #splitext includes a dot

    def test_exists(self):
        assert_equal(fs.exists(TestFS.FILE), True)
        #assert_equal(map(path.exists,TestFS.FILES), map(fs.exists, TestFS.FILES))

    def test_isDir(self):
        assert_equal(fs.isDir('/'), True)
        assert_equal(fs.isDir(TestFS.FILE), False)

    def test_isFile(self):
        assert_equal(fs.isFile('/'), False)
        assert_equal(fs.isFile(TestFS.FILE), True)

    def test_isLink(self):
        #make simple link
        os.link('f1.py', 'f1linked.py')
        assert_equal(path.islink('f1linked.py'), fs.isLink('f1linked.py'))
        os.unlink('f1linked.py')


    def test_getcwd(self):
        assert_equal(fs.getcwd(), os.getcwd())

    def test_touch(self):
        #Better way?
        assert_equal(path.exists('test1'), False)
        fs.touch('test1')
        assert_equal(path.exists('test1'), True)

        os.remove('test1')

    def test_getTmpFilePath(self):
        t=fs.getTmpFilePath()
        assert_in('/tmp', t)
        assert_equal(path.exists(t), True)
        assert_equal(path.isfile(t), True)

    def test_getTmpDirPath(self):
        t=fs.getTmpDirPath()
        assert_in('/tmp', t)
        assert_equal(path.exists(t), True)
        assert_equal(path.isdir(t), True)

    def test_getTempFileName(self):
        t=fs.getTempFileName()
        assert_in('/tmp', t)

    def test_fileSize(self):
        assert_equal(path.getsize(TestFS.FILE), fs.fileSize(TestFS.FILE))

    def test_isEmptyDir(self):
        d=tmpify('testdir')
        os.mkdir(d)
        assert_equal(os.listdir(d), [])
        assert_equal(fs.isEmptyDir(d), True)
        os.rmdir(d)

    def test_isAbsolute(self):
        assert_equal(path.isabs(TestFS.FILE), fs.isAbsolute(TestFS.FILE))


    def test_touch(self):
        f=tmpify('testx1')
        assert_equal(path.exists(f), False)
        fs.touch(f)
        assert_equal(path.exists(f), True)
        os.remove(f)


    def test_listpyscripts(self):
        #touch 3 files
        d=tmpify('pyscriptstest/')
        os.mkdir(d)
        FILES=list([d+x for x in ['f1.py', 'f2.py', 'f3.py'] ])
        touchmany(FILES)
        assert_equal(len(fs.listPyScriptsInDir(d)), 3)

        #remove the 3files
        removemany(FILES)
        os.rmdir(d)

    def test_changeDir(self):
        current=os.getcwd()
        os.chdir('/')
        fs.changeDir('/tmp')
        assert_in('/tmp', os.getcwd())
        os.chdir(current)

    def test_listFilesInDir(self):
        assert_equal(getfilesindir('.'), fs.listFilesInDir('.'))

    def test_listDirsInDir(self):
        assert_equal(getdirsindir('.'), fs.listDirsInDir('.'))

    def test_listDirsInDir(self):
        assert_equal(getdirsindir('.'), fs.listDirsInDir('.'))


    def test_listFilesAndDirsInDir(self):
        assert_equal(sorted(getallindir('.')), sorted(list(map(path.normpath,fs.listFilesAndDirsInDir('.'))))) ##FAILS ..

    def test_move(self): #moveFile & moveDir call fs.move anyways.
        touchone('testfile')
        assert_equal(path.exists('testfile'), True)
        fs.move('testfile', 'newtestfile')
        assert_equal(path.exists('newtestfile'), True)
        removeone('newtestfile')

    def test_pathShorten(self):
        f='/home/st/jumpscale/lib/main/../tests/runner.py'
        assert_equal(path.normpath(f), fs.pathShorten(f))


    def test_cleanupString(self):

        s="Hello%$$$%*&^WWW"
        cleaned=fs.cleanupString(s)
        assert_not_in("$", cleaned)
        assert_not_in("%", cleaned)
        assert_not_in("^", cleaned)


    def test_joinPaths(self):

        p1='/home'
        p2='striky/wspace'
        assert_equal(path.join(p1,p2), fs.joinPaths(p1,p2))
