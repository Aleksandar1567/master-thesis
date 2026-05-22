from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import json

UPLOAD_DIR = "upload"
PORT = 8000

class FingerprintHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_type = self.headers.get('Content-Type')
        if content_type != 'application/octet-stream':
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Content-Type not supported\n')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        template_id = self.headers.get('X-Template-ID', 'unknown')

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, f'{template_id}.bin')
        with open(file_path, 'wb') as f:
            f.write(post_data)

        self.send_response(200)
        self.end_headers()
        # self.wfile.write(b'Fingerprint template saved as .bin\n')

    def do_GET(self):
        if self.path == "/upload/list":
            try:
                files = os.listdir(UPLOAD_DIR)
                bin_files = [f for f in files if f.endswith(".bin")]
                response = json.dumps(bin_files)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(response.encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Server error: {str(e)}".encode('utf-8'))
            return

        if self.path.startswith("/upload/"):
            filename = os.path.basename(self.path)
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_path):
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'File not found\n')

def run():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, FingerprintHandler)
    print(f"Serving on port {PORT}")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
