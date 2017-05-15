#!/usr/bin/env python
# -*- coding: utf-8 -*-


import cgi
from jinja2 import Environment, FileSystemLoader

env = Environment(loader = FileSystemLoader("./", encoding = "utf-8"))
tpl_index = env.get_template("template/index.html")



def index() :

    html = tpl_index.render()

    print "Content-Type: text/html; charset=utf-8\n"
    print html




if __name__ == "__main__" :
    index()
