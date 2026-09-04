#!/usr/bin/env python3
"""
Diff CD 1.0 vs GOG 1.10 (DS2) by overlay segment to identify official patches.
"""
import subprocess
import json
import sys
from pathlib import Path

def get_map(exe_path):
    print(f"Mapping {exe_path}...")
    res = subprocess.run([sys.executable, "tools/ovr-map/ovr-map.py", str(exe_path), "--json"], 
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout)

def main():
    exe_10 = Path(".games/archive-org/cd10-extracted/DSUN.EXE")
    exe_110 = Path(".games/ds2/DSUN.EXE")

    map_10 = get_map(exe_10)
    map_110 = get_map(exe_110)

    with open(exe_10, "rb") as f:
        data_10 = f.read()
    with open(exe_110, "rb") as f:
        data_110 = f.read()

    print("Diffing overlay segments...")
    segs_10 = map_10["segments"]
    segs_110 = map_110["segments"]
    
    for i in range(min(len(segs_10), len(segs_110))):
        s1 = segs_10[i]
        s2 = segs_110[i]
        
        chunk_10 = data_10[s1["file_start"] : s1["file_end"]]
        chunk_110 = data_110[s2["file_start"] : s2["file_end"]]
        
        if chunk_10 == chunk_110:
            print(f"Segment {i:02d}: IDENTICAL")
        else:
            diff_len = len(chunk_110) - len(chunk_10)
            print(f"Segment {i:02d}: CHANGED (size delta: {diff_len} bytes)")
            
            # Simple byte diff
            min_len = min(len(chunk_10), len(chunk_110))
            diff_count = sum(1 for b1, b2 in zip(chunk_10[:min_len], chunk_110[:min_len]) if b1 != b2)
            print(f"  -> {diff_count} differing bytes in shared length, plus {abs(diff_len)} bytes length difference.")

if __name__ == "__main__":
    main()
