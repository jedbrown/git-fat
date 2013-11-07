import unittest
import os
import sys

fat_module = os.path.join(os.path.realpath(os.path.dirname(__file__)),'../git_fat')
fat_module = os.path.normpath(fat_module)
sys.path.insert(0, fat_module)

import git_fat

class GitFatTest(unittest.TestCase):

    def setUp(self):
        self.gf = git_fat.GitFat()


    def tearDown(self):
        pass

if __name__ == '__main__':

    unittest.main()

