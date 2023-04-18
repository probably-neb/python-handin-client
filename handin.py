import socket
import ssl
import pathlib
import argparse
import warnings

# ignore ssl.PROTOCOL_TLS DeprecationWarning
warnings.filterwarnings("ignore", category=DeprecationWarning)

parser = argparse.ArgumentParser(description="Handin client")

parser.add_argument(
    "--verbose",
    "-v",
    action="store_true",
    help="Be verbose. Mostly just prints debug information",
)

# TODO: turn these into subcommands
options = parser.add_mutually_exclusive_group(required=False)

options.add_argument(
    "--list", "-l", action="store_true", help="List active assignments."
)
options.add_argument(
    "--update",
    "-u",
    dest="update_certs",
    action="store_true",
    help="Download server certifications file (.pem file). Note: this file is required for the handin client to work. ",
)

HOSTNAME = "handin-1.brinckerhoff.org"
PORT = 7979

ROOT_CERTS = pathlib.Path(__file__).parent / "server-cert.pem"

# TODO: replace 2234 with {quarter} to allow for future generations
ROOT_CERTS_GH_LINK = "https://raw.githubusercontent.com/jbclements/racket-handin-client/master/2234-csc430-handin/server-cert.pem"


def download_certs():
    import urllib.request

    urllib.request.urlretrieve(ROOT_CERTS_GH_LINK, ROOT_CERTS)


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

    def write(self, msg, append_newline=True):
        if not isinstance(msg, (str, bytes)):
            msg = str(msg)
        if isinstance(msg, str):
            msg = msg.encode("utf-8")
        if append_newline:
            msg += b"\n"
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

    def get_user_info(self, uname, pword):
        msgs = [
            "get-user-fields",
        ]
        for msg in msgs:
            self.write(msg)
        return self.read()

    def ensure_ok(self, src, msg=None, expected="ok"):
        if msg is None:
            msg = self.read()
        assert msg == expected, f"{src} failed! Reason: {msg}"

    def submit(self, uname, pword, asgn, file):
        def wrap_quote(s):
            return '"' + s + '"'

        msgs = [
            "set",
            "username/s",
            wrap_quote(uname),
            "set",
            "password",
            wrap_quote(pword),
            "set",
            "assignment",
            wrap_quote(asgn),
            "save-submission",
        ]
        for s in msgs:
            self.write(s)
        self.ensure_ok("login")
        with open(file, "rb") as submission:
            content = submission.read()
        self.write(len(content))
        self.ensure_ok("upload", expected="go")
        self.write("$", append_newline=False)
        print("printing contents of", asgn, "type:", type(content))
        self.write(content)

        def read_messages():
            match (msg := self.read()):
                case "message":
                    print("message:\n", self.read())
                    read_messages()
                case "message-final":
                    print("message-final:\n", self.read())
                    read_messages()
                case "message-box":
                    print("message-box:\n", self.read(), "\n", self.read())
                    self.write(input("\nresponse:"))
                    read_messages()
                case _:
                    return msg
        self.ensure_ok("submit", msg=read_messages(), expected="confirm")
        self.write("check")
        self.ensure_ok("check", msg=read_messages(), expected="ok")


if __name__ == "__main__":
    args = parser.parse_args()
    if args.update_certs:
        download_certs()
    with Handin(args.verbose) as handin:
        if args.list:
            assignments = handin.get_active_assignments()
            for assignment in assignments:
                print(assignment)
