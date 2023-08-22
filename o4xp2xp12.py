import os, os.path, shlex, subprocess
import time
import re
import threading
from queue import Queue, Empty
import configparser

XP12root = "E:\\X-Plane-12"
dsf_tool = "E:\\XPL-Tools\\xptools_win_23-4\\tools\\DSFtool"
cmd_7zip = "c:\\Program Files\\7-Zip\\7z.exe"

work_dir = "work"


def locked(fn):
    @wraps(fn)
    def wrapped(self, *args, **kwargs):
        #result = fn(self, *args, **kwargs)
        with self._lock:
            result = fn(self, *args, **kwargs)
        return result
    return wrapped

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
                exit(1)

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
            exit(1)

        with open(o4xp_dsf_txt, 'a') as f:
            for l in self.rdata:
                if (l.find("spr") > 0 or l.find("sum") > 0 or l.find("win") > 0 # make a positive list
                   or l.find("fal") > 0 or l.find("soundscape") > 0 or l.find("elevation") > 0):
                    f.write(l)

        fname_new = self.fname + "-new"
        out = subprocess.run(shlex.split(f'"{dsf_tool}" -text2dsf "{o4xp_dsf_txt}" "{fname_new}"'), shell = True)
        if out.returncode != 0:
            log.error(f"Can't run {dsf_tool}: {out}")
            exit(1)


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
            dsf.convert()
            print(f"{i} -> E -> {dsf}")
            self.queue.task_done()

    def convert(self, num_workers):
        for i in range(num_workers):
            t = threading.Thread(target=self.worker, args=(i,), daemon = True)
            t.start()

        self.queue.join()

if not os.path.isdir(work_dir):
    os.makedirs(work_dir)

dsf_list = DsfList(XP12root)
#dsf_list.scan()
dsf_list.queue.put(Dsf("E:/X-Plane-12/Custom Scenery/z_autoortho/scenery/z_ao_eur/Earth nav data/+50+000/+51+009.dsf"))

dsf_list.convert(10)
