#!/bin/bash -ex
# Any copyright is dedicated to the Public Domain.
# http://creativecommons.org/publicdomain/zero/1.0/

# Clear out repos and fat store from prior test runs
rm -fR fat-test fat-test2 /tmp/fat-store

git init fat-test
cd fat-test
git fat init
cat - >> .gitfat <<EOF
[rsync]
remote = localhost:/tmp/fat-store
EOF
echo '*.fat filter=fat -crlf' > .gitattributes
git add .gitattributes .gitfat
git commit -m'Initial fat repository'

ln -s /oe/dss-oe/dss-add-ons-testing-build/deploy/licenses/common-licenses/GPL-3 c
git add c
git commit -m'add broken symlink'
echo 'fat content a' > a.fat
git add a.fat
git commit -m'add a.fat'
echo 'fat content b' > b.fat
git add b.fat
git commit -m'add b.fat'
echo 'revise fat content a' > a.fat
git commit -am'revise a.fat'
git fat push

cd ..
git clone fat-test fat-test2
cd fat-test2
# Pull should fail in repo not yet init'ed for git-fat
git fat pull -- 'a.fa*' && true
if [ $? -eq 0 ]
then
    echo 'ERROR: "git fat pull" in uninitialised repo should fail'
    exit 1
fi
git fat init
git fat pull -- 'a.fa*'
cat a.fat
echo 'file which is committed and removed afterwards' > d
git add d
git commit -m'add d with normal content'
rm d
git fat pull

