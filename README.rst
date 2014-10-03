git-fat
=======

A tool for managing large binary files in git repositories.

Introduction
------------

Git-fat is a tool written by `jedbrown <https://github.com/jedbrown/git-fat>`_.
This repository / pypi package is a fork which we are
`actively trying to resolve <https://github.com/jedbrown/git-fat/pull/19>`_.
With that said, the repository placeholder format is compatible with both, so
they should be interchangable for now.  Please take care to check which one
you are using before opening issues on either repository, and include as much
information as possible so that we are able to help you as best we can.

Now an explination about what (either) ``git-fat`` does:

Checking large binary files into a distributed version control system is
a bad idea because repository size quickly becomes unmanagable. Numerous
operations take longer to complete and fresh clones become something
that you start and wait for a bit before coming back to them.
Using ``git-fat`` allows you to separate the storage of largefiles from
the source while still having them in the working directory for your project.

Features
--------

-  Cloning the source code remains fast because binaries are not
   included
-  Binary files really exist in your working directory and are not
   soft-links
-  Only depends on Python 2.7 and a backend
-  Supports anonymous downloads of files over http

Installation
------------

You can install ``git-fat`` using pip.

::

    pip install git-fat

Or you can install it simply by placing it on your path.

::

    curl https://raw.github.com/cyaninc/git-fat/master/git_fat/git_fat.py \
    | sudo tee /usr/local/bin/git-fat && sudo chmod +x /usr/local/bin/git-fat

Usage
-----

First, create a
`git attributes <http://git-scm.com/book/en/Customizing-Git-Git-Attributes>`_
file in the root of your repository. This file determines which files
get converted to ``git-fat`` files.

::

    cat >> .gitattributes <<EOF
    *.deb filter=fat -crlf
    *.gz filter=fat -crlf
    *.zip filter=fat -crlf
    EOF

Next, create a ``.gitfat`` configuration file in the root of your repo
that contains the location of the remote store for the binary files.
Optionally include the ssh user and port if non-standard. Also,
optionally include an http remote for anonymous clones.

::

    [rsync]
    remote = storage.example.com:/path/to/store
    user = git
    port = 2222
    [http]
    remote = http://storage.example.com/store

Commit those files so that others will be able to use them.

Initalize the repository. This adds a line to ``.git/config`` telling
git what command to run for the ``fat`` filter is in the
``.gitattributes`` file.

::

    git fat init

Now when you add a file that matches a pattern in the ``.gitattributes``
file, it will be converted to a fat placeholder file before getting
commited to the repository. After you've added a file **remember to push
it to the fat store**, otherwise people won't get the binary file when
they try to pull fat-files.

::

    git fat push

After we've done a new clone of a repository using ``git-fat``, to get
the additional files we do a fat pull.  This will pull the default backend
as determined by the first entry in the ``.gitfat`` file for the repo.

::

    git fat pull

To specify which backend to use when pulling or pushing files, then simply
list the backend type after the pull or push command.

::

    git fat pull http

To list the files managed by ``git-fat``

::

    git fat list

To get a summary of the orphan and stale files in the repository

::

    git fat status

Orphans are files that exist as placeholders in the working copy. Stale
files are files that are in the ``.git/fat/objects`` directory, but have
no working copy associated with them (e.g. old versions of files).

To find files over a certain size, use git fat find. This example finds
all objects greater than 10MB in git's database and prints them out.

::

    git fat find 10485760

Implementation notes
--------------------

For many commands, ``git-fat`` by default only checks the current
``HEAD`` for placeholder files to clone. This can save on bandwidth for
frequently changing large files and also saves on processing time for
very large repositories. To force commands to search the entire history
for placeholders and pull all files, call ``git-fat`` with ``-a``. e.g.

::

    git fat -a pull

If you add ``git-fat`` to an existing repository, the default behavior
is to not convert existing binary files to ``git-fat``. Converting a
file that already exists in the history for git would not save any
space. Once the file is changed or renamed, it will then be added to the
fat store.

To setup an http server to accept ``git-fat`` requests, just configure a
webserver to have a url serve up the ``git-fat`` directory on the
server, and point the ``.gitfat`` http remote to that url.

Retroactive Import
------------------

You can retroactively import a repository to ``git-fat`` using a combination
of ``find`` and ``index-filter`` used with git's ``filter-branch`` command.

Before you do this, make sure you understand the consequences of
`rewriting history <http://git-scm.com/book/ch6-4.html>`_ and be sure to
backup your repository before starting.

First, clone the repository and find all the large files with the
``git fat find`` command.

::

    darthurdent at betelgeuse in /tmp/git-fat-demo (master)
    $ git fat find 5123123
    761a63bf287867da92eb420fca515363c4b02ad1 9437184 flowerpot.tar.gz
    6c5d4031e03408e34ae476c5053ee497a91ac37b 10485760 whale.tar.gz


Review the files and make sure that they're what you want to exclude from the
repository.  If the list looks good, put the filenames into another file that
will be read from during ``filter-branch``.

::

    darthurdent at betelgeuse in /tmp/git-fat-demo (master)
    $ git fat find 5123123 | cut -d' ' -f3- > /tmp/towel

    darthurdent at betelgeuse in /tmp/git-fat-demo (master)
    $ cat /tmp/towel
    flowerpot.tar.gz
    whale.tar.gz

    darthurdent at betelgeuse in /tmp/git-fat-demo (master)
    $ ll
    total 19M
    drwxrwxr-x 3 darthurdent darthurdent 4.0K Dec 10 13:42 .
    drwxrwxrwt 6 root         root          76K Dec 10 13:42 ..
    drwxrwxr-x 6 darthurdent darthurdent 4.0K Dec 10 13:42 .git
    -rw-r--r-- 1 darthurdent darthurdent 9.0M Dec 10 13:37 flowerpot.tar.gz
    -rw-r--r-- 1 darthurdent darthurdent  10M Dec 10 13:37 whale.tar.gz

Do the ``filter-branch`` using ``git fat index-filter`` as the index filter.
Pass in the filename containing the paths to files you want to exclude.

::

    darthurdent at betelgeuse in /tmp/git-fat-demo (master)
    $ git filter-branch --index-filter 'git fat index-filter /tmp/towel'\
        --tag-name-filter cat -- --all
    Rewrite 28cfba441aac92992c3f80dae97cd1c19b3befad (2/2)
    Ref 'refs/heads/master' was rewritten

Review the changes made to the repository.

::

    darthurdent at betelgeuse in /tmp/git-fat-demo (master)
    $ ll
    total 19M
    drwxrwxr-x 3 darthurdent darthurdent 4.0K Dec 10 13:42 .
    drwxrwxrwt 6 root         root          76K Dec 10 13:42 ..
    drwxrwxr-x 6 darthurdent darthurdent 4.0K Dec 10 13:42 .git
    -rw-rw-r-- 1 darthurdent darthurdent   64 Dec 10 13:42 .gitattributes
    -rw-rw-r-- 1 darthurdent darthurdent 9.0M Dec 10 13:42 flowerpot.tar.gz
    -rw-rw-r-- 1 darthurdent darthurdent  10M Dec 10 13:42 whale.tar.gz

    darthurdent at betelgeuse in /tmp/git-fat-demo (master)
    $ cat .gitattributes
    flowerpot.tar.gz filter=fat -text
    whale.tar.gz filter=fat -text

    darthurdent at betelgeuse in /tmp/git-fat-demo (master)
    $ git cat-file -p $(git hash-object whale.tar.gz)
    #$# git-fat 8c206a1a87599f532ce68675536f0b1546900d7a             10485760

Remove all the old and dangling references by doing a clone of the repository
you just cleaned.  The ``file://`` uri is
`important <http://git-scm.com/book/ch4-1.html>`_ here.

::

    darthurdent at betelgeuse in /tmp/git-fat-demo (master)
    $ cd .. && git clone file://git-fat-demo git-fat-clean

Related projects
----------------

-  `git-annex <http://git-annex.branchable.com>`_ is a far more
   comprehensive solution, but was designed for a more distributed use
   case and has more dependencies.
-  `git-media <https://github.com/schacon/git-media>`_ adopts a similar
   approach to ``git-fat``, but with a different synchronization
   philosophy and with many Ruby dependencies.

Development
-----------

To run the tests, simply run ``python setup.py test``.

To use the development version of ``git-fat`` for manual testing, run
``pip install -U .`` (suggest doing that in a virtualenv).

Master branch is a stable branch with the latest release at the HEAD.


Improvements
------------

-  Better Documentation (esp. setting up a server)
-  Improved Testing
-  config file location argument (global)
-  cli option to specify which backend to use for push and pull (http, rsync, etc)
-  Python 3 compatability (without six)
-  Really implement pattern matching
-  Git hooks
