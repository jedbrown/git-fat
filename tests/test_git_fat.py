import unittest
import os
import sys
import shutil
import tempfile

import subprocess as sub

printerr = sys.stderr.write

def call(cmd, *args, **kwargs):

    if isinstance(cmd, str):
        cmd = cmd.split()

    print('`{}`'.format(' '.join(cmd)))

    try:
        output = sub.check_output(cmd, stderr=sub.STDOUT, *args, **kwargs)
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

    def tearDown(self):

        for f in os.listdir(os.path.join(self.tempdir, 'fat-test')):
            if f.startswith('.coverage'):
                shutil.move(os.path.join(self.tempdir, 'fat-test', f),
                    os.path.join(self.olddir, f))
        os.chdir(self.olddir)
        # shutil.rmtree(self.tempdir)


    def test_git_fat_happy(self):

        base = os.getcwd()
        repo = os.path.join(base, 'fat-test')
        git('init {}'.format(repo))
        os.chdir(repo)
        out = git('fat init')
        self.assertEqual(out.strip(), 'Initialized git fat')
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
        git(['commit','-m"new repository'])

        with open('a.fat', 'w') as f:
            f.write('This is a fat file')

        git('add a.fat')
        git(['commit','-madded fatfile'])

        git('fat push')

        os.chdir(self.tempdir)

        repo2 = os.path.join(base, 'fat-test2')
        git('clone {} {}'.format(repo, repo2))

        os.chdir(repo2)
        git('fat init')
        print os.getcwd()
        print git('fat pull')
        print git('fat list')

if __name__ == '__main__':

    path = os.environ["PATH"]
    fat_repo = os.path.dirname(os.path.realpath(__file__))
    os.environ["PATH"] = ':'.join([fat_repo] + path.split(':'))

    unittest.main()

    os.environ["PATH"] = path
