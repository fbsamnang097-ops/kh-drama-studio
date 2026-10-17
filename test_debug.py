import builtins
import sys

def safe_open(*args, **kwargs):
    print("OPEN CALLED WITH:", args, kwargs)
    if 'metadata_errors' in kwargs:
        print("ERROR: metadata_errors passed to open!")
        sys.exit(1)
    return builtins.open(*args, **kwargs)

builtins.open = safe_open

print("Running pipeline.py...")
try:
    import subprocess
    result = subprocess.run(['python3', 'pipeline.py', 'test', '--scenes', '1'], capture_output=True, text=True)
    print("Result:", result.returncode)
    print(result.stdout)
    print(result.stderr)
except Exception as e:
    print("Exception:", e)
    sys.exit(1)
print("Done")
