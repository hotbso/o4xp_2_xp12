
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

import sys, os, os.path, shlex, subprocess
import re
import threading
from queue import Queue, Empty
import configparser
import logging

log = logging.getLogger("o4x_2_xp12")

XP12root = "E:\\X-Plane-12"
dsf_tool = "E:\\XPL-Tools\\xptools_win_23-4\\tools\\DSFtool"
cmd_7zip = "c:\\Program Files\\7-Zip\\7z.exe"

work_dir = "work"

class Dsf():
    def __init__(self, fname):
        self.fname = fname.replace('\\', '/')
        self.fname_bck = self.fname + "-bck"
        self.dsf_base, _ = os.path.splitext(os.path.basename(self.fname))
        self.rdata_fn = os.path.join(work_dir, self.dsf_base + ".rdata")
        self.rdata = []

    def __repr__(self):
        return f"{self.fname}"

    def convert(self):
        i = self.fname.find("/Earth nav data/")
        assert i > 0, "invalid filename"
        if os.path.isfile(self.rdata_fn):
            self.rdata = open(self.rdata_fn, "r").readlines()
        else:
            xp12_dsf = XP12root + "/Global Scenery/X-Plane 12 Global Scenery" + self.fname[i:]
            xp12_dsf_txt = os.path.join(work_dir, self.dsf_base + ".txt-xp12")
            #print(xp12_dsf)
            #print(xp12_dsf_txt)
            out = subprocess.run(shlex.split(f'"{dsf_tool}" -dsf2text "{xp12_dsf}" "{xp12_dsf_txt}"'), shell = True)
            if out.returncode != 0:
                log.error(f"Can't run {dsf_tool}: {out}")
                return False

            with open(self.rdata_fn, "w") as frd:
                with open(xp12_dsf_txt, "r") as dsft:
                    for l in dsft.readlines():
                        if l.find("RASTER_") == 0:
                            self.rdata.append(l)
                            #print(l.rstrip())
                            frd.write(l)

            os.remove(xp12_dsf_txt)

        o4xp_dsf = self.fname
        if os.path.isfile(self.fname_bck):
            o4xp_dsf = self.fname_bck

        o4xp_dsf_txt = os.path.join(work_dir, self.dsf_base + ".txt-o4xp")
        out = subprocess.run(shlex.split(f'"{dsf_tool}" -dsf2text "{o4xp_dsf}" "{o4xp_dsf_txt}"'), shell = True)
        if out.returncode != 0:
            log.error(f"Can't run {dsf_tool}: {out}")
            return False

        with open(o4xp_dsf_txt, 'a') as f:
            for l in self.rdata:
                if (l.find("spr") > 0 or l.find("sum") > 0 or l.find("win") > 0 # make a positive list
                   or l.find("fal") > 0 or l.find("soundscape") > 0 or l.find("elevation") > 0):
                    f.write(l)

        fname_new = self.fname + "-new"
        fname_new_1 = fname_new + "-1"
        out = subprocess.run(shlex.split(f'"{dsf_tool}" -text2dsf "{o4xp_dsf_txt}" "{fname_new_1}"'), shell = True)
        if out.returncode != 0:
            log.error(f"Can't run {dsf_tool}: {out}")
            return False

        cmd = shlex.split(f'"{cmd_7zip}" a -t7z -m0=lzma "{fname_new}" "{fname_new_1}"')
        out = subprocess.run(cmd, shell = True)
        if out.returncode != 0:
            log.error(f"Can't run {cmd}: {out}")
            return False

        os.remove(fname_new_1)
        return True

class DsfList():
    _o4xp_re = re.compile('zOrtho4XP_.*')
    _ao_re = re.compile('z_autoortho.scenery.z_ao_[a-z]+')

    def __init__(self, xp12root):
        self.xp12root = xp12root
        self.queue = Queue()
        self.custom_scenery = os.path.normpath(os.path.join(XP12root, "Custom Scenery"))

    def scan(self):
        for dir, dirs, files in os.walk(self.custom_scenery):
            if not self._o4xp_re.search(dir) and  not self._ao_re.search(dir):
                continue
            for f in files:
                _, ext = os.path.splitext(f)
                if ext != '.dsf':
                    continue
                self.queue.put(Dsf(os.path.join(dir, f)))

    def worker(self, i):
         while True:
            try:
                dsf = self.queue.get(block = False, timeout = 5)    # timeout to make it interruptible
            except Empty:
                break

            print(f"{i} -> S -> {dsf}")

            try:
                dsf.convert()
            except:
                pass

            print(f"{i} -> E -> {dsf}")
            self.queue.task_done()

    def convert(self, num_workers):
        for i in range(num_workers):
            t = threading.Thread(target=self.worker, args=(i,), daemon = True)
            t.start()

        self.queue.join()

###########
## main
###########
logging.basicConfig(level=logging.INFO,
                    handlers=[logging.FileHandler(filename = "o4xpsm_install.log", mode='w'),
                              logging.StreamHandler()])

#log.info(f"Version: {version}")

log.info(f"args: {sys.argv}")

if not os.path.isdir(work_dir):
    os.makedirs(work_dir)

dsf_list = DsfList(XP12root)
#dsf_list.scan()
dsf_list.queue.put(Dsf("E:/X-Plane-12/Custom Scenery/z_autoortho/scenery/z_ao_eur/Earth nav data/+50+000/+51+009.dsf"))

dsf_list.convert(10)
