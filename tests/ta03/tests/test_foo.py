import unittest

class TestSuite(unittest.TestCase):
    def test_record_passing(self):
        with open("test-ran", "w") as f:
            f.write("Done")
