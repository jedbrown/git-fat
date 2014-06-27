import os
import shutil
import subprocess as sub
import tempfile
import unittest
import logging


logging.basicConfig(format='%(levelname)s:%(filename)s:%(message)s',  level=logging.DEBUG)


def call(cmd, *args, **kwargs):

    if isinstance(cmd, str):
        cmd = cmd.split()

    # Uncomment to see command execution
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


class BaseTestCase(unittest.TestCase):

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

    def tearDown(self):
        # Only cleanup if successful so we can inspect results
        if self._resultForDoCleanups.wasSuccessful():
            shutil.rmtree(self.tempdir)
            os.environ["PATH"] = self.oldpath


class HappyTestCase(BaseTestCase):

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



if __name__ == "__main__":
    unittest.main()
