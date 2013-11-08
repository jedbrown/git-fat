import os
import shutil
import subprocess as sub
import sys
import tempfile
import unittest

printerr = sys.stderr.write


def call(cmd, *args, **kwargs):

    if isinstance(cmd, str):
        cmd = cmd.split()

    # Uncomment to see command execution
    # print('`{}`'.format(' '.join(cmd)))

    try:
        # output = sub.check_output(cmd, stderr=sub.STDOUT, *args, **kwargs)
        output = sub.check_output(cmd, *args, **kwargs)
        # sub.call(cmd, *args, **kwargs)
    except sub.CalledProcessError as e:
        printerr("cmd `{}` returned {}\n".format(e.cmd, e.returncode))
        printerr("The output of the command was: \n")
        printerr("{}\n".format(e.output))
    return output


def git(cliargs, *args, **kwargs):

    if isinstance(cliargs, str):
        cliargs = cliargs.split()
    cmd = ['git'] + cliargs
    return call(cmd)


class GitFatTest(unittest.TestCase):

    def setUp(self):

        self.tempdir = tempfile.mkdtemp(prefix='git-fat-test')
        self.olddir = os.getcwd()
        os.chdir(self.tempdir)
        self.fatstore = os.path.join(self.tempdir, 'fat-store')

        self.repo1 = os.path.join(self.tempdir, 'fat-test1')
        self.repo2 = os.path.join(self.tempdir, 'fat-test2')
        self.repos = [self.repo1, self.repo2]

    def tearDown(self):

        # move all the coverage files
        for r, d, files in os.walk(self.tempdir):
            for f in files:
                if f.startswith('.coverage'):
                    shutil.copy2(os.path.join(r, f),
                        os.path.join(self.olddir, f))

        os.chdir(self.olddir)

        # Comment out below to inspect results
        shutil.rmtree(self.tempdir)

    def test_git_fat_happy(self):

        git('init {}'.format(self.repo1))
        os.chdir(self.repo1)

        # Do this first so it doesn't become a fat file
        os.symlink('/oe/dss-oe/dss-add-ons-testing-build/deploy/licenses/common-licenses/GPL-3', 'c.fat')
        git('add c.fat')
        git(['commit', '-madded legacy file'])

        out = git('fat init')
        expect = 'Setting filters in .git/config\nCreating .git/fat/objects\nInitialized git-fat'.strip()
        self.assertEqual(out.strip(), expect)
        self.assertTrue('objects' in os.listdir('.git/fat/'))

        out = git('config filter.fat.clean')
        self.assertEqual(out.strip(), 'git-fat filter-clean %f')

        out = git('config filter.fat.smudge')
        self.assertEqual(out.strip(), 'git-fat filter-smudge %f')

        with open('.gitfat', 'w') as f:
            f.write('[rsync]\nremote=localhost:{}'.format(self.fatstore))

        with open('.gitattributes', 'w') as f:
            f.write('*.fat filter=fat -crlf')

        git('add .gitattributes .gitfat')
        git(['commit', '-m"new repository'])

        contents = 'This is a fat file\n'
        with open('a.fat', 'w') as f:
            f.write(contents)

        git('add a.fat')
        git(['commit', '-madded fatfile'])

        git('fat push')

        os.chdir(self.tempdir)

        git('clone {} {}'.format(self.repo1, self.repo2))

        os.chdir(self.repo2)
        git('fat init')
        out = git('fat pull')
        with open('a.fat', 'r') as f:
            # Validate the file contents are correct (This tests the git race condition)
            self.assertEquals(f.read(), contents)

        out = git('fat list')
        self.assertTrue('a.fat' in out)

        out = git('fat status')

    def test_git_fat_config(self):

        git('init {}'.format(self.repo1))

        check = sub.Popen('git fat status'.split(), stdout=sub.PIPE, stderr=sub.STDOUT)
        self.assertEqual(check.wait(), 1)
        self.assertTrue('run from a git' in check.stdout.read())

        os.chdir(self.repo1)

        check = sub.Popen('git fat push'.split(), stdout=sub.PIPE, stderr=sub.STDOUT)
        self.assertEqual(check.wait(), 1)
        self.assertTrue('.gitfat is present' in check.stdout.read())

        with open('.gitfat', 'w') as f:
            f.write('')
        check = sub.Popen('git fat push'.split(), stdout=sub.PIPE, stderr=sub.STDOUT)
        self.assertEqual(check.wait(), 1)
        self.assertTrue('No rsync.remote' in check.stdout.read())

    def test_git_fat_status(self):

        git('init {}'.format(self.repo1))
        os.chdir(self.repo1)
        git('fat init')

        with open('.gitfat', 'w') as f:
            f.write('[rsync]\nremote=localhost:{}'.format(self.fatstore))

        with open('.gitattributes', 'w') as f:
            f.write('*.fat filter=fat -crlf')

        git('add .gitattributes .gitfat')
        git(['commit', '-m"new repository'])

        contents = 'This is a fat file\n'
        with open('a.fat', 'w') as f:
            f.write(contents)

        git('add a.fat')
        git(['commit', '-madded fatfile'])

        a_digest = os.listdir('.git/fat/objects')[0]

        # Change contents to make garbage
        git('mv a.fat b.fat')
        with open('b.fat', 'a') as f:
            f.write(contents)

        git('add b.fat')
        git(['commit', '-mupdated fatfile'])

        b_digest = list(set(os.listdir('.git/fat/objects')) - set([a_digest]))[0]
        # Remove a file to make an orphan
        os.remove(os.path.join(self.repo1, '.git/fat/objects/', b_digest))

        out = git('fat status')
        self.assertTrue('Garbage' in out)
        self.assertTrue('Orphan' in out)

        # Traversing the history we can see that the file
        # in .git/fat/objects belongs to a.fat
        out = git('fat -a status')
        self.assertTrue('Garbage' not in out)


if __name__ == '__main__':

    path = os.environ["PATH"]
    # Use our coverage python executable
    test_dir = os.path.dirname(os.path.realpath(__file__))
    # Use development version of git-fat
    git_fat_bin = os.path.normpath(os.path.join(test_dir, '../bin'))
    os.environ["PATH"] = ':'.join([test_dir, git_fat_bin] + path.split(':'))
    print os.environ["PATH"]

    unittest.main()

    os.environ["PATH"] = path
