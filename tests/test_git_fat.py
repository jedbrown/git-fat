import os
import shutil
import subprocess as sub
import tempfile
import unittest
import logging


logging.basicConfig(format='%(levelname)s:%(filename)s:%(message)s')


def call(cmd, *args, **kwargs):

    if isinstance(cmd, str):
        cmd = cmd.split()

    logging.info('`{}`'.format(' '.join(cmd)))

    try:
        output = sub.check_output(cmd, *args, **kwargs)

    except sub.CalledProcessError as e:
        logging.error("cmd `{}` returned {}\n".format(e.cmd, e.returncode))
        logging.error("The output of the command was: \n")
        logging.error("{}\n".format(e.output))
    return output


def git(cliargs, *args, **kwargs):
    if isinstance(cliargs, str):
        cliargs = cliargs.split()
    cmd = ['git'] + cliargs
    return call(cmd)


def commit(message):
    git('add -A')
    git(['commit', '-m', message])


def read_index(filename):
    objhash = git(['hash-object', filename])
    contents = git('cat-file -p {}'.format(objhash))
    return contents


class Base(unittest.TestCase):

    def setUp(self):
        """ Get me into an initialized git directory! """
        # Configure path to use development git-fat binary script
        self.oldpath = os.environ["PATH"]
        test_dir = os.path.dirname(os.path.realpath(__file__))
        os.environ["PATH"] = ':'.join([test_dir] + self.oldpath.split(':'))

        self.olddir = os.getcwd()

        # Can't test in the repo
        # Easiest way is to do it in temp dir
        self.tempdir = tempfile.mkdtemp(prefix='git-fat-test')
        logging.info("tempdir: {}".format(self.tempdir))

        os.chdir(self.tempdir)

        self.fatstore = os.path.join(self.tempdir, 'fat-store')
        os.mkdir(self.fatstore)

        self.repo = os.path.join(self.tempdir, 'fat-test1')
        git('init {}'.format(self.repo))
        os.chdir(self.repo)

    def _setup_gitfat_files(self):
        with open('.gitfat', 'w') as f:
            f.write('[copy]\nremote={}'.format(self.fatstore))
        with open('.gitattributes', 'w') as f:
            f.write('*.fat filter=fat -crlf')

    def tearDown(self):
        os.chdir(self.olddir)
        shutil.rmtree(self.tempdir)
        os.environ["PATH"] = self.oldpath


class InitTestCase(Base):

    def test_git_fat_init(self):
        with open('.gitfat', 'w') as f:
            f.write('[copy]\nremote={}'.format(self.fatstore))
        out = git('fat init')
        expect = 'Setting filters in .git/config\nCreating .git/fat/objects\nInitialized git-fat'.strip()
        self.assertEqual(out.strip(), expect)
        self.assertTrue(os.path.isdir('.git/fat/objects'))

        out = git('config filter.fat.clean')
        self.assertEqual(out.strip(), 'git-fat filter-clean %f')

        out = git('config filter.fat.smudge')
        self.assertEqual(out.strip(), 'git-fat filter-smudge %f')

    def test_existing_files_pattern_match(self):
        """ Don't convert existing files into git-fat files unless they get renamed """

        expect = 'a fat file'
        with open('a.fat', 'w') as f:
            f.write(expect)

        commit('initial')

        # Setup git-fat after first commit
        self._setup_gitfat_files()
        git('fat init')

        # Initializing git-fat doesn't convert it
        with open('a.fat', 'r') as f:
            actual = f.read()
        self.assertEqual(expect, actual)
        actual = read_index('a.fat')
        self.assertEqual(expect, actual)

        # change the repo without changing a.fat
        with open('README', 'w') as f:
            f.write("something else changed")
        commit('a.fat doesnt change')
        actual = read_index('a.fat')
        self.assertEqual(expect, actual)

        # changing the file alone doesn't convert it
        append_me = '\nmore stuff'
        with open('a.fat', 'a') as f:
            f.write(append_me)
        commit('a.fat changed')
        actual = read_index('a.fat')
        self.assertEqual(expect + append_me, actual)

        # finally, rename the file
        os.rename('a.fat', 'b.fat')
        commit('a.fat->b.fat')
        actual = read_index('b.fat')
        expect = '#$# git-fat ebf646b3730c9f5ec2625081eb488c55000f622e                   21\n'
        self.assertEqual(expect, actual)


class InitRepoTestCase(Base):

    def setUp(self):
        super(InitRepoTestCase, self).setUp()

        self._setup_gitfat_files()
        git('fat init')
        commit('inital')


class FileTypeTestCase(InitRepoTestCase):

    def test_symlink_74bytes(self):
        """ Verify symlinks which match magiclen don't get converted """
        # Create broken symlink
        # is exactly 74 bytes, the magic length
        os.symlink('/oe/dss-oe/dss-add-ons-testing-build/deploy/licenses/common-licenses/GPL-3', 'c.fat')
        git('add c.fat')
        git('commit -m"added_symlink"')
        self.assertTrue(os.path.islink('c.fat'))

    def test_file_with_spaces(self):
        """ Ensure that files with spaces don't make git-fat barf """
        contents = 'This is a fat file\n'
        filename = 'A fat file with spaces.fat'
        with open(filename, 'w') as f:
            f.write(contents)
        commit("Nobody expects a space inafilename")
        self.assertTrue('#$# git-fat ' in read_index(filename))


class GeneralTestCase(InitRepoTestCase):

    def setUp(self):
        super(GeneralTestCase, self).setUp()

        filename = 'a.fat'
        contents = 'a'
        with open(filename, 'w') as f:
            f.write(contents * 1024)
        filename = 'b.fat'
        with open(filename, 'w') as f:
            f.write(contents * 1024 * 1024)
        filename = 'c d e.fat'
        with open(filename, 'w') as f:
            f.write(contents * 2048 * 1024)
        commit("add fatfiles")

    def test_status(self):
        out = git('fat status')
        self.assertEqual(out, '')
        objhash = read_index('b.fat').split()[2]
        path = os.path.join(os.getcwd(), '.git/fat/objects', objhash)
        os.rename(path, os.path.join(self.tempdir, objhash))
        os.remove('b.fat')

        # Need to checkout the file again so that it can be re-smudged
        git('checkout b.fat')

        # get the hash
        out = git('fat status')
        self.assertTrue('Orphan' in out)
        self.assertTrue(objhash in out)

        # Remove the file again
        os.remove('b.fat')
        # commit this time
        commit('remove file')

        os.rename(os.path.join(self.tempdir, objhash), path)
        # get the hash
        out = git('fat status')
        self.assertTrue('Stale' in out)
        self.assertTrue(objhash in out)

    def test_list(self):
        files = ('a.fat', 'b.fat', 'c d e.fat')
        hashes = {f: read_index(f).split()[2] for f in files}

        out = git('fat list')
        lines = out.split('\n')[:-1]  # ignore trailing newline
        for line in lines:
            objhash, filename = line.split(' ', 1)
            self.assertEqual(hashes[filename], objhash)

    def test_find(self):
        contents = 'b'

        filename = 'small.sh'
        with open(filename, 'w') as f:
            f.write(contents * 9990)
        # make sure they don't match our filter first
        filename = 'b.notfat'
        with open(filename, 'w') as f:
            f.write(contents * 1024 * 1024)
        filename = 'c d e.notfat'
        with open(filename, 'w') as f:
            f.write(contents * 2048 * 1024)
        commit('oops, added files not matching .gitattributes')
        out = git('fat find 10000')
        self.assertTrue('b.notfat' in out)
        self.assertTrue('c d e.notfat' in out)
        self.assertTrue('small.sh' not in out)


if __name__ == "__main__":
    logging.basicConfig(format='%(levelname)s:%(filename)s:%(message)s', level=logging.DEBUG)
    unittest.main()
