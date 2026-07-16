import socket
import socketserver
import threading


LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 5000
TARGET_HOST = "127.0.0.1"
TARGET_PORT = 5001


def pipe(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        for sock in (src, dst):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                sock.close()
            except OSError:
                pass


class ProxyHandler(socketserver.BaseRequestHandler):
    def handle(self):
        with socket.create_connection((TARGET_HOST, TARGET_PORT), timeout=10) as upstream:
            left = threading.Thread(target=pipe, args=(self.request, upstream), daemon=True)
            right = threading.Thread(target=pipe, args=(upstream, self.request), daemon=True)
            left.start()
            right.start()
            left.join()
            right.join()


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with ThreadingTCPServer((LISTEN_HOST, LISTEN_PORT), ProxyHandler) as server:
        print(f"Forwarding {LISTEN_HOST}:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}", flush=True)
        server.serve_forever()
