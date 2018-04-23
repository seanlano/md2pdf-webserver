#!/bin/bash

echo "Setting up chroot in "$(pwd)


IS_SNAP=0
if [ -z ${SNAP_NAME+x} ]
then
    echo "NOT installed as a Snap"
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
mkdir var
mkdir usr/local
mkdir usr/local/bin
mkdir usr/bin
mkdir usr/sbin
mkdir usr/share
mkdir usr/lib
mkdir var/lib

chmod 777 tmp
chmod 755 .


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
usr_bin_copies=("wget" "gpg2" "objdump" "fc-cache" "fc-cat" "fc-list" "fc-match" "fc-pattern" "fc-query" "fc-scan" "fc-validate" "dvipdf" "eps2eps" "font2c" "ghostscript" "gs" "gsbj" "gsdj" "gsdj500" "gslj" "gslp" "gsnd" "pdf2dsc" "pdf2ps" "pf2afm" "pfbtopfa" "pphs" "printafm" "ps2ascii" "ps2epsi" "ps2pdf" "ps2pdf12" "ps2pdf13" "ps2pdf14" "ps2pdfwr" "ps2ps" "ps2ps2" "ps2txt" "rsvg" "wftopfa")
for binary in "${usr_bin_copies[@]}"
do
    cp -a "${1}/usr/bin/${binary}" usr/bin/
done

# Copy from Snap (or from base if not running as Snap)
usr_share_dirs=("fonts" "i18n" "locale" "locales" "perl" "ghostscript")
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
cp -ar "${1}/lib64" .


if [ $IS_SNAP == 1 ]
then
    echo "Setting up ld.so"
    # TODO: Handle removing/updating this link
    mkdir -p snap/${SNAP_NAME}/${SNAP_REVISION}/lib/x86_64-linux-gnu
    ln -s ./${SNAP_REVISION} snap/${SNAP_NAME}/current
    ln lib64/ld-linux-x86-64.so.2 snap/${SNAP_NAME}/${SNAP_REVISION}/lib/x86_64-linux-gnu/ld-2.23.so
fi


echo "Setting up fonts"

cp -ar "${1}/etc/fonts" etc/
cp -ar "${1}/etc/ghostscript" etc/
cp -a "${1}/usr/sbin/update-gsfontmap" usr/bin/
cp -ar "${1}/var/lib/ghostscript" var/lib/


echo "Setting up config files"

echo "nameserver 8.8.8.8" >> etc/resolv.conf
echo \#\!/bin/sh >> usr/local/bin/wrapper
echo "export PATH=/usr/local/texlive/bin/x86_64-linux:/usr/local/bin:/usr/sbin:/usr/bin:/bin" >> usr/local/bin/wrapper
echo "export LC_ALL=C" >> usr/local/bin/wrapper
echo \$1 >> usr/local/bin/wrapper
chmod 555 usr/local/bin/wrapper

echo ${SNAP_REVISION} >> snap_revision


echo "Copying TeX Live installer"

mkdir -p install-tl-unx
if [ $IS_SNAP == 1 ]
then
    cp ${SNAP}/snap/install-tl-unx.tar.gz .
    cp ${SNAP}/snap/md2pdf-texlive.profile install-tl-unx/
else
    wget https://mirrors.sorengard.com/ctan/systems/texlive/tlnet/install-tl-unx.tar.gz
fi
# tar will complain about some permissions, we don't mind about that
tar xvf install-tl-unx.tar.gz --strip-components 1 --directory install-tl-unx 1> /dev/null 2> /dev/null


if [ $IS_SNAP == 1 ]
then
    echo "Copying Pandoc"
    # TODO: Handle removing/updating this
    cp -a ${SNAP}/bin/pandoc bin/
    cp -a ${SNAP}/bin/pandoc-citeproc bin/
    cp -a ${SNAP}/bin/pandoc-crossref bin/
fi


echo "Setting up a small amount of entropy into /dev/random"
echo "(this will be faster if you use the keyboard and mouse!)"

# Hide the output from dd, it's not really helpful in this case
dd if=/dev/random of=dev/random bs=1 count=256 1> /dev/null
dd if=/dev/random of=dev/urandom bs=1 count=256 1> /dev/null


echo "Running installer"

chroot /var/snap/md2pdf-webserver/common/texlive-chroot wrapper 'update-gsfontmap'
chroot /var/snap/md2pdf-webserver/common/texlive-chroot wrapper 'install-tl-unx/install-tl -profile install-tl-unx/md2pdf-texlive.profile'
chroot /var/snap/md2pdf-webserver/common/texlive-chroot wrapper 'tlmgr install datetime fmtcount enumitem soul'


echo "Cleaning up"

rm install-tl-unx.tar.gz
rm -rf install-tl-unx


echo
echo "DONE chroot setup"
