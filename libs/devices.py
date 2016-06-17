#!/usr/bin/env python

class Switches(object):
    def __init__(self, name):
        self.hall = None
        self.name = name
        self.rows = []
        self.bundle = None

    def set_hall(self, hall):
        self.hall = hall

    def set_rows(self, rows):
        self.rows = rows

    def set_bundle(self, bundle):
        self.bundle = bundle
        
