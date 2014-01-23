#!/usr/bin/env python
# -*- mode:python -*-

from __future__ import print_function, with_statement

import hashlib
import os
import subprocess as sub
import sys
import tempfile

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

__version__ = '0.2.4'

BLOCK_SIZE = 4096


def git(cliargs, *args, **kwargs):
    ''' Calls git commands with Popen arguments '''
    return sub.Popen(['git'] + cliargs, *args, **kwargs)


def error(*args, **kwargs):
    return print(*args, file=sys.stderr, **kwargs)


def empty(*args, **kwargs):
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


def http_get(baseurl, filename):
    ''' Returns file descriptor for http file stream, catches urllib2 errors '''
    import urllib2
    try:
        print("Downloading: {0}".format(filename))
        geturl = '/'.join([baseurl, filename])
        res = urllib2.urlopen(geturl)
        return res.fp
    except urllib2.URLError as e:
        error("WARN: " + e.reason + ': {0}'.format(geturl))
        return None


class GitFat(object):

    def __init__(self):

        def magiclen(enc_func):
            return len(enc_func(hashlib.sha1('dummy').hexdigest(), 5))

        self._cookie = '#$# git-fat '
        self._format = self._cookie + '{digest} {size:20d}\n'
        # Legacy format support below
        if os.environ.get('GIT_FAT_VERSION'):
            self._format = self._cookie + '{digest}\n'

        self._magiclen = magiclen(self._encode)

    def configure(self, verbose=False, **kwargs):
        '''
        Configure git-fat for usage: variables, environment
        '''

        # Setup Variables
        try:
            self.gitroot = sub.check_output('git rev-parse --show-toplevel'.split()).strip()
            self.gitdir = sub.check_output('git rev-parse --git-dir'.split()).strip()
        except sub.CalledProcessError:
            error('git-fat must be run from a git directory')
            sys.exit(1)

        self.objdir = os.path.join(self.gitdir, 'fat', 'objects')
        self.cfgpath = os.path.join(self.gitroot, '.gitfat')

        self.verbose = error if verbose or os.environ.get("GIT_FAT_VERBOSE") else empty

        if not self._configured():
            print('Setting filters in .git/config')
            gitconfig_set('filter.fat.clean', 'git-fat filter-clean %f')
            gitconfig_set('filter.fat.smudge', 'git-fat filter-smudge %f')
            print('Creating .git/fat/objects')
            mkdir_p(self.objdir)
            print('Initialized git-fat')

    def _configured(self):
        '''
        Returns true if git-fat is already configured
        '''
        reqs = os.path.isdir(self.objdir)
        filters = gitconfig_get('filter.fat.clean') and gitconfig_get('filter.fat.smudge')
        return filters and reqs

    def _rsync_opts(self):
        '''
        Read rsync options from config
        '''
        if not os.path.isfile(self.cfgpath):
            error('ERROR: git-fat requires that .gitfat is present to use rsync remotes')
            sys.exit(1)

        remote = gitconfig_get('rsync.remote', file=self.cfgpath)
        if not remote:
            error('ERROR: No rsync.remote in {0}'.format(self.cfgpath))
            sys.exit(1)

        ssh_port = gitconfig_get('rsync.sshport', file=self.cfgpath)
        ssh_user = gitconfig_get('rsync.sshuser', file=self.cfgpath)
        return remote, ssh_port, ssh_user

    def _http_opts(self):
        '''
        Read http options from config
        '''
        if not os.path.isfile(self.cfgpath):
            error('ERROR: git-fat requires that .gitfat is present to use http remotes')
            sys.exit(1)

        remote = gitconfig_get('http.remote', file=self.cfgpath)
        if not remote:
            error('ERROR: No http.remote in {0}'.format(self.cfgpath))
            sys.exit(1)

        if not remote.startswith('http') or remote.startswith('https'):
            error('ERROR: http remote url must start with http:// or https://')
            sys.exit(1)

        return remote

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

    def _encode(self, digest, size):
        '''
        Produce representation of file to be stored in repository. 20 characters can hold 64-bit integers.
        '''
        return self._format.format(digest=digest, size=size)

    def _decode(self, stream):
        '''
        Returns iterator and True if stream is git-fat object
        '''
        stream_iter = readblocks(stream)
        # Read block for check raises StopIteration if file is zero length
        try:
            block = next(stream_iter)
        except StopIteration:
            return stream_iter, False

        def prepend(blk, iterator):
            yield blk
            for i in iterator:
                yield i

        # Put block back
        ret = prepend(block, stream_iter)
        if block.startswith(self._cookie):
            assert(len(block) == self._magiclen)  # Sanity check
            return ret, True
        return ret, False

    def _hash_stream(self, blockiter, outstream):
        '''
        Writes blockiter to outstream and returns the digest and bytes written
        '''
        hasher = hashlib.new('sha1')
        bytes_written = 0

        for block in blockiter:
            # Add the block to be hashed
            hasher.update(block)
            bytes_written += len(block)
            outstream.write(block)
        outstream.flush()
        return hasher.hexdigest(), bytes_written

    def _get_digest(self, stream):
        '''
        Returns digest if stream is fatfile placeholder or '' if not
        '''
        # DONT EVER CALL THIS FUNCTION FROM FILTERS, IT DISCARDS THE FIRST
        # BLOCK OF THE INPUT STREAM.  IT IS ONLY MEANT TO CHECK THE STATUS
        # OF A FILE IN THE TREE
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

    def _rev_list(self, rev=None, full_history=False):
        '''
        Generator for objects in rev. Returns (hash, type, size) tuple.
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

        for line in catfile.stdout:
            objhash, objtype, size = line.split()
            yield objhash, objtype, size

        catfile.wait()

    def _find_paths(self, hashes, rev=None, full_history=False):
        '''
        Takes a list of git object hashes and generates hash,path tuples
        '''
        rev = rev or 'HEAD'
        # full_history implies --all
        args = ['--all'] if full_history else ['--no-walk', rev]

        revlist = git('rev-list --objects'.split() + args, stdout=sub.PIPE)
        for line in revlist.stdout:
            hashobj = line.strip()
            # Revlist prints all objects (commits, trees, blobs) but blobs have the file path
            # next to the git objecthash
            # Handle files with spaces
            hashobj, _, filename = hashobj.partition(' ')
            if filename:
                # If the object is one we're managing
                if hashobj in hashes:
                    yield hashobj, filename

        revlist.wait()

    def _managed_files(self, rev=None, full_history=False):
        '''
        Finds managed files in the specified revision
        '''
        revlistgen = self._rev_list(rev=rev, full_history=full_history)
        # Find any objects that are git-fat placeholders which are tracked in the repository
        managed = {}
        for objhash, objtype, size in revlistgen:
            # files are of blob type
            if objtype == 'blob' and int(size) == self._magiclen:
                # Read the actual file contents
                readfile = git(['cat-file', '-p', objhash], stdout=sub.PIPE)
                digest = self._get_digest(readfile.stdout)
                if digest:
                    managed[objhash] = digest

        # go through rev-list again to get the filenames
        # Again, I tried avoiding making another call to rev-list by caching the
        # filenames above, but was running into the memory buffer issue
        # Instead we just make another call to rev-list.  Takes more time, but still
        # only takes 5 seconds to traverse the entire history of a 22k commit repo
        filedict = dict(self._find_paths(managed.keys(), rev=rev, full_history=full_history))

        # return a dict(git-fat hash -> filename)
        # git's objhash are the keys in `managed` and `filedict`
        ret = dict((j, filedict[i]) for i, j in managed.iteritems())
        return ret

    def _orphan_files(self, patterns=[]):
        '''
        generator for placeholders in working tree that match pattern
        '''
        # Null-terminated for proper file name handling (spaces)
        for fname in sub.check_output(['git', 'ls-files', '-z'] + patterns).split('\x00')[:-1]:
            stat = os.lstat(fname)
            if stat.st_size != self._magiclen or os.path.islink(fname):
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
        blockiter, fatfile = self._decode(instream)
        if fatfile:
            block = next(blockiter)  # read the first block
            digest = block.split()[2]
            objfile = os.path.join(self.objdir, digest)
            try:
                with open(objfile) as f:
                    cat(f, outstream)
                self.verbose('git-fat filter-smudge: restoring from %s' % objfile)
            except IOError:
                self.verbose('git-fat filter-smudge: fat object not found in cache %s' % objfile)
                outstream.write(block)
        else:
            self.verbose('git-fat filter-smudge: not a managed file')
            cat_iter(blockiter, sys.stdout)

    def _filter_clean(self, instream, outstream):
        '''
        The clean filter runs when a file is added to the index. It gets the "smudged" (working copy)
        version of the file on stdin and produces the "clean" (repository) version on stdout.
        '''

        blockiter, is_placeholder = self._decode(instream)

        if is_placeholder:
            # This must be cat_iter, not cat because we already read from instream
            cat_iter(blockiter, outstream)
            return

        # make temporary file for writing
        fd, tmpname = tempfile.mkstemp(dir=self.objdir)
        tmpstream = os.fdopen(fd, 'w')

        # Hash the input, write to temp file
        digest, size = self._hash_stream(blockiter, tmpstream)
        tmpstream.close()

        objfile = os.path.join(self.objdir, digest)

        if os.path.exists(objfile):
            self.verbose('git-fat filter-clean: cached file already exists %s' % objfile)
            # Remove temp file
            os.remove(tmpname)
        else:
            # Set permissions for the new file using the current umask
            os.chmod(tmpname, int('444', 8) & ~umask())
            # Rename temp file
            os.rename(tmpname, objfile)
            self.verbose('git-fat filter-clean: caching to %s' % objfile)

        # Write placeholder to index
        outstream.write(self._encode(digest, size))

    def filter_clean(self, cur_file, **kwargs):
        '''
        Public command to do the clean (should only be called by git)
        '''
        if cur_file and not self.can_clean_file(cur_file):
            self.verbose(
                "Not adding: {0}\n".format(cur_file) +
                "It is not a new file and is not managed by git-fat"
            )
            # Git needs something, so we cat stdin to stdout
            cat(sys.stdin, sys.stdout)
        else:  # We clean the file
            if (cur_file):
                self.verbose("Adding {0}".format(cur_file))

            self._filter_clean(sys.stdin, sys.stdout)

    def filter_smudge(self, **kwargs):
        '''
        Public command to do the smudge (should only be called by git)
        '''
        self._filter_smudge(sys.stdin, sys.stdout)

    def find(self, size, **kwargs):
        '''
        Find any files over size threshold in the repository.
        '''
        revlistgen = self._rev_list(full_history=True)
        # Find any objects that are git-fat placeholders which are tracked in the repository
        objsizedict = {}
        for objhash, objtype, objsize in revlistgen:
            # files are of blob type
            if objtype == 'blob' and int(objsize) > size:
                objsizedict[objhash] = objsize
        for objhash, objpath in self._find_paths(objsizedict.keys(), full_history=True):
            print(objhash, objsizedict[objhash], objpath)

    def _parse_ls_files(self, line):
        mode, _, tail = line.partition(' ')
        blobhash, _, tail = tail.partition(' ')
        stageno, _, tail = tail.partition('\t')
        filename = tail.strip()
        return mode, blobhash, stageno, filename

    def index_filter(self, filelist, add_gitattributes=True, **kwargs):

        workdir = os.path.join(self.gitdir, 'fat', 'index-filter')
        mkdir_p(workdir)

        with open(filelist) as f:
            files_to_exclude = f.read().splitlines()

        ls_files = git('ls-files -s'.split(), stdout=sub.PIPE)
        update_index = git('update-index --index-info'.split(), stdin=sub.PIPE)
        lsfmt = '{0} {1} {2}\t{3}\n'

        newfiles = []
        for line in ls_files.stdout:
            mode, blobhash, stageno, filename = self._parse_ls_files(line)

            if filename not in files_to_exclude or mode == "120000":
                continue
            # Save file to update .gitattributes
            newfiles.append(filename)
            cleanedobj_hash = os.path.join(workdir, blobhash)
            # if it hasn't already been cleaned
            if not os.path.exists(cleanedobj_hash):
                catfile = git('cat-file blob {0}'.format(blobhash).split(), stdout=sub.PIPE)
                hashobj = git('hash-object -w --stdin'.split(), stdin=sub.PIPE, stdout=sub.PIPE)
                self._filter_clean(catfile.stdout, hashobj.stdin)
                hashobj.stdin.close()
                objhash = hashobj.stdout.read().strip()
                catfile.wait()
                hashobj.wait()
                with open(cleanedobj_hash, 'w') as f:
                    f.write(objhash + '\n')
            else:
                with open(cleanedobj_hash) as f:
                    objhash = f.read().strip()
            # Write the placeholder to the index
            update_index.stdin.write(lsfmt.format(mode, objhash, stageno, filename))

        if add_gitattributes:
            ls_ga = git('ls-files -s .gitattributes'.split(), stdout=sub.PIPE)
            lsout = ls_ga.stdout.read().strip()
            ls_ga.wait()
            if lsout:  # Always try to get the old gitattributes
                ga_mode, ga_hash, ga_stno, ga_filename = self._parse_ls_files(lsout)
                ga_cat = git('cat-file blob {0}'.format(ga_hash).split(), stdout=sub.PIPE)
                old_ga = ga_cat.stdout.read().splitlines()
                ga_cat.wait()
            else:
                ga_mode, ga_stno, old_ga = '100644', '0', []
            ga_hashobj = git('hash-object -w --stdin'.split(), stdin=sub.PIPE,
                stdout=sub.PIPE)
            new_ga = old_ga + ['{0} filter=fat -text'.format(f) for f in newfiles]
            stdout, stderr = ga_hashobj.communicate('\n'.join(new_ga) + '\n')
            update_index.stdin.write(lsfmt.format(ga_mode, stdout.strip(),
                ga_stno, '.gitattributes'))

        ls_files.wait()
        update_index.stdin.close()
        update_index.wait()

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
                with open(fname, 'r') as f:
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
        showfile = git(['show', 'HEAD:{0}'.format(filename)], stdout=sub.PIPE, stderr=sub.PIPE)

        blockiter, is_fatfile = self._decode(showfile.stdout)

        # Flush the buffers to prevent deadlock from wait()
        # Caused when stdout from showfile is a large binary file and can't be fully buffered
        # I haven't figured out a way to avoid this unfortunately
        for blk in blockiter:
            continue

        if showfile.wait() or is_fatfile:
            # The file didn't exist in the repository
            # The file was a fatfile (which may have changed)
            return True

        # File exists but is not a fatfile, don't add it
        return False

    def pull(self, pattern=None, **kwargs):
        '''
        Pull anything that I have referenced, but not stored
        '''
        cached_objs = self._cached_objects()
        if pattern:
            # filter the working tree by a pattern
            files = set(digest for digest, fname in self._orphan_files(patterns=[pattern])) - cached_objs
        else:
            # default pull any object referenced but not stored
            files = self._referenced_objects(**kwargs) - cached_objs

        if files:
            print("Pulling: ", list(files))
            rsync = self._rsync(push=False)
            self.verbose('Executing: {0}'.format(rsync))
            p = sub.Popen(rsync, stdin=sub.PIPE, preexec_fn=os.setsid)
            p.communicate(input='\x00'.join(files))
        else:
            print("You've got everything! d(^_^)b")

        self.checkout()

    def push(self, **kwargs):
        '''
        Push anything that I have stored and referenced (rsync doesn't push if exists on remote)
        '''
        files = self._referenced_objects(**kwargs) & self._cached_objects()
        rsync = self._rsync(push=True)
        self.verbose('Executing: {0}'.format(rsync))
        p = sub.Popen(rsync, stdin=sub.PIPE)
        p.communicate(input='\x00'.join(files))

    def _status(self, **kwargs):
        '''
        Helper function that returns the oprhans and stale files
        '''
        catalog = self._cached_objects()
        referenced = self._referenced_objects(**kwargs)
        stale = catalog - referenced
        orphans = referenced - catalog
        return stale, orphans

    def status(self, **kwargs):
        '''
        Show orphan (in tree, but not in cache) and stale (in cache, but not in tree) objects, if any.
        '''
        stale, orphans = self._status(**kwargs)
        if orphans:
            print('Orphan objects:')
            for orph in orphans:
                print('\t' + orph)
        if stale:
            print('Stale objects:')
            for g in stale:
                print('\t' + g)

    def http_pull(self, **kwargs):
        '''
        Alternative to rsync (for anon clones)
        '''
        ret_code = 0

        _, orphans = self._status(**kwargs)
        baseurl = self._http_opts()
        for o in orphans:
            stream = http_get(baseurl, o)
            blockiter = readblocks(stream)

            # HTTP Error
            if blockiter is None:
                ret_code = 1
                continue

            fd, tmpname = tempfile.mkstemp(dir=self.objdir)
            tmpstream = os.fdopen(fd, 'w')

            # Hash the input, write to temp file
            digest, size = self._hash_stream(blockiter, tmpstream)
            tmpstream.close()

            if digest != o:
                # Should I retry?
                error('ERROR: Downloaded digest ({0}) did not match stored digest for orphan: {1}'.format(digest, o))
                os.remove(tmpname)
                ret_code = 1
                continue

            objfile = os.path.join(self.objdir, digest)
            os.chmod(tmpname, int('444', 8) & ~umask())
            # Rename temp file
            os.rename(tmpname, objfile)

        self.checkout()
        sys.exit(ret_code)

    def http_push(self):
        ''' NOT IMPLEMENTED '''
        pass


def main():

    import argparse

    if sys.argv[1] in [ c + 'version' for c in '','-','--']:
        print(__version__)
        sys.exit(0)

    fat = GitFat()

    parser = argparse.ArgumentParser(usage=("%(prog)s [global options] command [command options]\n"
        "       %(prog)s -h for full usage."))  # Six spaces for len('usage: ')
    subparser = parser.add_subparsers()

    parser.add_argument('-a', "--full-history", dest='full_history', action='store_true',
        help='Look for git-fat placeholder files in the entire history instead of just the working copy')
    parser.add_argument('-v', "--verbose", dest='verbose', action='store_true',
        help='Verbose output')

    # Empty function for legacy api; config gets called every time
    # (assuming if user is calling git-fat they want it configured)
    parser_init = subparser.add_parser('init',
        help='Initialize git-fat')
    parser_init.set_defaults(func=empty)

    parser_filter_clean = subparser.add_parser('filter-clean',
        help='filter-clean to be called only by git')
    parser_filter_clean.add_argument("cur_file", nargs="?")
    parser_filter_clean.set_defaults(func=fat.filter_clean)

    parser_filter_smudge = subparser.add_parser('filter-smudge',
        help='filter-smudge to be called only by git')
    parser_filter_smudge.add_argument("cur_file", nargs="?")  # Currently unused
    parser_filter_smudge.set_defaults(func=fat.filter_smudge)

    parser_push = subparser.add_parser('push',
        help='push cache to remote git-fat server')
    parser_push.set_defaults(func=fat.push)

    parser_pull = subparser.add_parser('pull',
        help='pull fatfiles from remote git-fat server')
    parser_pull.add_argument("pattern", nargs="?",
        help='pull only files matching pattern')
    parser_pull.set_defaults(func=fat.pull)

    parser_checkout = subparser.add_parser('checkout',
        help='resmudge all orphan objects')
    parser_checkout.set_defaults(func=fat.checkout)

    parser_find = subparser.add_parser('find',
        help='find all objects over [size]')
    parser_find.add_argument("size", type=int,
        help='threshold size in bytes')
    parser_find.set_defaults(func=fat.find)

    parser_status = subparser.add_parser('status',
        help='print orphan and stale objects')
    parser_status.set_defaults(func=fat.status)

    parser_list = subparser.add_parser('list',
        help='list all files managed by git-fat')
    parser_list.set_defaults(func=fat.list_files)

    parser_list = subparser.add_parser('pull-http',
        help='anonymously download git-fat files over http')
    parser_list.set_defaults(func=fat.http_pull)

    parser_index_filter = subparser.add_parser('index-filter',
        help='git fat index-filter for filter-branch')
    parser_index_filter.add_argument('filelist',
        help='file containing all files to import to git-fat')
    parser_index_filter.add_argument('-x', dest='add_gitattributes',
        help='prevent adding excluded to .gitattributes', action='store_false')
    parser_index_filter.set_defaults(func=fat.index_filter)

    args = parser.parse_args()

    kwargs = dict(vars(args))
    del kwargs['func']

    # First configure git-fat
    fat.configure(**kwargs)

    # don't need this after configuring, breaks functions because of kwargs
    del kwargs['verbose']
    # Then execute function
    try:
        args.func(**kwargs)
    except:
        if kwargs.get('cur_file'):
            fat.verbose("ERROR: processing file: " + kwargs.get('cur_file'))
        raise


if __name__ == '__main__':
    main()

__all__ = ['__version__', 'main', 'GitFat']
