#!/usr/bin/env python3
"""Copy jobhunt-postman.json to iCloud Drive TEST API folder."""
import subprocess, os, shutil

# Get iCloud Drive path via osascript
result = subprocess.run(
    ['osascript', '-e', 'POSIX path of (path to iCloud Drive)'],
    capture_output=True, text=True, timeout=10
)
icloud_path = result.stdout.strip()
print(f"iCloud path: {icloud_path}")

if not icloud_path or not os.path.exists(icloud_path):
    print("ERROR: iCloud Drive not found or not accessible")
    exit(1)

# Create TEST API folder
test_api_dir = os.path.join(icloud_path, "TEST API")
os.makedirs(test_api_dir, exist_ok=True)
print(f"Created/Moved to: {test_api_dir}")

# Copy the file
src = "/Users/jahangir/jobhunt/jobhunt-postman.json"
dst = os.path.join(test_api_dir, "jobhunt-postman.json")
shutil.copy2(src, dst)
print(f"Copied: {src} -> {dst}")
print("OK")
