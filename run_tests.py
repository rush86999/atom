import unittest
import sys
import os

if __name__ == '__main__':
    # Add the atomic-docker directory to the Python path
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'atomic-docker')))

    # Discover and run the tests
    loader = unittest.TestLoader()
    suite = loader.discover('project/functions/atom-agent', pattern='test_*.py')
    runner = unittest.TextTestRunner()
    runner.run(suite)
