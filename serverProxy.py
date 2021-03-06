import gevent
from gevent import socket
import json
import struct
import sys

reload(sys).setdefaultencoding('utf-8')

BUF_SIZE = 4096
CONNETC = 1


def _decode_list(data):
    rv = []
    for item in data:
        if hasattr(item, 'encode'):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv


def _decode_dict(data):
    rv = {}
    for key, value in data.items():
        if hasattr(value, 'encode'):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv


class TcpRelay:
    def __init__(self, config):
        self.listen_ip = config['server']
        self.listen_port = config['server_port']
        self.listen_addr = (self.listen_ip, self.listen_port)

    def handle_remote_connection(self, remote_socket, client_socket):
        try:
            while True:
                data = remote_socket.recv(BUF_SIZE)
                if not data:
                    remote_socket.close()
                    return
                else:
                    client_socket.sendall(data)
        except socket.error as error:
            remote_socket.close()
            print error
            return

    def handle_client_connection(self, client_socket, remote_socket):
        try:
            while True:
                data = client_socket.recv(BUF_SIZE)
                if not data:
                    client_socket.close()
                    return
                else:
                    remote_socket.sendall(data)
        except socket.error as error:
            client_socket.close()
            print error
            return

    def handle_connection(self, client_socket):
        try:
            data = client_socket.recv(1024)
            addrtype = ord(data[0])
            if addrtype == 1:
                remote_ip = socket.inet_ntoa(data[1:5])
                remote_port = struct.unpack('>H', data[5:7])[0]
                remote_addr = (remote_ip, remote_port)
            elif addrtype == 3:
                domain_length = ord(data[1])
                remote_domain = data[2:2+domain_length]
                remote_port = struct.unpack(
                    '>H', data[2+domain_length:4+domain_length])[0]
                remote_addr = (remote_domain, remote_port)
            remote_socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM, socket.SOL_TCP)
            remote_socket.connect(remote_addr)
            gevent.spawn(self.handle_client_connection, client_socket,
                         remote_socket)
            gevent.spawn(self.handle_remote_connection, remote_socket,
                         client_socket)
        except socket.error as error:
            print error
            return

    def get_connection(self, listen_socket):
        while True:
            client_socket, client_addr = listen_socket.accept()
            print 'accept: ', client_addr
            gevent.spawn(self.handle_connection, client_socket)

    def run(self):
        addrs = socket.getaddrinfo(self.listen_ip, self.listen_port, 0,
                                   socket.SOCK_STREAM, socket.SOL_TCP)
        af, socktype, proto, canonname, sa = addrs[0]
        listen_socket = socket.socket(af, socktype, proto)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        listen_socket.bind(sa)
        listen_socket.listen(1024)
        gevent.joinall([gevent.spawn(self.get_connection, listen_socket)])


def main():
    with open('./serverconfig.json', 'r') as f:
        config = json.load(f, object_hook=_decode_dict)
        tcp_relay = TcpRelay(config)
        tcp_relay.run()

if __name__ == '__main__':
    main()
