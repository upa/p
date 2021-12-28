#!/usr/bin/env python3

from http.server import HTTPServer, CGIHTTPRequestHandler

class Handler(CGIHTTPRequestHandler):
    cgi_directories = ["/"]

PORT = 8000
httpd = HTTPServer(("", PORT), Handler)
httpd.serve_forever()
