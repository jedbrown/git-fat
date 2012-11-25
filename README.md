# Installation and configuration
Place `git-fat` in your `PATH`.

To use `git-fat` edit `.gitattributes` to regard any desired extensions
as fat files, e.g.

    *.png filter=fat -crlf
    *.jpg filter=fat -crlf
    *.gz  filter=fat -crlf

then run `git fat init` to active the extension. Now add and commit as
usual, all matched files will not go in `.git/objects`, but will appear
complete in the working tree. To set a remote store for the fat objects,
edit `.gitfat`

    [rsync]
    remote = your.remote-host.org:/share/fat-store

This file should typically be committed to the repository so that others
will automatically have their remote set. This remote address can use
any protocol supported by rsync. Most users will configure it to use
remote ssh in a directory with shared access.

# A worked example

    $ export GIT_FAT_VERBOSE=1              # Show more verbose information about what is happening
    $ git init repo
    Initialized empty Git repository in /tmp/repo/.git/
    $ cd repo
    $ git fat init
    $ cat > .gitfat
    [rsync] 
    remote = localhost:/tmp/fat-store
    $ mkdir -p /tmp/fat-store               # make sure the remote directory exists
    $ echo '*.gz filter=fat -crlf' > .gitattributes
    $ git add .gitfat .gitattributes
    $ git commit -m'Initial repository'
    [master (root-commit) eb7facb] Initial repository
     2 files changed, 3 insertions(+)
     create mode 100644 .gitattributes
     create mode 100644 .gitfat
    $ curl https://nodeload.github.com/jedbrown/git-fat/tar.gz/master -o master.tar.gz
      % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                     Dload  Upload   Total   Spent    Left  Speed
    100  6449  100  6449    0     0   7741      0 --:--:-- --:--:-- --:--:--  9786
    $ git add master.tar.gz
    git-fat filter-clean: caching to /tmp/repo/.git/fat/objects/b3489819f81603b4c04e8ed134b80bace0810324
    $ git commit -m'Added master.tar.gz'
    [master b85a96f] Added master.tar.gz
    git-fat filter-clean: caching to /tmp/repo/.git/fat/objects/b3489819f81603b4c04e8ed134b80bace0810324
     1 file changed, 1 insertion(+)
     create mode 100644 master.tar.gz
    $ du -s .git/objects .git/fat
    $ git fat push
    Pushing to localhost:/tmp/fat-store
    building file list ... 
    1 file to consider
    
    sent 61 bytes  received 12 bytes  48.67 bytes/sec
    total size is 6449  speedup is 88.34

We could now push to a remote 

    $ cd ..
    $ git clone repo repo2
    Cloning into 'repo2'...
    done.
    $ cd repo2
    $ git fat init                          # don't forget
    $ git fat pull
    receiving file list ... 
    1 file to consider
    1f218834a137f7b185b498924e7a030008aee2ae
            6449 100%    6.15MB/s    0:00:00 (xfer#1, to-check=0/1)
    
    sent 30 bytes  received 6558 bytes  4392.00 bytes/sec
    total size is 6449  speedup is 0.98
    $ cat master.tar.gz                     # we should checkout automatically
    #$# git-fat 1f218834a137f7b185b498924e7a030008aee2ae
    $ git checkout -f .
    git-fat filter-clean: caching to /tmp/repo2/.git/fat/objects/b7939480ed4e54109f8f82d43e46a39e144ecad1
    git-fat filter-smudge: restoring from /tmp/repo2/.git/fat/objects/1f218834a137f7b185b498924e7a030008aee2ae
    $ ls -l                                 # recovered the full file
    total 8
    -rw-r--r-- 1 jed users 6449 Nov 25 17:10 master.tar.gz

# Important refinements
* Put some more useful message in smudged (working tree) version of missing files.
* Make 
* Make commands safer in presence of a dirty tree.
* Private setting of a different remote.
* Gracefully handle unmanaged files when the filter is called (either
  legacy files or files matching the pattern that should some reason not
  be treated as fat).
