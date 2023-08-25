import sys, struct, os
from PIL import Image
import configparser

class Raster():
    width = 1201
    height = 1201
    scale = 1.0
    offset = 0
    flags = 5
    bpp = 2

    def __init__(self, fname):
        self.fname = fname
        self.raw_data = open(fname, 'rb').read()
        assert self.width * self.height * self.bpp == len(self.raw_data)
        self.min = self.max = None

    def get_val(self, x, y):
        k = (y * self.width + x) * self.bpp
        return struct.unpack('h', self.raw_data[k:k+self.bpp])[0]

    def get_val_ll_frac(self, lat_frac, lon_frac):
        """Get by lat/lan fraction [0..1)"""
        assert 0 <= lat_frac and lat_frac < 1.0
        assert 0 <= lon_frac and lon_frac < 1.0

        return self.get_val(int(lon_frac * self.width), int(lat_frac * self.height))

    def get_min_max(self):
        min_val = 100000
        max_val = -100000

        for x in range(self.width):
            for y in range(self.height):
                val = self.get_val(x, y)
                min_val = min(val, min_val)
                max_val = max(val, max_val)

        self.min = min_val
        self.max = max_val
        return (min_val, max_val)

    def make_png(self):
        if self.min is None:
            self.get_min_max()

        img = Image.new('RGB', (self.width, self.height))# the image size
        for x in range(self.width):
            for y in range(self.height):
                val = self.get_val(x, y)
                red = 0
                blue = 0
                if val < 0:
                    blue = int(255.0 * val / self.min)
                if val > 0:
                    red = int(255.0 * val / self.max)

                img.putpixel((x, self.height - 1 - y), (red, 0, blue))

        png_name = os.path.basename(self.fname) + ".png"
        img.save(png_name)
        print(f"created {png_name}")

def usage():
    print( \
    """raster_tool [-make_png] lat lon""")
    exit(1)

###########
## main
###########
CFG = configparser.ConfigParser()
CFG.read('o4xp_2_xp12.ini')

work_dir = CFG['DEFAULTS']['work_dir']

make_png = False

if len(sys.argv) < 3:
    usage()

i = 1
while i < len(sys.argv):
    if sys.argv[i] == "-make_png":
        make_png = True
    elif len(sys.argv) - i == 2:
        lat = sys.argv[i]
        i = i + 1
        lon = sys.argv[i]
    else:
        usage()
    i = i + 1

lat = float(lat)
lon = float(lon)
#print(lat, lon)

# corner
lat_c = int(lat)
lat_frac = lat - lat_c
lon_c = int(lon)
lon_frac = lon - lon_c

fname_sea = os.path.join(work_dir, f"{lat_c:+03d}{lon_c:+04d}.txt-xp12.sea_level.raw")
fname_elevation = os.path.join(work_dir, f"{lat_c:+03d}{lon_c:+04d}.txt-xp12.elevation.raw")
#print(fname_sea)

sea = Raster(fname_sea)
elevation = Raster(fname_elevation)

#min_val, max_val = sea.get_min_max()
#print(f"min: {min_val}, max: {max_val}")

if make_png:
    sea.make_png()
    elevation.make_png()
    exit()

sv = sea.get_val_ll_frac(lat_frac, lon_frac)
ev = elevation.get_val_ll_frac(lat_frac, lon_frac)

print(f"sea value: {sv}, elevation value: {ev}")

