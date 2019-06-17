#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import stat
import datetime
import cgi

from jinja2 import Environment, FileSystemLoader

from logging import getLogger, DEBUG, StreamHandler, Formatter
from logging.handlers import SysLogHandler

logger = getLogger(__name__)
logger.setLevel(DEBUG)
stream = StreamHandler()
syslog = SysLogHandler(address = "/dev/log")
syslog.setFormatter(Formatter("p: %(message)s"))
logger.addHandler(stream)
logger.addHandler(syslog)
logger.propagate = False


import zipfile
import datetime
import http

from PIL import Image
from PIL.ExifTags import TAGS
import sys


import pconfig # configuration of p
page_title = pconfig.page_title
image_dir = pconfig.image_dir
thumb_dir = pconfig.thumb_dir

thumb_width = 460
thumb_height = 380


env = Environment(loader = FileSystemLoader("./", encoding = "utf-8"))
tpl_index = env.get_template("template/index.html")

cookie_user = None


def get_exif_data(image) :
    # this returns date, model and orientation

    exif_data = {
        "date" : None,
        "model" : None,
        "orientation" : 1,
        "error" : None,
    }


    try :
        im = Image.open(image)
    except IOError :
        exif_data["error"] = "'I/O Error'"
        return exif_data

    try:
        exif = im._getexif()
    except AttributeError :
        exif_data["error"] = "Exif Attribute Error"
        return exif_data

    if not exif :
        exif_data["error"] = "No Exif Data"
        return exif_data


    for tag_id, value in exif.items() :
        tag = TAGS.get(tag_id, tag_id)

        if tag == "DateTimeOriginal" :
            # YYYY:MM:DD to YYYY/MM/DD
            exif_data["date"] = value.replace(":", "/", 2)

        elif tag == "DateTime" and not exif_data["date"] :
            exif_data["date"] = value.replace(":", "/", 2)

        elif tag == "DateTimeDigitized" and not exif_data["date"] :
            exif_data["date"] = value.replace(":", "/", 2)

        elif tag == "Model" :
            exif_data["model"] = value

        elif tag == "Orientation" :
            exif_data["orientation"] = value
    
    return exif_data

def get_create_time(image) :

    try :
        ctime = os.path.getctime(image)
    except :
        return None
    return datetime.date.fromtimestamp(ctime).strftime("%Y/%m/%d uploaded")


def index(message) :

    photos = []

    # retrieve thumbnails and images, and generate phtoto lists

    users = os.listdir(image_dir)
    filter_users = []

    # get filtered user if specified through filter-form
    form = cgi.FieldStorage()
    if "filter-user" in form and form["filter-user"].value != "_all_" :
        filter_user = form["filter-user"].value
    else :
        filter_user = None

    for user in users :

        user_image_dir = os.path.join(image_dir, user)
        user_thumb_dir = os.path.join(thumb_dir, user)

        if not os.path.isdir(user_image_dir) :
            continue

        filter_users.append(user)

        if filter_user and filter_user != user :
            continue

        images = os.listdir(user_image_dir)

        for image in images :

            p = {}
            p["image"] = os.path.join(user_image_dir, image)
            p["thumbnail"] = os.path.join(user_thumb_dir, image)

            p["user"] = user
            p["name"] = image.replace("-", "<wbr>-").replace("_", "<wbr>_")

            exif_data = get_exif_data(p["image"])
            p["date"] = exif_data["date"]
            p["model"] = exif_data["model"]
            p["error"] = exif_data["error"]
            if not p["date"] :
                p["date"] = get_create_time(p["image"])
            photos.append(p)


    filter_users.sort(key = str.lower)
    photos.sort(key = lambda x : x["date"] if x["date"] else "0")
    photos.reverse()

    if cookie_user :
        expire = datetime.datetime.today() + datetime.timedelta(days = 365)
        e = expire.strftime("%a, %d-%b-%Y 00:00:00 GMT")
        c = "Set-Cookie: username=%s; expires=%s;" % (cookie_user, e)
    else :
        c = None

    html = tpl_index.render({"photos" : photos,
                             "num_photos" : len(photos),
                             "page_title" : page_title,
                             "cookie" : c,
                             "cookie_user" : cookie_user,
                             "filter_user" : filter_user,
                             "filter_users" : filter_users,
                             "message" : message})

    print("Content-Type: text/html; charset=utf-8\n")
    sys.stdout.write(html)


def handle_zip(fm_file, fm_user) :

    # copy and unzip the zip file at /tmp
    zip = os.path.join("/tmp", fm_file.filename)

    fo = open(zip, "wb")
    while True :
        chunk = fm_file.file.read(65536)
        if not chunk: break
        fo.write(chunk)
    fo.close()

    # copy photo files from zip archive to image directory
    uploaded_files = []
    with zipfile.ZipFile(zip, 'r') as z:
        
        for filepath in z.namelist() :

            if re.search(r'\.(png|PNG|jpg|JPG)', filepath) :
                filename = filepath.split('/').pop()
                if filename[0] == "." : continue

            else :
                continue

            with z.open(filepath) as f :
                image = os.path.join(image_dir, fm_user.value, filename)
                thumb = os.path.join(thumb_dir, fm_user.value, filename)
                create_image_and_thumb(f, image, thumb)

                uploaded_files.append(filename)

    os.remove(zip)

    return uploaded_files


def upload() :

    form = cgi.FieldStorage()

    fm_user = form["upload-user"]
    fm_file = form["upload-file"]

    fm_user.value = fm_user.value.strip()

    if fm_user.value is "" :
        return "empty user name is prohibited"

    if (not isinstance(fm_file, list) and
        (not fm_file.file or not fm_file.filename)) :
        return "file not specified"

    # user directory check
    user_image_dir = os.path.join(image_dir, fm_user.value)
    user_thumb_dir = os.path.join(thumb_dir, fm_user.value)

    if not os.path.exists(user_image_dir) :
        os.mkdir(user_image_dir)
        os.chmod(user_image_dir, stat.S_IRWXU | stat.SIRWXG | stat.S_IRWXO)
    if not os.path.exists(user_thumb_dir) :
        os.mkdir(user_thumb_dir)
        os.chmod(user_thumb_dir, stat.S_IRWXU | stat.SIRWXG | stat.S_IRWXO)


    # set cookie
    global cookie_user
    cookie_user = fm_user.value

    if not isinstance(fm_file, list):
        fm_files = [fm_file]
    else :
        fm_files = fm_file

    logger.info("fm_files: %s" % fm_files)

    uploaded_files = []

    for fm in fm_files :

        if re.search(r'\.zip$', fm.filename) :
            uploaded_files += handle_zip(fm, fm_user)
        
        else :
            # write uploaded file to image directory
            image = os.path.join(image_dir, fm_user.value, fm.filename)
            thumb = os.path.join(thumb_dir, fm_user.value, fm.filename)
            create_image_and_thumb(fm.file, image, thumb)
            uploaded_files.append(fm.filename)

    return "%s uploaded by %s" % (" ".join(uploaded_files), fm_user.value)


def create_image_and_thumb(f_in, image, thumb) :
    
    fo = open(image, "wb")
    while True :
        chunk = f_in.read(65536)
        if not chunk : break
        fo.write(chunk)
    fo.close()

    # create thumbnail

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

    exif_data = get_exif_data(image)
    orientation = exif_data["orientation"]

    im = Image.open(image)
    conv = convert_image[orientation](im)
    conv.thumbnail((thumb_width, thumb_height), Image.ANTIALIAS)
    conv.save(thumb)

    return


if __name__ == "__main__" :

    upload_ret = None

    try :
        if os.environ["REQUEST_METHOD"] == "POST" :
            upload_ret = upload()
    except :
        pass

    if "HTTP_COOKIE" in os.environ :
        try:
            cookie = http.cookies.SimpleCookie()
            cookie.load(os.environ["HTTP_COOKIE"])
            if cookie["username"].value :
                cookie_user = cookie["username"].value
        except:
            pass

    index(upload_ret)
