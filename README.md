# Installation and configuration
Place `git-fat` in your `PATH`.

Edit `.gitattributes` to regard any desired extensions as fat files.

    $ cat >> .gitattributes
    *.png filter=fat -crlf
    *.jpg filter=fat -crlf
    *.gz  filter=fat -crlf
    ^D

Run `git fat init` to active the extension. Now add and commit as usual.
Matched files will be transparently stored externally, but will appear
complete in the working tree.

Set a remote store for the fat objects by editing `.gitfat`.

    [rsync]
    remote = your.remote-host.org:/share/fat-store

This file should typically be committed to the repository so that others
will automatically have their remote set. This remote address can use
any protocol supported by rsync. Most users will configure it to use
remote ssh in a directory with shared access.

# A worked example

Before we start, let's turn on verbose reporting so we can see what's
happening. Without this environment variable, all the output lines
starting with `git-fat` will not be shown.

    $ export GIT_FAT_VERBOSE=1

First, we create a repository and configure it for use with `git-fat`.

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

Now we add a binary file whose name matches the pattern we set in `.gitattributes`.

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

The patch itself is very simple and does not include the binary.

    $ git show --pretty=oneline HEAD
    918063043a6156172c2ad66478c6edd5c7df0217 Add master.tar.gz
    diff --git a/master.tar.gz b/master.tar.gz
    new file mode 100644
    index 0000000..12f7d52
    --- /dev/null
    +++ b/master.tar.gz
    @@ -0,0 +1 @@
    +#$# git-fat 1f218834a137f7b185b498924e7a030008aee2ae

## Pushing fat files
Now let's push our fat files using the rsync configuration that we set up earlier.

    $ git fat push
    Pushing to localhost:/tmp/fat-store
    building file list ...
    1 file to consider

    sent 61 bytes  received 12 bytes  48.67 bytes/sec
    total size is 6449  speedup is 88.34

We we might normally set a remote now and push the git repository.

## Cloning and pulling
Now let's look at what happens when we clone.

    $ cd ..
    $ git clone repo repo2
    Cloning into 'repo2'...
    done.
    $ cd repo2
    $ git fat init                          # don't forget
    $ ls -l                                 # file is just a placeholder
    total 4
    -rw-r--r--  1 jed  users  53 Nov 25 22:42 master.tar.gz
    $ cat master.tar.gz                     # holds the SHA1 of the file
    #$# git-fat 1f218834a137f7b185b498924e7a030008aee2ae

We can always get a summary of what fat objects are missing in our local cache.

    Orphan objects:
    1f218834a137f7b185b498924e7a030008aee2ae

Now get any objects referenced by our current `HEAD`. This command also
accepts the `--all` option to pull full history, or a revspec to pull
selected history.

    $ git fat pull
    receiving file list ...
    1 file to consider
    1f218834a137f7b185b498924e7a030008aee2ae
            6449 100%    6.15MB/s    0:00:00 (xfer#1, to-check=0/1)
    
    sent 30 bytes  received 6558 bytes  4392.00 bytes/sec
    total size is 6449  speedup is 0.98
    Restoring 1f218834a137f7b185b498924e7a030008aee2ae -> master.tar.gz
    git-fat filter-smudge: restoring from /tmp/repo2/.git/fat/objects/1f218834a137f7b185b498924e7a030008aee2ae

Everything is in place

    $ git status
    git-fat filter-clean: caching to /tmp/repo2/.git/fat/objects/1f218834a137f7b185b498924e7a030008aee2ae
    # On branch master
    nothing to commit, working directory clean
    $ ls -l                                 # recovered the full file
    total 8
    -rw-r--r-- 1 jed users 6449 Nov 25 17:10 master.tar.gz

## Summary
* Set the "fat" file types in `.gitattributes`.
* Use normal git commands to interact with the repository without
  thinking about what files are fat and non-fat. The fat files will be
  treated specially.
* Synchronize fat files with `git fat push` and `git fat pull`.

## Implementation notes
The actual binary files are stored in `.git/fat/objects`, leaving `.git/objects` nice and small.

    $ du -bs .git/objects
    2212    .git/objects/
    $ ls -l .git/fat/objects                # This is where the file actually goes, but that's not important
    total 8
    -rw------- 1 jed users 6449 Nov 25 17:01 1f218834a137f7b185b498924e7a030008aee2ae

# Some refinements
* Allow pulling and pushing only select files
* Relate orphan objects to file system
* Put some more useful message in smudged (working tree) version of missing files.
* More friendly configuration for multiple fat remotes
* Make commands safer in presence of a dirty tree.
* Private setting of a different remote.
* Gracefully handle unmanaged files when the filter is called (either
  legacy files or files matching the pattern that should some reason not
  be treated as fat).
* Don't append the [filter "fat"] section to .git/config if it doesn't already exist.
