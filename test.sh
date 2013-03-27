#!/bin/bash -ex
# Any copyright is dedicated to the Public Domain.
# http://creativecommons.org/publicdomain/zero/1.0/

# Clean up any existing directories from previous runs
if [ -d "fat-test" ] 
then
	rm -rf fat-test
fi
if [ -d "fat-test2" ]
then
	rm -rf fat-test2
fi

# Make sure that the "remote" directory exists
mkdir -p /tmp/fat-store

# Enable verbose mode
set -e
export GIT_FAT_VERBOSE=1

# Initialize first repo
git init fat-test
cd fat-test
git fat init
cat - >> .gitfat <<EOF
[rsync]
remote = localhost:/tmp/fat-store
EOF
cat - > .gitattributes <<EOF
*.fat filter=fat -crlf
*.gz filter=fat -crlf
EOF
git add .gitattributes .gitfat
git commit -m'Initial fat repository'
# Add content to repo
echo 'fat content a' > a.fat
git add a.fat
git commit -m'add a.fat'
echo 'fat content b' > b.fat
git add b.fat
git commit -m'add b.fat'
echo 'revise fat content a' > a.fat
git commit -am'revise a.fat'
curl https://nodeload.github.com/jedbrown/git-fat/tar.gz/master -o master.tar.gz
git add master.tar.gz
git commit -am'add gz file'
git fat push


# Clone first repo into second
cd ..
git clone fat-test fat-test2
cd fat-test2
git fat init
git fat pull
