import sys, os
import zipfile
from pathlib import Path

from .gathering import gather
from .filtering import filter
from .optimizing import optimize

COUNTER = 0


async def pack_files(zf, packlist, zfolders, target_folder):
    global COUNTER
    print("\n" * 4)
    print("=" * 80)
    print(target_folder)
    print("\n" * 4)
    for asset in packlist:
        zpath = list(zfolders)
        zpath.insert(0, str(target_folder))
        zpath.append(str(asset)[1:])

        zip_content = target_folder / str(asset)[1:]

        zpath = list(zfolders)
        zpath.append(str(asset)[1:].replace("-pygbag.", "."))

        if not zip_content.is_file():
            print("ERROR", zip_content)
            break
        zip_name = Path("/".join(zpath))
        COUNTER += 1
        zf.write(zip_content, zip_name)

    # raise SystemExit


async def archive(apkname, target_folder, build_dir=None):
    global COUNTER

    COUNTER = 0

    if build_dir:
        apkname = build_dir.joinpath(apkname).as_posix()

    walked = []
    for folder, filenames in gather(target_folder):
        walked.append([folder, filenames])
        sched_yield()

    filtered = []
    last = ""
    for infolder, fullpath in filter(walked):
        if last != infolder:
            print(f"Now in {infolder}")
            last = infolder

        print(" " * 4, fullpath)
        filtered.append(fullpath)
        sched_yield()

    packlist = []
    for filename in optimize(target_folder, filtered):
        packlist.append(filename)
        sched_yield()

    try:
        with zipfile.ZipFile(
            apkname, mode="x", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zf:
            # pack_files(zf, Path.cwd(), ["assets"], target_folder)
            await pack_files(zf, packlist, ["assets"], target_folder)

    except TypeError:
        # 3.6 does not support compresslevel
        with zipfile.ZipFile(apkname, mode="x", compression=zipfile.ZIP_DEFLATED) as zf:
            # pack_files(zf, Path.cwd(), ["assets"], target_folder)
            await pack_files(zf, packlist, ["assets"], target_folder)

    print(f"packing {COUNTER} files complete")


async def web_archive(apkname, build_dir):
    archfile = build_dir.with_name("web.zip")
    if archfile.is_file():
        archfile.unlink()

    with zipfile.ZipFile(archfile, mode="x", compression=zipfile.ZIP_STORED) as zf:
        for f in ("index.html", "favicon.png", apkname):
            zf.write(build_dir.joinpath(f), f)
