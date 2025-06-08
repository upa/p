from http.server import HTTPServer, CGIHTTPRequestHandler

class MyCGIHandler(CGIHTTPRequestHandler):
    cgi_directories = ['/'] 

if __name__ == '__main__':
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, MyCGIHandler)
    print("Serving on http://localhost:8000/")
    httpd.serve_forever()
