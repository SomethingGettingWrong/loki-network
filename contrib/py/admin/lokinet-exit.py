#!/usr/bin/env python3
import argparse
import sys

from socket import AF_INET

import requests
from pyroute2 import IPRoute

class LokinetRPC:

    def __init__(self, url):
        self._url = url
    
    def _jsonrpc(self, method, params={}):
        r = requests.post(
            self._url,
            headers={"Content-Type": "application/json", "Host": "localhost"},
            json={
                "jsonrpc": "2.0",
                "id": "0",
                "method": "{}".format(method),
                "params": params,
            },
        )
        return r.json()
        
    def get_first_hops(self):
        data = self._jsonrpc("llarp.admin.dumpstate")
        for link in data['result']['links']['outbound']:
            for session in link["sessions"]['established']:
                yield session['remoteAddr']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpc", type=str, default='127.0.0.1:1190')
    ap.add_argument("--ifname", type=str, default="lokitun0")
    ap.add_argument("--up", action='store_const', dest='action', const='up')
    ap.add_argument("--down", action='store_const', dest='action', const='down')
    args = ap.parse_args()
    rpc = LokinetRPC('http://{}/jsonrpc'.format(args.rpc))
    hops = dict()
    for hop in rpc.get_first_hops():
        ip = hop.split(':')[0]
        hops[ip] = 0

    with IPRoute() as ip:
        ip.bind()
        idx = ip.link_lookup(ifname=args.ifname)[0]
        gateways = ip.get_default_routes(family=AF_INET)
        gateway = None
        for g in gateways:
            useThisGateway = True
            for name, val in g['attrs']:
                if name == 'RTA_OIF' and val == idx:
                    useThisGateway = False
            if not useThisGateway:
                continue
            for name, val in g['attrs']:
                if name == 'RTA_GATEWAY':
                    gateway = val
        if gateway:
            for address in hops:
                try:
                    if args.action == 'up':
                        ip.route("add", dst="{}/32".format(address), gateway=gateway)
                    elif args.action == 'down':
                        ip.route("del", dst="{}/32".format(address), gateway=gateway)
                except:
                    pass
            if args.action == 'up':
                ip.route('add', dst='0.0.0.0/0', oif=idx)
            elif args.action == 'down':
                ip.route('del', dst='0.0.0.0/0', oif=idx)
                
                
if __name__ == '__main__':
    main()
