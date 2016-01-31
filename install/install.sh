rm -rf /opt/jumpscale8

set -ex
#known env variables

#JSBASE : is root where jumpscale will be installed
#SANDBOX : if system will be installed as sanbox or not (1 or 0)
#GITHUBUSER : user used to connect to github
#GITHUBPASSWD : passwd used to connect to github
#JSGIT : root for jumpcale git

#how to set the env vars: below you can find the defaults
# export GITHUBUSER=''
# export GITHUBPASSWD=''
#export SANDBOX=0
#export JSBASE='/opt/jumpscale8'
# export JSGIT='https://github.com/Jumpscale/jumpscale_core8.git'
export PYTHONVERSION='3'
export AYSGIT='https://github.com/Jumpscale/ays_jumpscale8'
export AYSBRANCH='master'

if [ "$(uname)" == "Darwin" ]; then
    # Do something under Mac OS X platform   
    #echo 'install brew'     
    #ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"
    brew install curl
    brew install python3
    # brew install git
    pip3 install --upgrade pip setuptools
    pip3 install ipdb
    pip3 install requests
    pip3 install paramiko
    pip3 install watchdog
    pip3 install mongoengine
    pip3 install hiredis
    # pip3 install dulwich
    pip3 install gitpython
    pip3 install click
    pip3 install ptpython
    pip3 install pymux
    pip3 install ptpdb
    
    export TMPDIR=~/tmp
    
    if [ -z"$JSBASE" ]; then 
        export JSBASE='~/opt/jumpscale8'
    fi
    
    cd $TMPDIR
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
    dist=''
    dist=`grep DISTRIB_ID /etc/*-release | awk -F '=' '{print $2}'`
    if [ "$dist" == "Ubuntu" ]; then
        echo "found ubuntu"
        apt-get install mc curl git ssh python3.5 -y
        rm -f /usr/bin/python
        rm -f /usr/bin/python3
        ln -s /usr/bin/python3.5 /usr/bin/python
        ln -s /usr/bin/python3.5 /usr/bin/python3

    elif [ -f "/etc/slitaz-release" ]; then
      echo "found slitaz"
      tazpkg get-install curl 
      tazpkg get-install git
      tazpkg get-install python3.5 
    fi

    if [ -z $JSBASE ]; then    
        export JSBASE='/opt/jumpscale8'
    fi
    export TMPDIR=/tmp
elif [ "$(expr substr $(uname -s) 1 10)" == "MINGW32_NT" ]; then
    # Do something under Windows NT platform
    echo 'windows'
    echo "CODE NOT COMPLETE FOR WINDOWS IN install.sh"
    exit
fi


set -ex
branch=${JSBRANCH-master}
curl -k https://raw.githubusercontent.com/Jumpscale/jumpscale_core8/$branch/install/web/bootstrap.py > $TMPDIR/bootstrap.py
curl -k https://raw.githubusercontent.com/Jumpscale/jumpscale_core8/$branch/install/web/InstallTools.py > $TMPDIR/InstallTools.py
cd $TMPDIR
python3.5 bootstrap.py
