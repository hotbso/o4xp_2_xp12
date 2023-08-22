import os, os.path, shlex, subprocess
import time
import re
import threading
from queue import Queue, Empty
import configparser

XP12root = "E:\\X-Plane-12"
dsf_tool = "E:\\XPL-Tools\\xptools_win_23-4\\tools\\DSFtool"
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
        self.dsf_base, _ = os.path.splitext(os.path.basename(self.fname))
        self.rdata_fn = os.path.join(work_dir, self.dsf_base + ".rdata")

    def __repr__(self):
        return f"{self.fname}"

    def extract_raster_data(self, ithread = -1):
        i = self.fname.find("/Earth nav data/")
        assert i > 0, "invalid filename"
        if os.path.isfile(self.rdata_fn):
            return

        print(f"{i} -> S -> {self}")

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
                        #print(l.rstrip())
                        frd.write(l)

        os.remove(xp12_dsf_txt)
        print(f"{i} -> E -> {self}")

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
                dsf = self.queue.get(block = False)
            except Empty:
                break
            dsf.extract_raster_data(i)
            self.queue.task_done()

    def convert(self, num_workers):
        for i in range(num_workers):
            t = threading.Thread(target=self.worker, args=(i,), daemon = True)
            t.start()

        self.queue.join()

if not os.path.isdir(work_dir):
    os.makedirs(work_dir)

dsf_list = DsfList(XP12root)
dsf_list.scan()
#dsf_list.queue.put(Dsf("E:/X-Plane-12/Custom Scenery/z_autoortho/scenery/z_ao_sa/Earth nav data/-60-080/-53-074.dsf"))

dsf_list.convert(10)
