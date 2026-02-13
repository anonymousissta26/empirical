import os
import glob
import argparse

import subprocess as sp

from pathlib import Path


parser = argparse.ArgumentParser(
    description="Replay testcases and measure branch coverage"
)

parser.add_argument(
    "program",
    choices=["diff", "find", "gawk", "gcal", "grep", "sed"],
    help="Target program"
)

parser.add_argument(
    "baseline",
    choices=["featmaker", "symtuner", "topseed"],
    help="Baseline type"
)

parser.add_argument(
    "rq_number",
    choices=["1", "2", "3"],
    help="RQ number"
)

args = parser.parse_args()

program = args.program
baseline = args.baseline
rq_number = args.rq_number

output_dir = f"/root/main/empirical/dataset/RQ{rq_number}/{baseline}/{program}"  

# Change to absolute path of klee-replay bin file in your environment. (commonly in klee/build/bin directory)
replay_bin = "/root/main/klee/build/bin/klee-replay"

# Change to absolute path of each benchmark's gcov object in your environment.
targets = {
    "diff" : "/root/main/empirical/diffutils-3.7/obj-gcov/src/diff",     
    "find" : "/root/main/empirical/findutils-4.7.0/obj-gcov/find/find",
    "gawk" : "/root/main/empirical/gawk-5.1.0/obj-gcov/gawk",
    "gcal" : "/root/main/empirical/gcal-4.1/obj-gcov/src/gcal",
    "grep" : "/root/main/empirical/grep-3.6/obj-gcov/src/grep",
    "sed" : "/root/main/empirical/sed-4.8/obj-gcov/sed/sed"
}  

depths = {
    "diff" : 1,
    "find" : 1,
    "gawk" : 0,
    "gcal" : 1,
    "grep" : 1,
    "sed" : 1
}


def find_all(path, ends):
    found = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(f'.{ends}'):
                found.append(os.path.join(root, file))
    return found

def clear_gcov(g_path, depth=1):
    for _ in range(depth):
        g_path = g_path[:g_path.rfind('/')]
    gcdas = find_all(g_path, "gcda")
    gcovs = find_all(g_path, "gcov")
    for gcda in gcdas:
        os.system(f"rm -f {gcda}")
    for gcov in gcovs:
        os.system(f"rm -f {gcov}")


target = targets[program]
depth = depths[program]
target = Path(target).absolute()
target_dir = Path(target).parent
original_path = Path().absolute()

clear_gcov(str(target_dir))

covered = set()
testcases = list()

iterations = [f"{output_dir}/{it}" for it in os.listdir(output_dir) if it.startswith("iteration")]
if baseline in ["featmaker", "topseed"]:
    for it in iterations:
        outs = [f"{it}/{out}" for out in os.listdir(it)]
        for out in outs:
            testcases = testcases + [f"{out}/{f}" for f in os.listdir(out) if f.endswith(".ktest")]
elif baseline in ["symtuner"]:
    for it in iterations:
        testcases = testcases + [f"{it}/{f}" for f in os.listdir(it) if f.endswith(".ktest")]

for testcase in testcases:
    os.chdir(str(target.parent))
    cmd = ' '.join([replay_bin, str(target), str(testcase)])
    process = sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.PIPE, shell=True)
    try:
        _, stderr = process.communicate(timeout=0.1)
    except sp.TimeoutExpired:
        pass
    finally:
        process.kill()    
    
try:
    base = Path()
    for _ in range(depth):
        base = base / '..'
    gcda_pattern = base / '**/*.gcda'
    gcdas = list(target.parent.glob(str(gcda_pattern)))
    gcdas = [gcda.absolute() for gcda in gcdas]

    os.chdir(str(target_dir))
    cmd = ["gcov", '-b', *list(map(str, gcdas))]
    cmd = ' '.join(cmd)
    _ = sp.run(cmd, stdout=sp.PIPE, stderr=sp.PIPE, shell=True, check=True)

    base = Path()
    for _ in range(depth):
        if "gawk" in str(target) or "make" in str(target) or "sqlite" in str(target):
            pass
        else:
            base = base / '..'

    gcov_pattern = base / '**/*.gcov'
    gcovs = list(Path().glob(str(gcov_pattern)))

    for gcov in gcovs:
        try:
            with gcov.open(encoding='UTF-8', errors='replace') as f:
                file_name = f.readline().strip().split(':')[-1]
                for i, line in enumerate(f):
                    if ('branch' in line) and ('never' not in line) and ('taken 0%' not in line) and (
                            ":" not in line) and ("returned 0% blocks executed 0%" not in line):
                        bid = f'{file_name} {i}'
                        covered.add(bid)
        except:
            pass
    os.chdir(str(original_path))
except:
    pass

print("========== RESULT OF REPLAYING TESTCASES ==========")
print(f"Output Directory : {output_dir}")
print(f"Replayed Baseline : {baseline}")
print(f"# of Covered Branches : {len(covered)}")