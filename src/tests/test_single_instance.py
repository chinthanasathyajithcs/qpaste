import sys
import unittest
from unittest.mock import patch, MagicMock
from core.single_instance import SingleInstance, ERROR_ALREADY_EXISTS

class TestSingleInstance(unittest.TestCase):
    def test_acquire_first_instance(self):
        si = SingleInstance("Local\\Test_QPaste_Mutex_Unique_1")
        result = si.acquire()
        self.assertTrue(result)
        si.release()

    def test_acquire_second_instance_fails(self):
        si1 = SingleInstance("Local\\Test_QPaste_Mutex_Unique_2")
        result1 = si1.acquire()
        self.assertTrue(result1)

        si2 = SingleInstance("Local\\Test_QPaste_Mutex_Unique_2")
        result2 = si2.acquire()
        self.assertFalse(result2)

        si1.release()
        si2.release()

    @patch("sys.platform", "linux")
    def test_non_windows_platform(self):
        si = SingleInstance("Local\\Test_QPaste_Mutex_NonWin")
        result = si.acquire()
        self.assertTrue(result)
        si.release()

if __name__ == "__main__":
    unittest.main()
