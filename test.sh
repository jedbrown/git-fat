#!/bin/bash
# Any copyright is dedicated to the Public Domain.
# http://creativecommons.org/publicdomain/zero/1.0/

set -e

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

echo 'fat content a' > a.fat
git add a.fat
git commit -m'add a.fat'
echo 'fat content b' > b.fat
git add b.fat
git commit -m'add b.fat'
echo 'revise fat content a' > a.fat
git commit -am'revise a.fat'
