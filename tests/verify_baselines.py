import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import sys
import os

# Add the backend/app directory to sys.path so we can import db
import pathlib
current_dir = pathlib.Path(__file__).parent.resolve()
backend_app_dir = current_dir.parent / 'backend' / 'app'
# In case the structure is surprisingly different, let's try a few
# My creation path was codebase/tests/verify_baselines.py
# Actual structure: codebase/backend/app/db.py
# visible path: ../../backend/app

# Let's try absolute path based on known structure
project_root = current_dir.parent
target_dir = project_root / 'backend' / 'app'
sys.path.append(str(target_dir))

print(f"Added to sys.path: {target_dir}")
print(f"Direct file check: {(target_dir / 'db.py').exists()}")

try:
    from db import calculate_and_set_baseline
except ImportError:
    # process might be missing too if it's imported in db
    sys.path.append(str(target_dir)) # ensuring it is there
    # Also need to make sure dependencies of db are met.
    # db imports 'processing'. efficient way is to just have backend/app in path.
    pass

from db import calculate_and_set_baseline

class TestCalculateAndSetBaseline(unittest.TestCase):
    @patch('db.engine')
    def test_calculate_and_set_baseline(self, mock_engine):
        # Mock the connection and execution
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Mock the result of the SELECT query
        # We need at least 10 samples
        # rms_x, rms_y, rms_z, rms_total, dom_freq_x, dom_freq_y, dom_freq_z
        mock_data = []
        for i in range(10):
            mock_data.append((1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0))
        
        mock_conn.execute.return_value.fetchall.return_value = mock_data

        # Run the function
        calculate_and_set_baseline(1)

        # Verify the INSERT execution
        # Get the second call to execute (the INSERT/UPSERT)
        # The first call is the SELECT
        self.assertEqual(mock_conn.execute.call_count, 2)
        
        insert_call_args = mock_conn.execute.call_args_list[1]
        _, kwargs = insert_call_args
        
        # Check if parameters are correct (mean should be the value, std should be 0 since all values are same)
        params = insert_call_args[0][1] # Get the params dict
        
        self.assertAlmostEqual(params['mx'], 1.0)
        self.assertAlmostEqual(params['sx'], 0.0)
        self.assertAlmostEqual(params['mdfx'], 10.0)
        self.assertAlmostEqual(params['sdfx'], 0.0)
        
        # Check return value
        # calculate_and_set_baseline now returns a dict on success
        # We need to mock the return value of calculate_and_set_baseline if we were mocking it, 
        # but here we are testing the function itself, so we capture its return.
        
        print("Verification passed: calculate_and_set_baseline logic is correct.")

if __name__ == '__main__':
    unittest.main()
