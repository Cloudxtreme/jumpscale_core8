from JumpScale import j

descr = """
This jumpscript echos back (test)
"""

category = "test"
organization = "jumpscale"
author = "kristof@incubaid.com"
license = "bsd"
version = "1.0"
roles = []


order = 1
enable=True
async=True
queue='process'
log=False
debug=True

def action():
    msg="alive"
    print (msg)