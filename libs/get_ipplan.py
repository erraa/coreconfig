#!/usr/bin/env

# Requires lzma and requests that's not from python-core

import sys
import requests
import lzma
import os
from requests.auth import HTTPBasicAuth

# Just doin' this for testing
#requests.packages.urllib3.disable_warnings()

class Ipplan:
    def __init__(self, url, ipplan_user, ipplan_password):
        self.url = url
        self.user = ipplan_user
        self.password = ipplan_password

    def get_ipplan(self):
        """ We download ipplan in db format to the current directory"""
        self.local_filename = self.url.split('/')[-1]

        rp = requests.get(
                self.url, 
                auth=HTTPBasicAuth(self.user, self.password), 
                verify=False
                )

        data = []

        with open(self.local_filename, 'wb') as f:
            for chunk in rp.iter_content(chunk_size=1024): 
                if chunk: # filter out keep-alive new chunks
                    data.append(chunk)

        return ''.join(data)

    def unpack_ipplan(self):
        ipplan = self.get_ipplan()
        return lzma.decompress(ipplan)

    def to_file(self):
        """ Creates the ipplan file in your current directory """
        with open('ipplan.db', 'wb+') as f:
            f.write(self.unpack_ipplan())

        return 'ipplan.db'
    
    def cleanup(self):
        os.remove(self.local_filename)

def __main__():
    url = 'https://doc.tech.dreamhack.se/stuff/ipplan.db.xz'
    ipplan_user = sys.argv[1]
    ipplan_password = sys.argv[2]
    p = Ipplan( 
            url, 
            ipplan_user, 
            ipplan_password
            )
    unzip = p.to_file()
    p.cleanup()

if __name__ == "__main__":
    __main__()
