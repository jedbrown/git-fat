#!/usr/bin/env python
# -*- mode:python -*-

from __future__ import print_function, with_statement

import sys
import hashlib
import tempfile
import os
import subprocess as sub
from subprocess import CalledProcessError
import itertools
import threading
import time
import collections
from multiprocessing import Process, Manager
from datetime import datetime as dt

try:
    from subprocess import check_output
    del check_output  # noqa

except ImportError:

    def backport_check_output(*popenargs, **kwargs):
        '''
        Run command with arguments and return its output as a byte string.
        Backported from Python 2.7 as it's implemented as pure python on stdlib.

        >> check_output(['/usr/bin/python', '--version'])
        Python 2.6.2
        '''
        process = sub.Popen(stdout=sub.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            error = sub.CalledProcessError(retcode, cmd)
            error.output = output
            raise error
        return output

    sub.check_output = backport_check_output

BLOCK_SIZE = 4096


def git(cliargs, *args, **kwargs):
    ''' Calls git commands with Popen arguments '''
    return sub.Popen(['git'] + cliargs, *args, **kwargs)


def verbose_stderr(*args, **kwargs):
    return print(*args, file=sys.stderr, **kwargs)


def verbose_ignore(*args, **kwargs):
    pass


def mkdir_p(path):
    import errno
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def umask():
    '''
    Get umask without changing it.
    '''
    old = os.umask(0)
    os.umask(old)
    return old


def readblocks(stream):
    '''
    Reads BLOCK_SIZE from stream and yields it
    '''
    while True:
        data = stream.read(BLOCK_SIZE)
        if not data:
            break
        yield data



def cat_iter(initer, outstream):
    for block in initer:
        outstream.write(block)


def cat(instream, outstream):
    return cat_iter(readblocks(instream), outstream)


def gitconfig_get(name, file=None):
    args = ['config', '--get']
    if file is not None:
        args += ['--file', file]
    args.append(name)
    p = git(args, stdout=sub.PIPE)
    output = p.communicate()[0].strip()
    if p.returncode != 0:
        return ''
    else:
        return output


def gitconfig_set(name, value, file=None):
    args = ['git', 'config']
    if file is not None:
        args += ['--file', file]
    args += [name, value]
    sub.check_call(args)


class GitFat(object):

    def __init__(self):
        self.verbose = verbose_stderr if os.environ.get('GIT_FAT_VERBOSE') else verbose_ignore
        try:
            self.gitroot = sub.check_output('git rev-parse --show-toplevel'.split()).strip()
        except sub.CalledProcessError:
            sys.stderr.write('git-fat must be run from a git directory\n')
            sys.exit(1)
        self.gitdir = sub.check_output('git rev-parse --git-dir'.split()).strip()
        self.objdir = os.path.join(self.gitdir, 'fat', 'objects')
        self.cfgpath = os.path.join(self.gitroot, (gitconfig_get('gitfat.config') or '.gitfat'))

        if os.environ.get('GIT_FAT_VERSION') == '1':
            self.encode = self.encode_v1
        else:
            self.encode = self.encode_v2

        def magiclen(enc):
            return len(enc(hashlib.sha1('dummy').hexdigest(), 5))

        self.magiclen = magiclen(self.encode)  # Current version
        self.magiclens = [magiclen(enc) for enc in [self.encode_v1, self.encode_v2]]  # All prior versions

    def _rsync_opts(self):
        '''
        Read rsync options from config
        '''
        remote = gitconfig_get('rsync.remote', file=self.cfgpath)
        ssh_port = gitconfig_get('rsync.sshport', file=self.cfgpath)
        ssh_user = gitconfig_get('rsync.sshuser', file=self.cfgpath)
        if remote is None:
            raise RuntimeError('No rsync.remote in %s' % self.cfgpath)
        return remote, ssh_port, ssh_user

    def _rsync(self, push):
        '''
        Construct the rsync command
        '''
        (remote, ssh_port, ssh_user) = self._rsync_opts()
        if push:
            self.verbose('Pushing to %s' % (remote))
        else:
            self.verbose('Pulling from %s' % (remote))

        cmd = ['rsync', '--progress', '--ignore-existing', '--from0', '--files-from=-']
        rshopts = ''
        if ssh_user:
            rshopts += ' -l ' + ssh_user
        if ssh_port:
            rshopts += ' -p ' + ssh_port
        if rshopts:
            cmd.append('--rsh=ssh' + rshopts)
        if push:
            cmd += [self.objdir + '/', remote + '/']
        else:
            cmd += [remote + '/', self.objdir + '/']
        return cmd

    def encode_v1(self, digest, bytes):
        'Produce legacy representation of file to be stored in repository.'
        return '#$# git-fat %s\n' % (digest, )

    def encode_v2(self, digest, bytes):
        'Produce representation of file to be stored in repository. 20 characters can hold 64-bit integers.'
        return '#$# git-fat %s %20d\n' % (digest, bytes)

    def _decode(self, stream):
        '''
        Returns iterator and True if stream is git-fat object
        '''
        cookie = '#$# git-fat '
        stream_iter = readblocks(stream)
        # Read block for check
        block = next(stream_iter)

        def prepend(blk, iterator):
            yield blk
            for i in iterator:
                yield i

        # Put block back
        ret = prepend(block, stream_iter)
        if block.startswith(cookie):
            assert(len(block) == self.magiclen)  # Sanity check
            return ret, True
        return ret, False

    def _get_digest(self, stream):
        '''
        Returns digest if stream is fatfile placeholder or '' if not
        '''
        stream, fatfile = self._decode(stream)
        if fatfile:
            block = next(stream)  # read the first block
            digest = block.split()[2]
            return digest
        return ''

    def _cached_objects(self):
        '''
        Returns a set of all the cached objects
        '''
        return set(os.listdir(self.objdir))

    def _referenced_objects(self, **kwargs):
        '''
        Return just the hashes of the files that are referenced in the repository
        '''
        objs_dict = self._managed_files(**kwargs)
        return set(objs_dict.keys())

    def _managed_files(self, rev=None, full_history=False):
        '''
        Finds managed files in the specified revision
        '''
        rev = rev or 'HEAD'
        # full_history implies --all
        args = ['--all'] if full_history else ['--no-walk', rev]

        # Get all the git objects in the current revision and in history if --all is specified
        revlist = git('rev-list --objects'.split() + args, stdout=sub.PIPE)
        # Grab only the first column.  Tried doing this in python but because of the way that
        # subprocess.PIPE buffering works, I was running into memory issues with larger repositories
        # plugging pipes to other subprocesses appears to not have the memory buffer issue
        awk = sub.Popen(['awk', '{print $1}'], stdin=revlist.stdout, stdout=sub.PIPE)
        # Read the objects and print <sha> <type> <size>
        catfile = git('cat-file --batch-check'.split(), stdin=awk.stdout, stdout=sub.PIPE)

        # Find any objects that are git-fat placeholders which are tracked in the repository
        managed = {}
        for line in catfile.stdout:
            objhash, objtype, size = line.split()
            # files are of blob type
            if objtype == 'blob' and int(size) in self.magiclens:
                # Read the actual file contents
                readfile = git(['cat-file', '-p', objhash], stdout=sub.PIPE)
                digest = self._get_digest(readfile.stdout)
                if digest:
                    managed[objhash] = digest
        catfile.wait()

        # go through rev-list again to get the filenames
        # Again, I tried avoiding making another call to rev-list by caching the
        # filenames above, but was running into the memory buffer issue
        # Instead we just make another call to rev-list.  Takes more time, but still
        # only takes 5 seconds to traverse the entire history of a 22k commit repo
        filedict = {}
        revlist2 = git('rev-list --objects'.split() + args, stdout=sub.PIPE)
        for line in revlist2.stdout:
            hashobj = line.split()
            # Revlist prints all objects (commits, trees, blobs) but blobs have the file path
            # next to the git objecthash
            if len(hashobj) == 2:
                # If the object is one we're managing
                if hashobj[0] in managed.keys():
                    filedict[hashobj[0]] = hashobj[1]
        revlist2.wait()

        # return a dict(git-fat hash -> filename)
        # git's objhash are the keys in `managed` and `filedict`
        ret = dict((j, filedict[i]) for i,j in managed.iteritems())
        return ret

    def _orphan_files(self, patterns=[]):
        '''
        generator for placeholders in working tree that match pattern
        '''
        # Null-terminated for proper file name handling
        sys.stderr.write('In orphan_files\n')
        for fname in sub.check_output(['git', 'ls-files', '-z'] + patterns).split('\x00')[:-1]:
            stat = os.lstat(fname)
            if stat.st_size != self.magiclen or os.path.islink(fname):
                continue
            with open(fname) as f:
                digest = self._get_digest(f)
                if digest:
                    yield (digest, fname)

    def _filter_smudge(self, instream, outstream):
        '''
        The smudge filter runs whenever a file is being checked out into the working copy of the tree
        instream is sys.stdin and outstream is sys.stdout when it is called by git
        '''
        sys.stderr.write('In filter_smudge\n')
        stream, fatfile = self._decode(instream)
        if fatfile:
            block = next(stream)  # read the first block
            digest = block.split()[2]
            objfile = os.path.join(self.objdir, digest)
            try:
                cat(open(objfile), outstream)
                self.verbose('git-fat filter-smudge: restoring from %s' % objfile)
            except IOError:
                self.verbose('git-fat filter-smudge: fat object not found in cache %s' % objfile)
                outstream.write(block)
        else:
            self.verbose('git-fat filter-smudge: not a managed file')
            cat_iter(stream, sys.stdout)

    def _filter_clean(self, instream, outstream):
        '''
        The clean filter runs when a file is added to the index. It gets the "smudged" (working copy)
        version of the file on stdin and produces the "clean" (repository) version on stdout.
        '''

        self.verbose("In filter clean for file {}".format(sys.argv[2]))
        hasher = hashlib.new('sha1')
        bytes = 0
        fd, tmpname = tempfile.mkstemp(dir=self.objdir)
        cached = False

        try:
            blockiter, is_placeholder = self._decode(instream)

            # Open the temporary file for writing
            ostream = outstream

            # if it's not a git-fat placeholder file, cache it
            if not is_placeholder:
                ostream = os.fdopen(fd, 'w')

            for block in blockiter:
                # Add the block to be hashed
                hasher.update(block)
                bytes += len(block)
                ostream.write(block)

            ostream.flush()
            digest = hasher.hexdigest()
            objfile = os.path.join(self.objdir, digest)

            # Create placeholder for the file
            if not is_placeholder:
                # Close temporary file
                ostream.close()
                if os.path.exists(objfile):
                    self.verbose('git-fat filter-clean: cached file already exists %s' % objfile)
                    os.remove(tmpname)
                else:
                    # Set permissions for the new file using the current umask
                    os.chmod(tmpname, int('444', 8) & ~umask())
                    os.rename(tmpname, objfile)
                    self.verbose('git-fat filter-clean: caching to %s' % objfile)
                cached = True
                # Write placeholder to index
                outstream.write(self.encode(digest, bytes))
        finally:
            # cleanup always
            if not cached:
                os.remove(tmpname)

    def filter_clean(self, cur_file, **kwargs):
        '''
        Public command to do the clean (should only be called by git)
        '''
        if self.can_clean_file(cur_file):
            self._filter_clean(sys.stdin, sys.stdout)
        else:
            verbose_stderr(
                "Not adding: {}\n".format(cur_file) +
                "It is not a new file and is not managed by git-fat"
            )
            cat(sys.stdin, sys.stdout)

    def filter_smudge(self, **kwargs):
        '''
        Public command to do the smudge (should only be called by git)
        '''
        self._filter_smudge(sys.stdin, sys.stdout)

    def list_files(self, **kwargs):
        '''
        Command to list the files by fat-digest -> gitroot relative path
        '''
        managed = self._managed_files(**kwargs)
        for f in managed.keys():
            print(f, managed.get(f))

    def checkout(self, show_orphans=False, **kwargs):
        '''
        Update any stale files in the present working tree
        '''
        for digest, fname in self._orphan_files():
            objpath = os.path.join(self.objdir, digest)
            if os.access(objpath, os.R_OK):
                print('Restoring %s -> %s' % (digest, fname))
                # The output of our smudge filter depends on the existence of
                # the file in .git/fat/objects, but git caches the file stat
                # from the previous time the file was smudged, therefore it
                # won't try to re-smudge. There's no git command to specifically
                # invalidate the index cache so we have two options:
                # Change the file stat mtime or change the file size. However, since
                # the file mtime only has a granularity of 1s, if we're doing a pull
                # right after a clone or checkout, it's possible that the modified
                # time will be the same as in the index. Git knows this can happen
                # so git checks the file size if the modified time is the same.
                # The easiest way around this is just to remove the file we want
                # to replace (since it's an orphan, it should be a placeholder)
                with open(fname,'r') as f:
                    if self._get_digest(f):  # One last sanity check
                        os.remove(fname)
                # This re-smudge is essentially a copy that restores permissions.
                sub.check_call(['git', 'checkout-index', '--index', '--force', fname])
            elif show_orphans:
                print('Data unavailable: %s %s' % (digest, fname))

    def can_clean_file(self, filename):
        '''
        Checks to see if the current file exists in the local repo before filter-clean
        This method prevents fat from hijacking glob matches that are old
        '''
        # If the file doesn't exist in the immediately previous revision, add it
        showfile = git('show HEAD:{}'.format(filename).split(), stdout=sub.PIPE, stderr=sub.PIPE)
        if (showfile.wait()):
            return True
        # If it is already tracked, add it
        stream, is_fatfile = self._decode(showfile.stdout)
        return is_fatfile

    def checkconfig(self):
        '''
        Returns true if git-fat is already configured
        '''
        return gitconfig_get('filter.fat.clean') and gitconfig_get('filter.fat.smudge')

    def pull(self, pattern=None, **kwargs):
        '''
        Pull anything that I have referenced, but not stored
        '''
        cached_objs = self._cached_objects()
        sys.stderr.write(str(cached_objs)+'\n')
        if pattern:
            # filter the working tree by a pattern
            files = set(digest for digest, fname in self._orphan_files(patterns=[pattern])) - cached_objs
        else:
            # default pull any object referenced but not stored
            files = self._referenced_objects(**kwargs) - cached_objs

        if files:
            print("Pulling: ", list(files))
            rsync = self._rsync(push=False)
            self.verbose('Executing: {}'.format(rsync))
            p = sub.Popen(rsync, stdin=sub.PIPE, preexec_fn=os.setsid)
            p.communicate(input='\x00'.join(files))
        else:
            print("You've got everything! d(^_^)b")

        self.checkout()

    def push(self, **kwargs):
        '''
        Push anything that I have stored and referenced (rsync doesn't push if exists on remote)
        '''
        # Default to push only those objects referenced by current HEAD
        # (includes history). Finer-grained pushing would be useful.
        files = self._referenced_objects(**kwargs) & self._cached_objects()
        rsync = self._rsync(push=True)
        self.verbose('Executing: {}'.format(rsync))
        p = sub.Popen(rsync, stdin=sub.PIPE)
        p.communicate(input='\x00'.join(files))

    def init(self, **kwargs):
        '''
        Create cache directory and setup filters in .git/config
        '''
        mkdir_p(self.objdir)
        gitconfig_set('filter.fat.clean', 'git-fat filter-clean %f')
        gitconfig_set('filter.fat.smudge', 'git-fat filter-smudge %f')
        print('Initialized git fat')

    def gc(self, **kwargs):
        '''
        Remove any objects that aren't referenced in the tree
        '''
        # Make sure user doesn't accidently delete something they didn't mean to
        if not kwargs.get("full_history"):
            kwargs.update({"full_history":True})

        garbage = self._cached_objects() - self._referenced_objects(**kwargs)

        print('Unreferenced objects to remove: %d' % len(garbage))
        for obj in garbage:
            fname = os.path.join(self.objdir, obj)
            print('%10d %s' % (os.stat(fname).st_size, obj))
            os.remove(fname)

    def status(self, **kwargs):
        '''
        Show orphan (in tree, but not in cache) and garbage (in cache, but not in tree) objects, if any.
        '''
        catalog = self._cached_objects()
        referenced = self._referenced_objects(**kwargs)
        garbage = catalog - referenced
        orphans = referenced - catalog
        if orphans:
            print('Orphan objects:')
            for orph in orphans:
                print('\t' + orph)
        if garbage:
            print('Garbage objects:')
            for g in garbage:
                print('\t' + g)

if __name__ == '__main__':

    import argparse

    fat = GitFat()

    parser = argparse.ArgumentParser()
    subparser = parser.add_subparsers()

    parser.add_argument('-a', "--full-history", dest='full_history', action='store_true',
        help='Look for git-fat placeholder files in the entire history instead of just the working copy')

    parser_init = subparser.add_parser('init', help='Initialize git-fat')
    parser_init.set_defaults(func=fat.init)

    parser_filter_clean = subparser.add_parser('filter-clean', help='filter-clean to be called only by git')
    parser_filter_clean.add_argument("cur_file")
    parser_filter_clean.set_defaults(func=fat.filter_clean)

    parser_filter_smudge = subparser.add_parser('filter-smudge', help='filter-smudge to be called only by git')
    parser_filter_smudge.add_argument("cur_file")  # Currently unused
    parser_filter_smudge.set_defaults(func=fat.filter_smudge)

    parser_push = subparser.add_parser('push', help='push cache to remote git-fat server')
    parser_push.set_defaults(func=fat.push)

    parser_pull = subparser.add_parser('pull', help='pull fatfiles from remote git-fat server')
    parser_pull.add_argument("pattern", nargs="?", help='pull only files matching pattern')
    parser_pull.set_defaults(func=fat.pull)

    parser_checkout = subparser.add_parser('checkout', help='resmudge all orphan objects')
    parser_checkout.set_defaults(func=fat.checkout)

    parser_status = subparser.add_parser('status', help='print orphan and garbage objects')
    parser_status.set_defaults(func=fat.status)

    parser_list = subparser.add_parser('list', help='list all files managed by git-fat')
    parser_list.set_defaults(func=fat.list_files)

    parser_gc = subparser.add_parser('gc', help='remove all garbage files in cache (files without placeholders)')
    parser_gc.set_defaults(func=fat.gc)

    args = parser.parse_args()

    if not fat.checkconfig() and args.func != fat.init:
        sys.stderr.write("Git fat not configured, first run: git fat init\n")
        sys.exit(1)

    kwargs = dict(vars(args))
    del kwargs['func']

    args.func(**kwargs)

