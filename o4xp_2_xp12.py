# MIT License

# Copyright (c) 2023 Holger Teutsch

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

VERSION = "1.4-b2"

import tempfile
import platform, sys, os, os.path, time, shlex, subprocess, shutil, re, threading
from queue import Queue, Empty
import configparser
import logging

log = logging.getLogger("o4xp_2_xp12")


class Dsf:

    def __init__(self, fname):
        self.fname = fname.replace("\\", "/")
        self.fname_bck = self.fname + "-pre_o4xp_2_xp12"
        self.cnv_marker = self.fname + "-o4xp_2_xp12_done"
        self.dsf_base, _ = os.path.splitext(os.path.basename(self.fname))
        self.rdata = []
        self.is_converted = os.path.isfile(self.cnv_marker)
        self.has_backup = os.path.isfile(self.fname_bck)

    def __repr__(self):
        return f"{self.fname}"

    def run_cmd(self, cmd):
        # "shell = True" is not needed on Windows, bombs on Lx
        # log.info(cmd)
        out = subprocess.run(shlex.split(cmd), capture_output=True)
        if out.returncode != 0:
            log.error(f"Can't run {cmd}: {out}")
            return False

        return True

    def convert(self):
        i = self.fname.find("/Earth nav data/")
        assert i > 0, "invalid filename"

        tmp_files = []

        try:
            o4xp_dsf_txt = os.path.join(work_dir, self.dsf_base + ".txt-o4xp")
            tmp_files.append(o4xp_dsf_txt)
            for n in [
                "spr1",
                "sum1",
                "fal1",
                "win1",
                "spr2",
                "sum2",
                "fal2",
                "win2",
                "soundscape",
                "sea_level",
                "elevation",
            ]:
                tmp_files.append(
                    f"{o4xp_dsf_txt}.{n}.raw",
                )

            if not self.run_cmd(
                f'"{dsf_tool}" -dsf2text "{self.fname}" "{o4xp_dsf_txt}"'
            ):
                return False

            # sanity checks
            o4xp_dsf_txt_lines = open(o4xp_dsf_txt, "r").readlines()
            if not any("PATCH_VERTEX" in l for l in o4xp_dsf_txt_lines):
                log.warning(f"{self.fname} does not contain a mesh, skipped")
                return False

            if any("RASTER" in l for l in o4xp_dsf_txt_lines):
                log.warning(f"{self.fname} contains RASTER data, skipped")
                return False

            # extract raster data from XP12
            # demo areas overlay global scenery
            xp12_dsf = (
                xp12_root + "/Global Scenery/X-Plane 12 Demo Areas" + self.fname[i:]
            )
            if not os.path.isfile(xp12_dsf):
                xp12_dsf = (
                    xp12_root
                    + "/Global Scenery/X-Plane 12 Global Scenery"
                    + self.fname[i:]
                )

            xp12_dsf = os.path.normpath(xp12_dsf)
            if not os.path.isfile(xp12_dsf):
                log.warning(f"{xp12_dsf} does not exist!")
                return False

            xp12_dsf_txt = os.path.join(work_dir, self.dsf_base + ".txt-xp12")
            tmp_files.append(xp12_dsf_txt)
            for n in [
                "spr1",
                "sum1",
                "fal1",
                "win1",
                "spr2",
                "sum2",
                "fal2",
                "win2",
                "soundscape",
                "sea_level",
                "elevation",
            ]:
                tmp_files.append(
                    f"{xp12_dsf_txt}.{n}.raw",
                )

            # print(xp12_dsf)
            # print(xp12_dsf_txt)
            if not self.run_cmd(
                f'"{dsf_tool}" -dsf2text "{xp12_dsf}" "{xp12_dsf_txt}"'
            ):
                return False

            with open(xp12_dsf_txt, "r") as dsft:
                for l in dsft.readlines():
                    if l.find("RASTER_") == 0:
                        self.rdata.append(l)

            # append RASTER to o4xp file
            with open(o4xp_dsf_txt, "a") as f:
                for l in self.rdata:
                    if (
                        l.find("spr") > 0
                        or l.find("sum") > 0
                        or l.find("win") > 0  # use a positive list
                        or l.find("fal") > 0
                        or l.find("soundscape") > 0
                        or l.find("elevation") > 0
                    ):
                        f.write(l)

            # always create a backup
            if not os.path.isfile(self.fname_bck):
                shutil.copy2(self.fname, self.fname_bck)

            fname_new = self.fname + "-new"
            fname_new_1 = fname_new + "-1"
            tmp_files.append(fname_new_1)
            if not self.run_cmd(
                f'"{dsf_tool}" -text2dsf "{o4xp_dsf_txt}" "{fname_new_1}"'
            ):
                return False

            if not self.run_cmd(
                f'"{cmd_7zip}" a -t7z -m0=lzma "{fname_new}" "{fname_new_1}"'
            ):
                return False
        finally:
            for f in tmp_files:
                try:
                    os.remove(f)
                except:
                    pass

        os.remove(self.fname)
        os.rename(fname_new, self.fname)
        open(self.cnv_marker, "w")  # create the marker
        return True

    def undo(self):
        os.remove(self.fname)
        os.rename(self.fname_bck, self.fname)
        try:
            os.remove(self.cnv_marker)
        except:
            pass

    def cleanup(self):
        os.remove(self.fname_bck)


class DsfList:
    # modes
    M_CONVERT = 0
    M_REDO = 1
    M_UNDO = 2
    M_CLEANUP = 3

    def __init__(self, dir_re, xp12_root, ortho_dir):
        self._dir_re = re.compile(dir_re)
        self.queue = Queue()
        self._threads = []
        self.xp12_root = xp12_root
        self.ortho_dir = os.path.normpath(ortho_dir)

    def scan(self, mode, limit, subset, rect):
        lat_lon_re = None
        if rect is not None:
            lat1, lon1, lat2, lon2 = rect
            lat_lon_re = re.compile(r"([+-]\d\d)([+-]\d\d\d).dsf")

        try:  # until StopIteration
            for dir, dirs, files in os.walk(self.ortho_dir):
                if not self._dir_re.search(dir):
                    continue

                for f in files:
                    if limit <= 0:
                        raise StopIteration  # break out of all loops

                    _, ext = os.path.splitext(f)
                    if ext != ".dsf":
                        continue

                    full_name = os.path.join(dir, f)
                    if subset is not None:
                        if full_name.find(subset) < 0:
                            continue

                    if lat_lon_re is not None:
                        m = lat_lon_re.match(f.replace("\\", "/"))
                        assert m is not None
                        lat = int(m.group(1))
                        lon = int(m.group(2))
                        if lat < lat1 or lon < lon1 or lat > lat2 or lon > lon2:
                            continue

                    dsf = Dsf(full_name)
                    if mode == self.M_CONVERT and not dsf.is_converted:
                        self.queue.put(dsf)
                        limit = limit - 1
                        log.info(f"queued {dsf}")

                    elif mode == self.M_REDO and dsf.is_converted:
                        if dsf.has_backup:
                            self.queue.put(dsf)
                            log.info(f"queued {dsf}")
                            limit = limit - 1
                        else:
                            log.warning(f"{dsf} has no backup")

                    elif mode == self.M_UNDO:
                        if dsf.has_backup:
                            self.queue.put(dsf)
                            log.info(f"queued {dsf}")
                            limit = limit - 1
                        elif dsf.is_converted:
                            log.warning(f"{dsf} has no backup, can't undo")

                    elif mode == self.M_CLEANUP:
                        if dsf.has_backup and dsf.is_converted:
                            self.queue.put(dsf)
                            limit = limit - 1
                            log.info(f"queued {dsf}")
        except StopIteration:
            pass

        log.info(f"Queued {self.queue.qsize()} files")

    def worker(self, i, mode):
        while True:
            try:
                dsf = self.queue.get(
                    block=False, timeout=5
                )  # timeout to make it interruptible
            except Empty:
                break

            log.info(f"Worker {i} --> {dsf}")

            try:
                if mode == DsfList.M_CONVERT or mode == DsfList.M_REDO:
                    dsf.convert()
                elif mode == DsfList.M_UNDO:
                    dsf.undo()
                elif mode == DsfList.M_CLEANUP:
                    dsf.cleanup()
                else:
                    assert False

            except Exception as err:
                log.warning({err})

            log.info(f"Worker {i} <-- {dsf}")

    def execute(self, num_workers, mode):
        qlen_start = self.queue.qsize()
        start_time = time.time()

        for i in range(num_workers):
            t = threading.Thread(target=self.worker, args=(i, mode), daemon=True)
            self._threads.append(t)
            t.start()

        while True:
            qlen = self.queue.qsize()
            if qlen == 0:
                break
            log.info(
                f"{qlen_start - qlen}/{qlen_start} = {100 * (1-qlen/qlen_start):0.1f}% processed"
            )
            time.sleep(20)

        for t in self._threads:
            t.join()

        end_time = time.time()
        log.info(
            f"Processed {qlen_start} tiles in {end_time - start_time:0.1f} seconds"
        )


###########
## main
###########
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler(filename="o4x_2_xp12.log", mode="w"),
        logging.StreamHandler(),
    ],
)

log.info(f"Version: {VERSION}")
log.info(f"args: {sys.argv}")
isRunningInXplaneRoot = False

CFG = configparser.ConfigParser()
if not os.path.isfile("o4xp_2_xp12.ini"):
    log.error("ini file 'o4xp_2_xp12.ini' does not exist!")
    # check if we are under xplane root
    if os.path.isfile(
        "Resources/default scenery/default apt dat/Earth nav data/apt.dat"
    ):
        log.warning("You are in an X-Plane root directory, but the ini file is missing")
        log.warning(
            "Please copy the ini file from the tools directory to this location"
        )
        isRunningInXplaneRoot = True
    else:
        sys.exit(1)

if not isRunningInXplaneRoot:
    CFG.read("o4xp_2_xp12.ini")
    dry_run = False


def usage():
    log.error(
        """o4xp_2_xp12 [-rect lower_left,upper_right] [-subset string] [-limit n] [-dry_run] [-root xp12_root] convert|undo|cleanup
            -rect       restrict to rectangle, corners format is lat,lon, e.g. +50+009
            -subset     matching filenames must contain the string
            -dry_run    only list matching files
            -root       override root
            -limit n    limit operation to n dsf files

            convert     you guessed it
            undo        undo conversions
            cleanup     remove backup files

            convert, undo, cleanup are mutually exclusive

            Examples:
                o4xp_2_xp12 -rect +36+019,+40+025 convert
                o4xp_2_xp12 -subset z_ao_eur -dry_run cleanup
                o4xp_2_xp12 -root E:/XP12-test -subset z_ao_eur -limit 1000 convert
                o4xp_2_xp12 -rect +36+019,+40+025 -cleanup
        """
    )
    sys.exit(2)


mode = None
subset = None
rect = None

limit = 10000000

i = 1
while i < len(sys.argv):
    if sys.argv[i] == "-root":
        i = i + 1
        if i >= len(sys.argv):
            usage()

        xp12_root = sys.argv[i]
        CFG["DEFAULTS"][
            "xp12_root"
        ] = xp12_root  # other values may be interpolated on xp12_root

    elif sys.argv[i] == "-rect":
        i = i + 1
        if i >= len(sys.argv):
            usage()

        m = re.match(r"([+-]\d\d)([+-]\d\d\d),([+-]\d\d)([+-]\d\d\d)", sys.argv[i])
        if m is None:
            usage()

        lat1 = int(m.group(1))
        lon1 = int(m.group(2))
        lat2 = int(m.group(3))
        lon2 = int(m.group(4))
        log.info(f"restricting to rect ({lat1},{lon1}) -> ({lat2},{lon2})")
        rect = (lat1, lon1, lat2, lon2)

    elif sys.argv[i] == "-subset":
        i = i + 1
        if i >= len(sys.argv):
            usage()

        subset = sys.argv[i]

    elif sys.argv[i] == "-limit":
        i = i + 1
        if i >= len(sys.argv):
            usage()

        limit = int(sys.argv[i])
        if limit <= 0:
            usage()

    elif sys.argv[i] == "-dry_run":
        dry_run = True

    elif sys.argv[i] == "convert":
        if mode is not None:
            usage()
        mode = DsfList.M_CONVERT

    elif sys.argv[i] == "redo":
        if mode is not None:
            usage()
        mode = DsfList.M_REDO

    elif sys.argv[i] == "undo":
        if mode is not None:
            usage()
        mode = DsfList.M_UNDO

    elif sys.argv[i] == "cleanup":
        if mode is not None:
            usage()
        mode = DsfList.M_CLEANUP

    else:
        usage()

    i = i + 1

if mode is None:
    usage()

# added in 1.2
dir_re = CFG["DEFAULTS"].get(
    "dir_re",
    "zOrtho4XP_.*|z_autoortho.scenery.z_ao_[a-z]+|Orbx_.*_TE_Orthos|zVStates_.*",
)

# get xp12_root or default to current script location
xp12_root = CFG["DEFAULTS"].get(
    "xp12_root", os.path.dirname(os.path.realpath(__file__))
)
# get work_dir or default to system temp
work_dir = CFG["DEFAULTS"].get("work_dir", tempfile.gettempdir())
ortho_dir = CFG["DEFAULTS"]["ortho_dir"]
# get num_workers or default to 10
num_workers = int(CFG["DEFAULTS"].get("num_workers", 10))
# get pyinstaller fs path
if hasattr(sys, "_MEIPASS"):
    MEIPASS_PATH = sys._MEIPASS
# get dsf_tool or default to dsf_tool in pyinstaller bundle
dsf_tool = CFG["TOOLS"].get("dsf_tool", os.path.join(MEIPASS_PATH, "dsf_tool"))
cmd_7zip = CFG["TOOLS"].get("7zip", os.path.join(MEIPASS_PATH, "7z"))

sanity_checks = True
if not os.path.isdir(xp12_root):
    sanity_checks = False
    log.error(f"xp12_root: '{xp12_root}' is not a valid directory")

if not os.path.isdir(ortho_dir):
    sanity_checks = False
    log.error(f"ortho_dir: '{ortho_dir}' is not a valid directory")

if not os.path.isfile(dsf_tool):
    sanity_checks = False
    log.error(f"dsf_tool: '{dsf_tool}' is not pointing to a file")

if platform.system() == "Windows":
    if not os.path.isfile(cmd_7zip):
        sanity_checks = False
        log.error(f"cmd_7zip: '{cmd_7zip}' is not pointing to a file")

if not sanity_checks:
    sys.exit(2)

log.info(f"dir_re:    {dir_re}")
log.info(f"xp12_root: {xp12_root}")
log.info(f"ortho_dir: {ortho_dir}")
log.info(f"work_dir:  {work_dir}")
log.info(f"dsf_tool:  {dsf_tool}")
log.info(f"cmd_7zip:  {cmd_7zip}")

dsf_list = DsfList(dir_re, xp12_root, ortho_dir)

if not os.path.isdir(work_dir):
    os.makedirs(work_dir)

if not os.access(work_dir, os.W_OK):
    log.error(f"work_dir: '{work_dir}' is not writeable")
    sys.exit(2)

dsf_list.scan(mode, limit, subset, rect)

# dsf_list.queue.put(Dsf("E:/X-Plane-12/Custom Scenery/z_autoortho/scenery/z_ao_eur/Earth nav data/+50+000/+51+009.dsf"))
if not dry_run:
    dsf_list.execute(num_workers, mode)
