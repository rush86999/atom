
import sys
import os

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")
print(f"CWD: {os.getcwd()}")
print(f"Sys Path: {sys.path}")

try:
    import numpy
    print(f"✅ numpy: {numpy.__version__} at {numpy.__file__}")
except ImportError as e:
    print(f"❌ numpy: {e}")

try:
    import pandas
    print(f"✅ pandas: {pandas.__version__} at {pandas.__file__}")
except ImportError as e:
    print(f"❌ pandas: {e}")

try:
    import lancedb
    print(f"✅ lancedb: {lancedb.__version__} at {lancedb.__file__}")
except ImportError as e:
    print(f"❌ lancedb: {e}")

try:
    import sentence_transformers
    print(f"✅ sentence_transformers: {sentence_transformers.__version__} at {sentence_transformers.__file__}")
except ImportError as e:
    print(f"❌ sentence_transformers: {e}")
