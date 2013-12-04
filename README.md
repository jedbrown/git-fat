git-fat
=======

A tool for managing large binary files in git repositories.

Introduction
------------

Checking large binary files into a distributed version control system is a bad idea because repository size quickly
becomes unmanagable. Every operation takes longer to complete and fresh clones become something that you do start
doing overnight. Binary files do not have clean diffs and as a result do not compress well. Using git-fat allows you to
separate the storage of largefiles from the source while still having them in the working directory for your project.

Features
--------

- Cloning the source code remains fast because binaries are not included
- Binary files really exist in your working directory and are not soft-links
- Only depends on Python 2.7, rsync and ssh
- Download only the files you need with pattern matching
- Supports anonymous downloads of files over http

Installation
------------

You can install git-fat using pip.

    pip install git-fat

Or you can install it simply by placing it on your path.

    curl https://raw.github.com/cyaninc/git-fat/master/git_fat/git_fat.py \
    | sudo tee /usr/local/bin/git-fat && sudo chmod +x /usr/local/bin/git-fat

Usage
-----

First, create a [`.gitattributes`](http://git-scm.com/book/en/Customizing-Git-Git-Attributes) file in the
root of your repository.  This file determines which files get converted to git-fat files.

    cat >> .gitattributes <<EOF
    *.deb filter=fat -crlf
    *.gz filter=fat -crlf
    *.zip filter=fat -crlf
    EOF

Next, create a `.gitfat` configuration file in the root of your repo that contains the location of the
remote store for the binary files. Optionally include the ssh user and port if non-standard. Also,
optionally include an http remote for anonymous clones.

    [rsync]
    remote = storage.example.com:/path/to/store
    user = git
    port = 2222
    [http]
    remote = http://storage.example.com/store

Commit those files so that others will be able to use them.

Initalize the repository.  This adds a line to `.git/config` telling git what command to run for the `fat`
filter is in the `.gitattributes` file.

    git fat init

Now when you add a file that matches a pattern in the `.gitattributes` file, it will be converted to a fat placeholder
file before getting commited to the repository. After you've added a file **remember to push it to the fat store**,
otherwise people won't get the binary file when they try to pull fat-files.

    git fat push

After we've done a new clone of a repository using git-fat, to get the additional files we do a fat pull.

    git fat pull

Or if you're doing an anonymous pull, and the repository managers support it.

    git fat pull-http

To list the files managed by git-fat

    git fat list

To get a summary of the orphans and stale files in the repository

    git fat status

Orphans are files that exist as placeholders in the working copy.  Stale files are files that are in the
`.git/fat/objects` directory, but have no working copy associated with them (e.g. old versions of files).

Implementation notes
--------------------

For many commands, `git-fat` by default only checks the current `HEAD` for placeholder files to clone. This can
save on bandwidth for frequently changing large files and also saves on processing time for very large repositories.
To force commands to search the entire history for placeholders and pull all files, call `git-fat` with `-a`. e.g.

    git fat -a pull

If you add `git-fat` to an existing repository, the default behavior is to not convert existing binary files to
git-fat. Converting a file that already exists in the history for git would not save any space. Once the file is
changed or renamed, it will then be added to the fat store.

To setup an http server to accept git-fat requests, just configure a webserver to have a url serve up the git-fat
directory on the server, and point the `.gitfat` http remote to that url.

Related projects
----------------

- [git-annex](http://git-annex.branchable.com) is a far more comprehensive solution, but designed for a more distributed use case and has more dependencies.
- [git-media](https://github.com/schacon/git-media) adopts a similar approach to `git-fat`, but with a different synchronization philosophy and with many Ruby dependencies.

Improvements
------------

- More friendly configuration for multiple fat remotes
- Private setting of a different remote.
