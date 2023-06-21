#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import io
import sys
import stat
import datetime
import cgi
import json
import argparse

from jinja2 import Environment, FileSystemLoader
from http import cookies

import pyheif
import exifread

from PIL import Image
from PIL.ExifTags import TAGS

script_dir = os.path.dirname(__file__)


import pconfig # configuration of p
page_title = pconfig.page_title
image_dir = os.path.relpath(os.path.join(script_dir, pconfig.image_dir), os.getcwd())
thumb_dir = os.path.relpath(os.path.join(script_dir, pconfig.thumb_dir), os.getcwd())

thumb_width = 460
thumb_height = 380


env = Environment(loader = FileSystemLoader(script_dir + "/templates"))
tpl_index = env.get_template("index.html")


def listtxt_path(username):
    return os.path.join(image_dir, username, "list.txt")

class ExifData:
    def __init__(self, image_path = None):
        self.date = None
        self.model = None
        self.orientation = 1
        self.error = None
        if image_path:
            self.load(image_path)

    def load(self, image_path):

        """
        How to read exif from HEIF is:
        https://stackoverflow.com/questions/54395735/how-to-work-with-heic-image-file-types-in-python
        """

        with open(image_path, "rb") as f:
            if re.search(r"\.(HEIC|heic)$", image_path):
                im = pyheif.read_heif(image_path)
                for meta in im.metadata or []:
                    if meta["type"] == "Exif":
                        exif = exifread.process_file(io.BytesIO(meta["data"][6:]))
            else:
                exif = exifread.process_file(f)

        if not exif:
            self.error = "No Exif Data"
            return self

        for tag, v in exif.items():

            if tag == "EXIF DateTimeOriginal":
                # YYYY:MM:DD to YYYY/MM/DD
                self.date = str(v).replace(":", "/", 2)
            elif tag == "Image DateTime" and not self.date:
                self.date = str(v).replace(":", "/", 2)
            elif tag == "EXIF DateTimeDigitized" and not self.date:
                self.date = str(v).replace(":", "/", 2)
            elif tag == "Image Model":
                self.model = str(v)
            elif tag == "Image Orientation":
                self.orientation = v.values.pop(0)

        if not self.date:
            self.date = self.__class__.get_create_time(image_path)

        return self

    @classmethod
    def load_create_time(cls, image_path):
        try:
            ctime = os.path.getctime(image)
        except:
            return None
        return datetime.date.fromtimestamp(ctime).strftime("%Y/%m/%d uploaded")


    def todict(self):
        return {
            "date": self.date,
            "model": self.model,
            "orientation": self.orientation,
            "error": self.error,
        }

    @classmethod
    def fromdict(cls, d):
        exif = ExifData()
        for k, v in d.items():
            setattr(exif, k, v)
        return exif
        

class Photo:
    def __init__(self, username = None, filename = None):

        if (username and not filename) or (not username and filename):
            raise RuntimeError("username and filename must be both None or exist")

        self.username = username
        self.filename = filename

        if not username and not filename:
            return self

        self.image_path = os.path.join(image_dir, username, filename)
        self.thumb_path = os.path.join(thumb_dir, username, filename)
        self.thumb_path += ".jpg"
        self.image_url_path = os.path.relpath(self.image_path, script_dir)
        self.thumb_url_path = os.path.relpath(self.thumb_path, script_dir)
        self.exif = None
        
    def load_exit(self):
        self.exif = ExifData(self.image_path)

    def todict(self):
        if not self.exif:
            self.load_exit()
        return {
            "username": self.username,
            "image_path": self.image_path,
            "thumb_path": self.thumb_path,
            "image_url_path": self.image_url_path,
            "thumb_url_path": self.thumb_url_path,
            "exif": self.exif.todict(),
        }

    @classmethod
    def fromdict(cls, d):
        photo = Photo()
        for k, v in d.items():
            if k == "exif" and v != None:
                setattr(photo, k, ExifData.fromdict(v))
            setattr(photo, k, v)
        
    def upload(self, fh):
        
        """
        Read data from fh, write it to self.image_path, and create thumbnail
        at self.thumb_path.
        """
        with open(self.image_path, "wb") as f:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                f.write(chunk)

        # create thumbnail
        if re.search(r"\.(HEIC|heic)$", self.image_path):
            heif_file = pyheif.read(self.image_path)
            im = Image.frombytes(heif_file.mode, heif_file.size,
                                 heif_file.data, "raw", heif_file.mode,
                                 heif_file.stride)
        else:
            im = Image.open(self.image_path)

        convert_image = {
            1: lambda img: img,
            2: lambda img: img.transpose(Image.FLIP_LEFT_RIGHT),
            3: lambda img: img.transpose(Image.ROTATE_180),
            4: lambda img: img.transpose(Image.FLIP_TOP_BOTTOM),
            5: lambda img: \
            img.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_90),
            6: lambda img: img.transpose(Image.ROTATE_270),
            7: lambda img: \
            img.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.ROTATE_270),
            8: lambda img: img.transpose(Image.ROTATE_90),
        }

        self.load_exit()
        conv = convert_image[self.exif.orientation](im).convert('RGB')
        conv.thumbnail((thumb_width, thumb_height), Image.LANCZOS)
        conv.save(self.thumb_path)

        # write jsonl to list.txt
        with open(listtxt_path(self.username), "a") as f:
            print(json.dumps(self.todict()), file = f)

            


def upload():

    form = cgi.FieldStorage()

    form_file = form["upload-file"]
    form_user = form["upload-user"]

    username = form_user.value.strip()
    cookie = cookies.SimpleCookie()
    cookie["username"] = username

    if not username:
        return "Empty user name is prohibited", cookie

    # user directory check and create
    user_image_dir = os.path.join(image_dir, username)
    user_thumb_dir = os.path.join(thumb_dir, username)
    if not os.path.exists(user_image_dir):
        os.mkdir(user_image_dir)
        os.chmod(user_image_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
    if not os.path.exists(user_thumb_dir):
        os.mkdir(user_thumb_dir)
        os.chmod(user_thumb_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

    if not isinstance(form_file, list):
        form_files = [form_file]
    else:
        form_files = form_file

    uploaded_files = []
    for form in form_files:
        if not form_file.file or not form_file.filename:
            return "File not specified", cookie
        p = Photo(username = username, filename = form.filename)
        p.upload(form.file)
        uploaded_files.append(form.filename)

    return("%s uploaded by %s" % (" ".join(uploaded_files), username), cookie)


def index(message, cookie):

    photos = []

    # retrieve photos from list.txt in username directories
    users = os.listdir(image_dir)

    for username in users:
        listtxt = listtxt_path(username)
        if not os.path.exists(listtxt):
            continue

        with open(listtxt, "r") as f:
            for line in f:
                photos.append(json.loads(line.strip()))

    key = lambda x: x["exif"]["date"] if x["exif"] and x["exif"]["date"] else "0"
    photos.sort(key = key)
    photos.reverse()

    cookie_user = None if not cookie else cookie["username"].value

    html = tpl_index.render({"photos": photos,
                             "num_photos": len(photos),
                             "page_title": page_title,
                             "cookie_user": cookie_user,
                             "message": message})

    out = ""
    if cookie:
        out += cookie.output()

    out += "Content-Type: text/html; charset=utf-8\n"
    out += html

    print(out)



def scan(debug = False):
    """ called via scan.py. create image/{username}/list.txt from images """

    isimg = re.compile(r".*(png|PNG|jpg|JPG|jpeg|JPEG|heic|HEIC)$")

    users = os.listdir(image_dir)

    for username in users:
        user_image_dir = os.path.join(image_dir, username)
        if (not os.path.isdir(user_image_dir) or
            user_image_dir == "." or user_image_dir == ".."):
            continue

        print("scan '{}'".format(user_image_dir), file = sys.stderr)

        user_photos = []

        for filename in os.listdir(user_image_dir):
            if not isimg.match(filename):
                continue
            p = Photo(username = username, filename = filename)
            p.load_exit()
            user_photos.append(p.todict())
            
        if debug:
            print(json.dumps(user_photos, indent = 4))
        else:
            with open(listtxt_path(username), "w") as f:
                for p in user_photos:
                    print(json.dumps(p), file = f)
    

def main():

    cookie = None
    upload_msg = None

    if ("REQUEST_METHOD" in os.environ and
        os.environ["REQUEST_METHOD"] == "POST"):
        upload_msg, cookie = upload()

    if not cookie and "HTTP_COOKIE" in os.environ:
        try:
            cookie = cookies.SimpleCookie()
            cookie.load(os.environ["HTTP_COOKIE"])
        except:
            pass

    sys.exit(index(upload_msg, cookie))



if __name__ == "__main__":
    main()
