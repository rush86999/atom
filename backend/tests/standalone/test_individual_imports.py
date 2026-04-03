
import os
import sys

sys.path.append(os.path.dirname(os.getcwd()))
sys.path.append(os.getcwd())

modules_to_test = [
    "backend.sales.models",
    "backend.ecommerce.models",
    "backend.marketing.models",
    "backend.core.models",
    "backend.integrations.ai_enhanced_service"
]

with open("import_debug.log", "w") as f:
    f.write("Starting granular import test...\n")
    for module in modules_to_test:
        try:
            f.write(f"Importing {module}...")
            f.flush()
            __import__(module, fromlist=[''])
            f.write(" OK\n")
        except Exception as e:
            f.write(f" FAILED: {e}\n")
            import traceback
            traceback.print_exc(file=f)

