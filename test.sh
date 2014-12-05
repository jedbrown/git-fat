#!/bin/bash -ex
# Any copyright is dedicated to the Public Domain.
# http://creativecommons.org/publicdomain/zero/1.0/

export GIT_FAT_VERBOSE=1

# Clear out repos and fat store from prior test runs
rm -fR fat-test fat-test2 /tmp/fat-store
mkdir -p /tmp/fat-store

git init fat-test
cd fat-test
git fat init
cat - >> .gitfat <<EOF
[rsync]
remote = /tmp/fat-store
share = /tmp/fat-store
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
mkdir sub
echo 'fat content b' > sub/b.fat
git add sub/b.fat
git commit -m'add b.fat'
echo 'revise fat content a' > a.fat
git commit -am'revise a.fat'
git fat push

cd ..
git clone fat-test fat-test2
cd fat-test2
git fat init
git fat pull -- 'a.fa*'
cat a.fat
echo 'file which is committed and removed afterwards' > d
git add d
git commit -m'add d with normal content'
rm d
git fat pull

# Check verify command finds corrupt object
mv .git/fat/objects/sub/b.fat.6ecec2e21d3033e7ba53e2db63f69dbd3a011fa8 \
   .git/fat/objects/sub/b.fat.6ecec2e21d3033e7ba53e2db63f69dbd3a011fa8.bak
echo "Not the right data" > .git/fat/objects/sub/b.fat.6ecec2e21d3033e7ba53e2db63f69dbd3a011fa8
git fat verify && true
if [ $? -eq 0 ]; then echo "Verify did not detect invalid object"; exit 1; fi
mv .git/fat/objects/sub/b.fat.6ecec2e21d3033e7ba53e2db63f69dbd3a011fa8.bak \
   .git/fat/objects/sub/b.fat.6ecec2e21d3033e7ba53e2db63f69dbd3a011fa8
