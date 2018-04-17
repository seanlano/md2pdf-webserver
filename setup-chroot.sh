#!/bin/bash

echo "Setting up chroot in "$(pwd)
# echo "Command line ARG1: '${1}'"
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

bin_copies=("cp" "tar" "bunzip2" "bzcat" "bzip2" "cat" "chgrp" "chmod" "chown" "dash" "date" "dd" "df" "dir" "echo" "egrep" "false" "fgrep" "grep" "gunzip" "gzip" "hostname" "kill" "ln" "ls" "mkdir" "mknod" "mktemp" "mv" "rm" "rmdir" "sed" "sh" "sleep" "stty" "sync" "touch" "true" "uname" "vdir")
for binary in "${bin_copies[@]}"
do
    cp -a "${1}/bin/${binary}" bin/
done

usr_bin_copies=("wget" "uniq" "sort" "tty" "env" "gpg2" "objdump" "locale" "clear" "tr" "basename" "dirname" "fc-cache" "fc-cat" "fc-list" "fc-match" "fc-pattern" "fc-query" "fc-scan" "fc-validate" "perl")
for binary in "${usr_bin_copies[@]}"
do
    cp -a "${1}/usr/bin/${binary}" usr/bin/
done

usr_share_dirs=("fonts" "i18n" "locale" "locales" "perl")
for folder in "${usr_share_dirs[@]}"
do
    cp -ar "${1}/usr/share/${folder}" usr/share/
done

usr_lib_dirs=("x86_64-linux-gnu" "locale")
for folder in "${usr_lib_dirs[@]}"
do
    cp -ar "${1}/usr/lib/${folder}" usr/lib/
done

cp -ar "${1}/lib/x86_64-linux-gnu" lib/
cp -ar "${1}/lib64" .


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
