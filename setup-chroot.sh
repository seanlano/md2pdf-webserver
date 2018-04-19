#!/bin/bash

echo "Setting up chroot in "$(pwd)
# echo "Command line ARG1: '${1}'"


IS_SNAP=0
if [ -z ${SNAP_NAME+x} ]
then
    echo "NOT installed as a Snap"
    IS_SNAP=false
else
    echo "SNAP_NAME is '${SNAP_NAME}'"
    IS_SNAP=1
fi


echo "Creating basic folder structure"

mkdir bin
mkdir usr
mkdir dev
mkdir etc
mkdir lib
mkdir tmp
mkdir usr/local
mkdir usr/local/bin
mkdir usr/bin
mkdir usr/sbin
mkdir usr/share
mkdir usr/lib

chmod 777 tmp
chmod 777 .


echo "Copying binaries and libraries"

# Always copy from base system (i.e. from Core Snap if running as Snap)
bin_copies=("cp" "tar" "bunzip2" "bzcat" "bzip2" "cat" "chmod" "chown" "dash" "date" "dd" "dir" "echo" "egrep" "false" "fgrep" "grep" "gzip" "hostname" "kill" "ln" "ls" "mkdir" "mknod" "mktemp" "mv" "rm" "rmdir" "sed" "sh" "sleep" "stty" "sync" "touch" "true" "uname" "vdir")
for binary in "${bin_copies[@]}"
do
    cp -a "/bin/${binary}" bin/
done

# Copy from base system (i.e. from Core Snap if running as Snap)
usr_bin_copies=("uniq" "sort" "tty" "env" "locale" "clear" "tr" "basename" "dirname" "perl")
for binary in "${usr_bin_copies[@]}"
do
    cp -a "/usr/bin/${binary}" usr/bin/
done

# Copy from Snap (or from base if not running as Snap)
usr_bin_copies=("wget" "gpg2" "objdump" "fc-cache" "fc-cat" "fc-list" "fc-match" "fc-pattern" "fc-query" "fc-scan" "fc-validate")
for binary in "${usr_bin_copies[@]}"
do
    cp -a "${1}/usr/bin/${binary}" usr/bin/
done

# Copy from Snap (or from base if not running as Snap)
usr_share_dirs=("fonts" "i18n" "locale" "locales" "perl")
for folder in "${usr_share_dirs[@]}"
do
    cp -ar "${1}/usr/share/${folder}" usr/share/
done

# Always copy from base system (i.e. from Core Snap if running as Snap)
usr_lib_dirs=("x86_64-linux-gnu" "locale")
for folder in "${usr_lib_dirs[@]}"
do
    cp -ar "${1}/usr/lib/${folder}" usr/lib/
done

# Always copy from base system (i.e. from Core Snap if running as Snap)
cp -ar "/lib/x86_64-linux-gnu" lib/
# Copy from Snap (or from base if not running as Snap)
# cp -ar 
# Copy from Snap (or from base if not running as Snap)
cp -ar "${1}/lib64" .


echo "Setting up ld.so"
# TODO: Handle removing/updating this link
mkdir -p snap/${SNAP_NAME}/${SNAP_REVISION}/lib/x86_64-linux-gnu
ln -s ./${SNAP_REVISION} snap/${SNAP_NAME}/current
# cp -a lib64/ld-linux-x86-64.so.2 snap/${SNAP_NAME}/${SNAP_REVISION}/lib/x86_64-linux-gnu/ld-2.23.so
ln lib64/ld-linux-x86-64.so.2 snap/${SNAP_NAME}/${SNAP_REVISION}/lib/x86_64-linux-gnu/ld-2.23.so

echo "Setting up fonts"

cp -ar "${1}/etc/fonts" etc/

echo "Setting up config files"

echo "nameserver 8.8.8.8" >> etc/resolv.conf
# cp ../wrapper usr/local/bin/
# chmod 555 usr/local/bin/wrapper

# echo "Cleaning up"
#
# rm install-tl-unx.tar.gz
# rm -rf install-tl-20180303


echo "Setting up a small amount of entropy into /dev/random"
echo "(this will be faster if you use the keyboard and mouse!)"

dd if=/dev/random of=dev/random bs=1 count=256


echo "DONE chroot setup"


# sudo chroot ./ wrapper 'wget http://mirror.ctan.org/systems/texlive/tlnet/install-tl-unx.tar.gz'
# sudo chroot ./ wrapper 'tar xvf install-tl-unx.tar.gz'
# sudo chroot ./ wrapper 'perl install-tl-20180303/install-tl'
# sudo chroot ./ wrapper 'tlmgr install datetime fmtcount enumitem soul'
# sudo chroot ./ wrapper 'run-xelatex /tmp/testfile/test.latex'
