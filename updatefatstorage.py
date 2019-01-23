#!/usr/bin/python

"""
script to update fat storage file name from something like

a08929b5b00f6e9fbb60e013a0024805c75e9d42
to
a0/8929b5b00f6e9fbb60e013a0024805c75e9d42

If one folder has too many files, the performance won't be very good.

git-fat design is rather simple, to update storage, assume your files are
stored in 
/git_storage_folder

Run the following command:

    cd /git_storage_folder
    updatefatstorage.py

You need to change your local storage format too
assume your git working tree is
/your_git_working_tree

    cd /your_git_working_tree/.git/fat/objects
    updatefatstorage.py

G. T. 
1-23-2019

"""

import os

def mkdir_p(path):
    import errno
    try:
        os.makedirs(path)
    except OSError as exc: # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: raise

flist = os.listdir('.')
for fname in flist:
    if len(fname) == 40:
        ofname = fname[:2] + '/' + fname[2:]
        mkdir_p(os.path.dirname(ofname))
        os.rename(fname, ofname)
        print(ofname)

