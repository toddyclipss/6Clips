import os
import sys
from pathlib import Path

# Force isolated test environment
base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir))
test_data_dir = base_dir / "tmp_isolated_test"
os.environ["VIRALMINT_DATA_DIR"] = str(test_data_dir)
os.environ["HOST"] = "127.0.0.1"
os.environ["PORT"] = "16889"

import uvicorn
from backend.main import app

if __name__ == "__main__":
    print(f"Starting isolated test server on 127.0.0.1:16889 with data_dir={test_data_dir}...")
    uvicorn.run(app, host="127.0.0.1", port=16889, log_level="info")
