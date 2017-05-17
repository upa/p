#!/opt/local/Library/Frameworks/Python.framework/Versions/2.7/bin/python
# -*- coding: utf-8 -*-


import os
import cgi
from jinja2 import Environment, FileSystemLoader

from PIL import Image
from PIL.ExifTags import TAGS

page_title = "Photo UpLoader"

image_dir = "image"
thumb_dir = "thumb"

thumb_width = 230
thumb_height = 190


env = Environment(loader = FileSystemLoader("./", encoding = "utf-8"))
tpl_index = env.get_template("template/index.html")


def get_date_of_image_from_exif(image) :

    im = Image.open(image)

    try:
        exif = im._getexif()
    except AttributeError :
        return None

    exif_table = {}
    for tag_id, value in exif.items() :
        tag = TAGS.get(tag_id, tag_id)
        if tag == "DateTimeOriginal" :
            return value

    return None


def index(message) :

    photos = []

    # retrieve thumbnails and images, and generate phtoto lists
    # a photo is
    # { 'image' : image path, 'thumbnail' : thumbnail path,
    #   'caption' : caption string }

    users = os.listdir(image_dir)

    for user in users :

        user_image_dir = os.path.join(image_dir, user)
        user_thumb_dir = os.path.join(thumb_dir, user)

        if not os.path.isdir(user_image_dir) :
            continue

        images = os.listdir(user_image_dir)

        for image in images :
            p = {}
            p["image"] = os.path.join(user_image_dir, image)
            p["thumbnail"] = os.path.join(user_thumb_dir, image)

            p["user"] = user
            p["date"] = get_date_of_image_from_exif(p["image"])
            p["name"] = image
            photos.append(p)


    photos.sort(key = lambda x : x["date"])
    photos.reverse()

    html = tpl_index.render({"photos" : photos,
                             "page_title" : page_title,
                             "message" : message})

    print "Content-Type: text/html; charset=utf-8\n"
    print html


def upload() :

    form = cgi.FieldStorage()

    fm_user = form["upload-user"]
    fm_file = form["upload-file"]

    if fm_user.value is "" :
        return "empty user name is prohibited"

    if not fm_file.file or not fm_file.filename :
        return "file not specified"

    # user directory check
    user_image_dir = os.path.join(image_dir, fm_user.value)
    user_thumb_dir = os.path.join(thumb_dir, fm_user.value)

    if not os.path.exists(user_image_dir) :
        os.mkdir(user_image_dir)
        os.chmod(user_image_dir, 0777)

    if not os.path.exists(user_thumb_dir) :
        os.mkdir(user_thumb_dir)
        os.chmod(user_thumb_dir, 0777)


    # write uploaded file to image directory
    image = os.path.join(image_dir, fm_user.value, fm_file.filename)
    thumb = os.path.join(thumb_dir, fm_user.value, fm_file.filename)

    fo = file(image, "wb")
    while True :
        chunk = fm_file.file.read(1024)
        if not chunk : break
        fo.write(chunk)
    fo.close()


    # create thumbnail
    im = Image.open(image)
    im.thumbnail((thumb_width, thumb_height), Image.ANTIALIAS)
    im.save(thumb)

    return "%s is uploaded by %s" % (fm_file.filename, fm_user.value)


if __name__ == "__main__" :

    upload_ret = None

    if os.environ["REQUEST_METHOD"] == "POST" :
        upload_ret = upload()

    index(upload_ret)
