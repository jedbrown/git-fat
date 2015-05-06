#!/usr/bin/env python
# -*- mode:python -*-

from __future__ import print_function, with_statement

import hashlib
import os
import subprocess as sub
import sys
import tempfile
import warnings
import ConfigParser as cfgparser
import logging as _logging  # Use logger.error(), not logging.error()
import shutil
import argparse
import platform
import stat

_logging.basicConfig(format='%(levelname)s:%(filename)s: %(message)s')
logger = _logging.getLogger(__name__)

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
        output, _ = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            err = sub.CalledProcessError(retcode, cmd)
            err.output = output
            raise err
        return output

    sub.check_output = backport_check_output

__version__ = '0.5.0'

BLOCK_SIZE = 4096

NOT_IMPLEMENTED_MESSAGE = "This method isn't implemented for this backend!"


def get_log_level(log_level_string):
    log_level_string = log_level_string.lower()
    if not log_level_string:
        return _logging.WARNING
    levels = {'debug': _logging.DEBUG,
              'info': _logging.INFO,
              'warning': _logging.WARNING,
              'error': _logging.ERROR,
              'critical': _logging.CRITICAL}
    if log_level_string in levels:
        return levels[log_level_string]
    else:
        logger.warning("Invalid log level: {}".format(log_level_string))
    return _logging.WARNING


GIT_FAT_LOG_LEVEL = get_log_level(os.getenv("GIT_FAT_LOG_LEVEL", ""))
GIT_FAT_LOG_FILE = os.getenv("GIT_FAT_LOG_FILE", "")
GIT_SSH = os.getenv("GIT_SSH")


def git(cliargs, *args, **kwargs):
    ''' Calls git commands with Popen arguments '''
    if GIT_FAT_LOG_FILE and "--failfast" in sys.argv:
        # Flush any prior logger warning/error/critical to the log file
        # which is being checked by unit tests.
        sys.stdout.flush()
        sys.stderr.flush()
    if GIT_FAT_LOG_LEVEL == _logging.DEBUG:
        logger.debug('{}'.format(' '.join(['git'] + cliargs))
                     + ' ({}, {})'.format(args, kwargs))
    return sub.Popen(['git'] + cliargs, *args, **kwargs)


def check_output2(args):
    if GIT_FAT_LOG_FILE and "--failfast" in sys.argv:
        # Flush any prior logger warning/error/critical to the log file
        # which is being checked by unit tests.
        sys.stdout.flush()
        sys.stderr.flush()
    if GIT_FAT_LOG_LEVEL == _logging.DEBUG:
        args2 = args
        for i, v in enumerate(args):
            args[i] = v.replace("\x00", r"\x00")
        logger.debug('{}'.format(' '.join(args2)))
    return original_check_output(args)


original_check_output = sub.check_output
sub.check_output = check_output2


def mkdir_p(path):
    import errno
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


# -----------------------------------------------------------------------------
# On Windows files may be read only and may require changing
# permissions. Always use these functions for moving/deleting files.

def move_file(src, dst):
    if platform.system() == "Windows":
        if os.path.exists(src) and not os.access(src, os.W_OK):
            st = os.stat(src)
            os.chmod(src, st.st_mode | stat.S_IWUSR)
        if os.path.exists(dst) and not os.access(dst, os.W_OK):
            st = os.stat(dst)
            os.chmod(dst, st.st_mode | stat.S_IWUSR)
    shutil.move(src, dst)


def delete_file(f):
    if platform.system() == "Windows":
        if os.path.exists(f) and not os.access(f, os.W_OK):
            st = os.stat(f)
            os.chmod(f, st.st_mode | stat.S_IWUSR)
    os.remove(f)

# -----------------------------------------------------------------------------


def make_sys_streams_binary():
    # Information for future: in Python 3 use sys.stdin.detach()
    # for both Linux and Windows.
    if platform.system() == "Windows":
        import msvcrt  # pylint: disable=import-error
        result = msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        if result == -1:
            raise Exception("Setting sys.stdin to binary mode failed")
        result = msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        if result == -1:
            raise Exception("Setting sys.stdout to binary mode failed")


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


def gitconfig_get(name, cfgfile=None):
    args = ['config', '--get']
    if cfgfile is not None:
        args += ['--file', cfgfile]
    args.append(name)
    p = git(args, stdout=sub.PIPE)
    output = p.communicate()[0].strip()
    if p.returncode != 0:
        return ''
    else:
        return output


def gitconfig_set(name, value, cfgfile=None):
    args = ['git', 'config']
    if cfgfile is not None:
        args += ['--file', cfgfile]
    args += [name, value]
    sub.check_call(args)


def _config_path(path=None):
    try:
        root = sub.check_output('git rev-parse --show-toplevel'.split()).strip()
    except sub.CalledProcessError:
        raise RuntimeError('git-fat must be run from a git directory')
    default_path = os.path.join(root, '.gitfat')
    path = path or default_path
    return path


def _obj_dir():
    try:
        gitdir = sub.check_output('git rev-parse --git-dir'.split()).strip()
    except sub.CalledProcessError:
        raise RuntimeError('git-fat must be run from a git directory')
    objdir = os.path.join(gitdir, 'fat', 'objects')
    return objdir


def http_get(baseurl, filename):
    ''' Returns file descriptor for http file stream, catches urllib2 errors '''
    import urllib2
    try:
        print("Downloading: {0}".format(filename))
        geturl = '/'.join([baseurl, filename])
        res = urllib2.urlopen(geturl)
        return res.fp
    except urllib2.URLError as e:
        logger.warning(e.reason + ': {0}'.format(geturl))
        return None


def hash_stream(blockiter, outstream):
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


class BackendInterface(object):
    """ __init__ and pull_files are required, push_files is optional """

    def __init__(self, base_dir, **kwargs):
        """ Configuration options should be set in here """
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    def push_files(self, file_list):
        """ Return True if push was successful, False otherwise. Not required but useful """
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)

    def pull_files(self, file_list):
        """ Return True if pull was successful, False otherwise """
        raise NotImplementedError(NOT_IMPLEMENTED_MESSAGE)


class CopyBackend(BackendInterface):
    def __init__(self, base_dir, **kwargs):
        other_path = kwargs.get('remote')
        if not os.path.isdir(other_path):
            raise RuntimeError('copybackend target path is not directory: {}'.format(other_path))
        logger.debug("CopyBackend: other_path={}, base_dir={}"
                     .format(other_path, base_dir))
        self.other_path = other_path
        self.base_dir = base_dir

    def pull_files(self, file_list):
        for f in file_list:
            fullpath = os.path.join(self.other_path, f)
            shutil.copy2(fullpath, self.base_dir)
        return True

    def push_files(self, file_list):
        for f in file_list:
            fullpath = os.path.join(self.base_dir, f)
            shutil.copy2(fullpath, self.other_path)
        return True


class HTTPBackend(BackendInterface):
    """ Pull files from an HTTP server """

    def __init__(self, base_dir, **kwargs):
        remote_url = kwargs.get('remote')
        if not remote_url:
            raise RuntimeError('No remote url configured for http backend')

        if not remote_url.startswith('http') or remote_url.startswith('https'):
            raise RuntimeError('http remote url must start with http:// or https://')

        self.remote_url = remote_url
        self.base_dir = base_dir

    def pull_files(self, file_list):
        is_success = True

        for o in file_list:
            stream = http_get(self.remote_url, o)
            blockiter = readblocks(stream)

            # HTTP Error
            if blockiter is None:
                is_success = False
                continue

            fd, tmpname = tempfile.mkstemp(dir=self.base_dir)
            with os.fdopen(fd, 'wb') as tmpstream:
                # Hash the input, write to temp file
                digest, _ = hash_stream(blockiter, tmpstream)

            if digest != o:
                # Should I retry?
                logger.error('Downloaded digest ({0}) did not match stored digest for orphan: {1}'.format(digest, o))
                delete_file(tmpname)
                is_success = False
                continue

            objfile = os.path.join(self.base_dir, digest)
            os.chmod(tmpname, int('444', 8) & ~umask())
            # Rename temp file.
            move_file(tmpname, objfile)

        return is_success


class RSyncBackend(BackendInterface):
    """ Push and pull files from rsync remote """

    def __init__(self, base_dir, **kwargs):
        remote_url = kwargs.get('remote')

        # Allow support for rsyncd servers (Looks like "remote = example.org::mybins")
        ssh_user = ''
        ssh_port = ''
        if "::" in remote_url:
            self.is_rsyncd_remote = True
        else:
            self.is_rsyncd_remote = False
            ssh_user = kwargs.get('sshuser')
            ssh_port = kwargs.get('sshport', '22')

        if not remote_url:
            raise RuntimeError("No remote url configured for rsync")

        self.remote_url = remote_url
        self.ssh_user = ssh_user
        self.ssh_port = ssh_port
        self.base_dir = base_dir
        # Swap Windows style drive letters (e.g. 't:') for cygwin style drive letters (e.g. '/t')
        # Otherwise, when using an rsyncd remote (e.g. 'example.org::bin'),
        # The rsync client on Windows will exit with this error:
        # "The source and destination cannot both be remote."
        # Presumably, this is because rsync assumes any path is remote if it contains a colon.
        if platform.system() == 'Windows' and self.is_rsyncd_remote and self.base_dir.find(':') == 1:
            self.base_dir = "/" + self.base_dir[0] + self.base_dir[2:]

    def _rsync(self, push):
        ''' Construct the rsync command '''
        if platform.system() == 'Windows':
            # Windows installer ships its own rsync tool
            rsync_tool = 'git-fat_rsync.exe'
        else:
            rsync_tool = 'rsync'
        cmd_tmpl = [rsync_tool] + ' --protect-args --progress'\
            ' --ignore-existing --from0 --files-from=-'.split()

        if push:
            src, dst = self.base_dir, self.remote_url
        else:
            src, dst = self.remote_url, self.base_dir
        cmd = cmd_tmpl + [src + '/', dst + '/']

        # extra must be passed in as single argv, which is why it's
        # not in the template and split isn't called on it
        if self.is_rsyncd_remote:
            extra = ''
        elif GIT_SSH:
            extra = '--rsh={}'.format(GIT_SSH)
        elif platform.system() == "Windows":
            extra = '--rsh=git-fat_ssh.exe'
        else:
            extra = '--rsh=ssh'

        if self.ssh_user:
            extra = ' '.join([extra, '-l {}'.format(self.ssh_user)])
        if self.ssh_port:
            extra = ' '.join([extra, '-p {}'.format(self.ssh_port)])

        if extra:
            cmd.append(extra)

        return cmd

    def pull_files(self, file_list):
        rsync = self._rsync(push=False)
        logger.debug("rsync pull command: {}".format(" ".join(rsync)))
        try:
            p = sub.Popen(rsync, stdin=sub.PIPE)
        except OSError:
            # re-raise with a more useful message
            raise OSError('Error running "%s"' % " ".join(rsync))

        p.communicate(input='\x00'.join(file_list))
        # TODO: fix for success check
        return True

    def push_files(self, file_list):
        rsync = self._rsync(push=True)
        logger.debug("rsync push command: {}".format(" ".join(rsync)))
        p = sub.Popen(rsync, stdin=sub.PIPE)
        p.communicate(input='\x00'.join(file_list))
        # TODO: fix for success check
        return True


BACKEND_MAP = {
    'rsync': RSyncBackend,
    'http': HTTPBackend,
    'copy': CopyBackend,
}


class GitFat(object):

    def __init__(self, backend, full_history=False):

        # The backend instance we use to get the files
        self.backend = backend
        self.full_history = full_history
        self.rev = None  # Unused
        self.objdir = _obj_dir()
        self._cookie = '#$# git-fat '
        self._format = self._cookie + '{digest} {size:20d}\n'

        # Legacy format support below, need to actually check the version once/if we have more than 2
        if os.environ.get('GIT_FAT_VERSION'):
            self._format = self._cookie + '{digest}\n'

        # considers the git-fat version when generating the magic length
        _ml = lambda fn: len(fn(hashlib.sha1('dummy').hexdigest(), 5))
        self._magiclen = _ml(self._encode)

        self.configure()

    def configure(self):
        '''
        Configure git-fat for usage: variables, environment
        '''
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
            if len(block) != self._magiclen:  # Sanity check
                warnings.warn('Found file with cookie but without magiclen')
                return ret, False
            return ret, True
        return ret, False

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

    def _rev_list(self):
        '''
        Generator for objects in rev. Returns (hash, type, size) tuple.
        '''

        rev = self.rev or 'HEAD'
        # full_history implies --all
        args = ['--all'] if self.full_history else ['--no-walk', rev]

        # Get all the git objects in the current revision and in history if --all is specified
        revlist = git('rev-list --objects'.split() + args, stdout=sub.PIPE)
        # Grab only the first column.  Tried doing this in python but because of the way that
        # subprocess.PIPE buffering works, I was running into memory issues with larger repositories
        # plugging pipes to other subprocesses appears to not have the memory buffer issue
        if platform.system() == "Windows":
            # Windows installer ships its own awk tool
            awk_tool = 'git-fat_gawk.exe'
        else:
            awk_tool = 'awk'
        awk = sub.Popen([awk_tool, '{print $1}'], stdin=revlist.stdout, stdout=sub.PIPE)
        # Read the objects and print <sha> <type> <size>
        catfile = git('cat-file --batch-check'.split(), stdin=awk.stdout, stdout=sub.PIPE)

        for line in catfile.stdout:
            objhash, objtype, size = line.split()
            yield objhash, objtype, size

        catfile.wait()

    def _find_paths(self, hashes):
        '''
        Takes a list of git object hashes and generates hash,path tuples
        '''
        rev = self.rev or 'HEAD'
        # full_history implies --all
        args = ['--all'] if self.full_history else ['--no-walk', rev]

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

    def _managed_files(self, **unused_kwargs):
        revlistgen = self._rev_list()
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
        filedict = dict(self._find_paths(managed.keys()))

        # return a dict(git-fat hash -> filename)
        # git's objhash are the keys in `managed` and `filedict`
        ret = dict((j, filedict[i]) for i, j in managed.iteritems())
        return ret

    def _orphan_files(self, patterns=None):
        '''
        generator for placeholders in working tree that match pattern
        '''
        patterns = patterns or []
        # Null-terminated for proper file name handling (spaces)
        for fname in sub.check_output(['git', 'ls-files', '-z'] + patterns).split('\x00')[:-1]:
            if not os.path.exists(fname):
                continue
            st = os.lstat(fname)
            if st.st_size != self._magiclen or os.path.islink(fname):
                continue
            with open(fname, "rb") as f:
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
                with open(objfile, "rb") as f:
                    cat(f, outstream)
                logger.info('git-fat filter-smudge: restoring from {}'.format(objfile))
            except IOError:
                logger.info('git-fat filter-smudge: fat object not found in cache {}'.format(objfile))
                outstream.write(block)
        else:
            logger.info('git-fat filter-smudge: not a managed file')
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
        tmpstream = os.fdopen(fd, 'wb')

        # Hash the input, write to temp file
        digest, size = hash_stream(blockiter, tmpstream)
        tmpstream.close()

        objfile = os.path.join(self.objdir, digest)

        if os.path.exists(objfile):
            logger.info('git-fat filter-clean: cached file already exists {}'.format(objfile))
            # Remove temp file
            delete_file(tmpname)
        else:
            # Set permissions for the new file using the current umask
            os.chmod(tmpname, int('444', 8) & ~umask())
            # Rename temp file
            move_file(tmpname, objfile)
            logger.info('git-fat filter-clean: caching to {}'.format(objfile))

        # Write placeholder to index
        outstream.write(self._encode(digest, size))

    def filter_clean(self, cur_file, **unused_kwargs):
        '''
        Public command to do the clean (should only be called by git)
        '''
        logger.debug("CLEAN: cur_file={}, unused_kwargs={}"
                     .format(cur_file, unused_kwargs))
        if cur_file and not self.can_clean_file(cur_file):
            logger.info(
                "Not adding: {0}. ".format(cur_file) +
                "It is not a new file and is not managed by git-fat"
            )
            # Git needs something, so we cat stdin to stdout
            cat(sys.stdin, sys.stdout)
        else:  # We clean the file
            if cur_file:
                logger.info("Adding {0}".format(cur_file))
            self._filter_clean(sys.stdin, sys.stdout)

    def filter_smudge(self, **unused_kwargs):
        '''
        Public command to do the smudge (should only be called by git)
        '''
        logger.debug("SMUDGE: unused_kwargs={}".format(unused_kwargs))
        self._filter_smudge(sys.stdin, sys.stdout)

    def find(self, size, **unused_kwargs):
        '''
        Find any files over size threshold in the repository.
        '''
        revlistgen = self._rev_list()
        # Find any objects that are git-fat placeholders which are tracked in the repository
        objsizedict = {}
        for objhash, objtype, objsize in revlistgen:
            # files are of blob type
            if objtype == 'blob' and int(objsize) > size:
                objsizedict[objhash] = objsize
        for objhash, objpath in self._find_paths(objsizedict.keys()):
            print(objhash, objsizedict[objhash], objpath)

    def _parse_ls_files(self, line):
        mode, _, tail = line.partition(' ')
        blobhash, _, tail = tail.partition(' ')
        stageno, _, tail = tail.partition('\t')
        filename = tail.strip()
        return mode, blobhash, stageno, filename

    def _get_old_gitattributes(self):
        """ Get the last .gitattributes file in HEAD, and return it """
        ls_ga = git('ls-files -s .gitattributes'.split(), stdout=sub.PIPE)
        lsout = ls_ga.stdout.read().strip()
        ls_ga.wait()
        if lsout:  # Always try to get the old gitattributes
            ga_mode, ga_hash, ga_stno, _ = self._parse_ls_files(lsout)
            ga_cat = git('cat-file blob {0}'.format(ga_hash).split(), stdout=sub.PIPE)
            old_ga = ga_cat.stdout.read().splitlines()
            ga_cat.wait()
        else:
            ga_mode, ga_stno, old_ga = '100644', '0', []
        return old_ga, ga_mode, ga_stno

    def _update_index(self, uip, mode, content, stageno, filename):
        fmt = '{0} {1} {2}\t{3}\n'
        uip.stdin.write(fmt.format(mode, content, stageno, filename))

    def _add_gitattributes(self, newfiles, unused_update_index):
        """ Find the previous gitattributes file, and append to it """

        old_ga, ga_mode, ga_stno = self._get_old_gitattributes()
        ga_hashobj = git('hash-object -w --stdin'.split(), stdin=sub.PIPE,
                         stdout=sub.PIPE)
        # Add lines to the .gitattributes file
        new_ga = old_ga + ['{0} filter=fat -text'.format(f) for f in newfiles]
        stdout, _ = ga_hashobj.communicate('\n'.join(new_ga) + '\n')
        return ga_mode, stdout.strip(), ga_stno, '.gitattributes'

    def _process_index_filter_line(self, line, workdir, excludes):

        mode, blobhash, stageno, filename = self._parse_ls_files(line)

        if filename not in excludes or mode == "120000":
            return None
        # Save file to update .gitattributes
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
            with open(cleanedobj_hash, 'wb') as cleaned:
                cleaned.write(objhash + '\n')
        else:
            with open(cleanedobj_hash, 'rb') as cleaned:
                objhash = cleaned.read().strip()
        return mode, objhash, stageno, filename

    def index_filter(self, filelist, add_gitattributes=True, **unused_kwargs):
        gitdir = sub.check_output('git rev-parse --git-dir'.split()).strip()
        workdir = os.path.join(gitdir, 'fat', 'index-filter')
        mkdir_p(workdir)

        with open(filelist, 'rb') as excludes:
            files_to_exclude = excludes.read().splitlines()

        ls_files = git('ls-files -s'.split(), stdout=sub.PIPE)
        uip = git('update-index --index-info'.split(), stdin=sub.PIPE)

        newfiles = []
        for line in ls_files.stdout:
            newfile = self._process_index_filter_line(line, workdir, files_to_exclude)
            if newfile:
                self._update_index(uip, *newfile)
                # The filename is in the last position
                newfiles.append(newfile[-1])

        if add_gitattributes:
            # Add the files to the gitattributes file and update the index
            attrs = self._add_gitattributes(newfiles, add_gitattributes)
            self._update_index(uip, *attrs)

        ls_files.wait()
        uip.stdin.close()
        uip.wait()

    def list_files(self, **kwargs):
        '''
        Command to list the files by fat-digest -> gitroot relative path
        '''
        managed = self._managed_files(**kwargs)
        for f in managed.keys():
            print(f, managed.get(f))

    def _remove_orphan_file(self, fname):
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
        with open(fname, 'rb') as f:
            recheck_digest = self._get_digest(f)  # One last sanity check
        if recheck_digest:
            delete_file(fname)

    def checkout(self, show_orphans=False, **unused_kwargs):
        '''
        Update any stale files in the present working tree
        '''
        to_checkout = []
        for digest, fname in self._orphan_files():
            objpath = os.path.join(self.objdir, digest)
            if os.access(objpath, os.R_OK):
                print('Restoring %s -> %s' % (digest, fname))
                self._remove_orphan_file(fname)
                # This re-smudge is essentially a copy that restores permissions.
                to_checkout.append(fname)
            elif show_orphans:
                print('Data unavailable: %s %s' % (digest, fname))
        sub.check_call(['git', 'checkout-index', '--index', '--force'] + to_checkout)

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
        for _ in blockiter:
            continue

        if showfile.wait() or is_fatfile:
            # The file didn't exist in the repository
            # The file was a fatfile (which may have changed)
            return True

        # File exists but is not a fatfile, don't add it
        return False

    def pull(self, patterns=None, **kwargs):
        """ Get orphans, call backend pull """
        cached_objs = self._cached_objects()

        # TODO: Why use _orphan _and_ _referenced here?
        if patterns:
            # filter the working tree by a pattern
            files = set(digest for digest, fname in self._orphan_files(patterns=patterns)) - cached_objs
        else:
            # default pull any object referenced but not stored
            files = self._referenced_objects(**kwargs) - cached_objs

        logger.debug("PULL: patterns={}, kwargs={}, len(files)={}"
                     .format(patterns, kwargs, len(files)))

        if not self.backend.pull_files(files):
            sys.exit(1)
        self.checkout()

    def push(self, unused_pattern=None, **kwargs):
        # We only want the intersection of the referenced files and ones we have cached
        # Prevents file doesn't exist errors, while saving on bw by default (_referenced only
        # checks HEAD for files)
        files = self._referenced_objects(**kwargs) & self._cached_objects()
        logger.debug("PUSH: unused_pattern={}, kwargs={}, len(files)={}"
                     .format(unused_pattern, kwargs, len(files)))
        if not self.backend.push_files(files):
            sys.exit(1)

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


def _get_options(config, backend, cfg_file_path):
    """ returns the options for a backend in dictionary form """
    try:
        opts = dict(config.items(backend))
    except cfgparser.NoSectionError:
        err = "No section found in {} for backend {}".format(cfg_file_path, backend)
        raise RuntimeError(err)
    return opts


def _read_config(cfg_file_path=None):
    config = cfgparser.SafeConfigParser()
    if not os.path.exists(cfg_file_path):
        # Can't continue, but this isn't unusual
        logger.warning("This does not appear to be a repository managed by git-fat. "
                       "Missing configfile at: {}".format(cfg_file_path))
        sys.exit(0)
    try:
        config.read(cfg_file_path)
    except cfgparser.Error:  # TODO: figure out what to catch here
        raise RuntimeError("Error reading or parsing configfile: {}".format(cfg_file_path))
    return config


def _parse_config(backend=None, cfg_file_path=None):
    """ Parse the given config file and return the backend instance """
    cfg_file_path = _config_path(path=cfg_file_path)
    config = _read_config(cfg_file_path)
    if backend is None:
        try:
            backends = config.sections()
        except cfgparser.Error:
            raise RuntimeError("Error reading or parsing configfile: {}".format(cfg_file_path))
        if not backends:  # e.g. empty file
            raise RuntimeError("No backends configured in config: {}".format(cfg_file_path))
        backend = backends[0]

    opts = _get_options(config, backend, cfg_file_path)
    base_dir = _obj_dir()

    try:
        Backend = BACKEND_MAP[backend]
    except IndexError:
        raise RuntimeError("Unknown backend specified: {}".format(backend))
    return Backend(base_dir, **opts)


def run(backend, **kwargs):
    make_sys_streams_binary()
    name = kwargs.pop('func')
    full_history = kwargs.pop('full_history')
    gitfat = GitFat(backend, full_history=full_history)
    fn = name.replace("-", "_")
    if not hasattr(gitfat, fn):
        raise Exception("Unknown function called")
    getattr(gitfat, fn)(**kwargs)


def _configure_logging(log_level):
    if GIT_FAT_LOG_LEVEL:
        log_level = GIT_FAT_LOG_LEVEL
    if GIT_FAT_LOG_FILE:
        file_handler = _logging.FileHandler(GIT_FAT_LOG_FILE)
        file_handler.setLevel(log_level)
        formatter = _logging.Formatter(
            '%(levelname)s:%(filename)s:%(funcName)s:%(lineno)d: %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    logger.setLevel(log_level)


def _load_backend(kwargs):
    needs_backend = ('pull', 'push')
    backend_opt = kwargs.pop('backend', None)
    config_file = kwargs.pop('config_file', None)
    backend = None
    if kwargs['func'] == 'pull':
        # since pull can be of the form pull [backend] [patterns], we need to check
        # the first argument and insert into file patterns if it's not a backend
        # this means you can't use a file pattern which is an exact match with
        # a backend name (e.g. you can't have a file named copy, rsync, http, etc)
        if backend_opt and backend_opt not in BACKEND_MAP:
            kwargs['patterns'].insert(0, backend_opt)
            backend_opt = None
    if kwargs['func'] in needs_backend:
        backend = _parse_config(backend=backend_opt, cfg_file_path=config_file)
    return backend


def main():

    parser = argparse.ArgumentParser(
        argument_default=argparse.SUPPRESS,
        description='A tool for managing large binary files in git repositories.')
    subparser = parser.add_subparsers()

    # Global options
    parser.add_argument(
        '-a', "--full-history", dest='full_history', action='store_true', default=False,
        help='Look for git-fat placeholder files in the entire history instead of just the working copy')
    parser.add_argument(
        '-v', "--verbose", dest='verbose', action='store_true',
        help='Get verbose output about what git-fat is doing')
    parser.add_argument(
        '-d', "--debug", dest='debug', action='store_true',
        help='Get debugging output about what git-fat is doing')
    parser.add_argument(
        '-c', "--config", dest='config_file', type=str,
        help='Specify which config file to use (defaults to .gitfat)')

    # redundant function for legacy api; config gets called every time.
    # (assuming if user is calling git-fat they want it configured)
    # plus people like running init when setting things up d(^_^)b
    sp = subparser.add_parser('init', help='Initialize git-fat')
    sp.set_defaults(func="configure")

    sp = subparser.add_parser('filter-clean', help="Internal function used by git")
    sp.add_argument("cur_file", nargs="?")
    sp.set_defaults(func='filter_clean')

    sp = subparser.add_parser('filter-smudge', help="Internal function used by git")
    sp.add_argument("cur_file", nargs="?")
    sp.set_defaults(func='filter_smudge')

    sp = subparser.add_parser('push', help='push cache to remote git-fat server')
    sp.add_argument("backend", nargs="?", help='pull using given backend')
    sp.set_defaults(func='push')

    sp = subparser.add_parser('pull', help='pull fatfiles from remote git-fat server')
    sp.add_argument("backend", nargs="?", help='pull using given backend')
    sp.add_argument("patterns", nargs="*", help='files or file patterns to pull')
    sp.set_defaults(func='pull')

    sp = subparser.add_parser('checkout', help='resmudge all orphan objects')
    sp.set_defaults(func='checkout')

    sp = subparser.add_parser('find', help='find all objects over [size]')
    sp.add_argument("size", type=int, help='threshold size in bytes')
    sp.set_defaults(func='find')

    sp = subparser.add_parser('status', help='print orphan and stale objects')
    sp.set_defaults(func='status')

    sp = subparser.add_parser('list', help='list all files managed by git-fat')
    sp.set_defaults(func='list_files')

    # Legacy function to preserve backwards compatability
    sp = subparser.add_parser('pull-http', help="Deprecated, use `pull http` (no dash) instead")
    sp.set_defaults(func='pull', backend='http')

    sp = subparser.add_parser('index-filter', help='git fat index-filter for filter-branch')
    sp.add_argument('filelist', help='file containing all files to import to git-fat')
    sp.add_argument(
        '-x', dest='add_gitattributes',
        help='prevent adding excluded to .gitattributes', action='store_false')
    sp.set_defaults(func='index_filter')

    if len(sys.argv) > 1 and sys.argv[1] in [c + 'version' for c in '', '-', '--']:
        print(__version__)
        sys.exit(0)

    args = parser.parse_args()
    kwargs = dict(vars(args))

    if kwargs.pop('debug', None):
        log_level = _logging.DEBUG
    elif kwargs.pop('verbose', None):
        log_level = _logging.INFO
    else:
        log_level = _logging.WARNING
    _configure_logging(log_level)

    try:
        backend = _load_backend(kwargs)  # load_backend mutates kwargs
        run(backend, **kwargs)
    except RuntimeError as err:
        logger.error(str(err))
        sys.exit(1)
    except:
        if kwargs.get('cur_file'):
            logger.error("processing file: " + kwargs.get('cur_file'))
        raise


if __name__ == '__main__':
    main()

__all__ = ['__version__', 'main', 'GitFat']
