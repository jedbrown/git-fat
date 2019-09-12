#!/usr/bin/env python
# -*- mode:python -*-
"""
Simple runner for test.sh but it modifies it to explicily test python2 and 3
"""
from __future__ import print_function,unicode_literals
import sys
import os
import shutil
import subprocess

if sys.version_info[0] <= 2:
    from io import open


# Build a dead-simple CLI. Not worth argparse, etc
help="""\
Run tests with specific versions

    $ ./run_test.py # Both Python 2 and 3
    $ ./run_test.py 2 # Only python2
    $ ./run_test.py 3 # Only python3

Any argument specified will be appended to the git-fat shebang. For example

    $ ./run_test.py 2.6

will change the shebang to 
    
    #!/usr/bin/env python2.6

Or specify more than one:

    $ ./run_test.py 2 3 2.6

"""
vers = sys.argv[1:]
if len(vers) == 0:
    vers = ['2','3']

if '-h' in vers or '--help' in vers:
    print(help)
    sys.exit()
    
for ver in vers:
    print('-='*20)
    print('Testing %s' % ver)
    print('-_'*20)
    
    testdir = 'TEST_py%s' % ver
    testdir = os.path.abspath(testdir)
    
    # Delete the prior test dir and make a new one
    if os.path.isdir(testdir):
        shutil.rmtree(testdir)
    os.makedirs(testdir)
    
    shebang = '#!/usr/bin/env python%s\n' % ver
    pathline = 'export PATH=%s:$PATH\n' % testdir
    
    testfile = os.path.join(testdir,'test%s.sh' % ver)
    testfileR = os.path.join(testdir,'test-retroactive%s.sh' % ver)
    fatfile = os.path.join(testdir,'git-fat')
    
    # Write the files. Do not use multiple with's to support 2.6
    with open('git-fat','rt') as infile:
        with open(fatfile,'wt') as outfile:
            infile.readline() # Skip shebang
            outfile.write(shebang)
            outfile.write(infile.read())
    
    with open('test.sh','rt') as infile:
        with open(testfile,'wt') as outfile:
            outfile.write(infile.readline()) # copy shebang
            outfile.write(pathline)
            outfile.write(infile.read())

    with open('test-retroactive.sh','rt') as infile:
        with open(testfileR,'wt') as outfile:
            outfile.write(infile.readline()) # copy shebang
            outfile.write(pathline)
            outfile.write(infile.read())
        
    os.chmod(fatfile, 509)
    os.chmod(testfile, 509)
    os.chmod(testfileR, 509)
    
    try:
        subprocess.check_call(['./test%s.sh' % ver],cwd=testdir)
    except subprocess.CalledProcessError as err:
        print('F'*60)
        print(err,file=sys.stderr)
        print('FAILED python %s'%ver,file=sys.stderr)
        sys.exit(1)
    
    print('###################')
    print('###### RETRO ######')
    print('###################')
    
    try:
        subprocess.check_call(['./test-retroactive%s.sh' % ver],cwd=testdir)
    except subprocess.CalledProcessError as err:
        print('F'*60)
        print(err,file=sys.stderr)
        print('FAILED RETRO python %s'%ver,file=sys.stderr)
        sys.exit(1)




