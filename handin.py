import socket
import ssl
import pathlib
import argparse
import warnings

# ignore ssl.PROTOCOL_TLS DeprecationWarning
warnings.filterwarnings("ignore", category=DeprecationWarning)

parser = argparse.ArgumentParser(description="Handin client")

parser.add_argument(
    "--list", "-l", action="store_true", help="List active assignments"
)
parser.add_argument(
    "--verbose",
    "-v",
    action="store_true",
    help="Be verbose. Mostly just prints debug information",
)

HOSTNAME = "handin-1.brinckerhoff.org"
PORT = 7979

ROOT_CERTS = pathlib.Path(__file__).parent / "handin-server-cert.pem"


def printf(*args, **kwargs):
    """print and flush"""
    print(*args, **kwargs, flush=True)


# create a socket and wrap it with the SSL context
# connect to the server
class Handin:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def __enter__(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # create an SSL context
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        # load root certificates from a .pem file
        ssl_context.load_verify_locations(cafile=ROOT_CERTS)
        ssl_context.check_hostname = False

        self.ssl_socket = ssl_context.wrap_socket(
            self.socket,
            server_side=False,
            do_handshake_on_connect=True,
            server_hostname=HOSTNAME,
        )
        self.ssl_socket.connect((HOSTNAME, PORT))
        self.handshake()
        return self

    def __exit__(self, _type, _value, _traceback):
        self.ssl_socket.send(b"bye")
        self.ssl_socket.close()

    def log(self, *args, **kwargs):
        if self.verbose:
            printf(*args, **kwargs)

    def write(self, msg):
        msg = (msg + "\n").encode("utf-8")
        self.ssl_socket.send(msg)

    def read(self, len=1024, message=True, max_tries=10240):
        msg = b""
        tries = 0
        # TODO: what if server begins sending another message immediately
        # after i.e. "msg1\nmsg2"
        while not msg.endswith(b"\n"):
            msg += self.ssl_socket.recv(len)
            tries += 1
            if tries == max_tries:
                raise Exception(
                    f"max tries (max_tries) exceeded when attempting to read{' message ' if message else ''}from handshake"
                )
        return msg.decode("utf-8").strip()

    def handshake(self):
        self.log("initiating handshake...")
        self.ssl_socket.send(b"handin\n")
        handin = self.ssl_socket.recv(6)
        assert handin == b"handin", 'server did not echo "handin"'

        self.log("sending protocol information")
        self.ssl_socket.send(b"ver1\n")
        self.log("waiting...", end="")
        self.read(1)
        ver1_res = self.read(4)
        assert ver1_res == "ver1", (
            "server did not recognize protocol. Returned: " + ver1_res
        )
        self.log("handshake completed successfully")

    def get_active_assignments(self):
        self.write("get-active-assignments")
        res = self.read()
        active_assignments = [a.strip('"') for a in res.strip().strip("()").split()]
        return active_assignments


if __name__ == "__main__":
    args = parser.parse_args()
    with Handin(args.verbose) as handin:
        if args.list:
            assignments = handin.get_active_assignments()
            for assignment in assignments:
                print(assignment)
