# -*- coding: utf-8 -*-
"""
Created on Mon Jun  3 12:19:05 2024

@author: -
"""
import json


filepath = 'D:/Dropbox/Documents/Work_ESSL/Code/radar_rendering_tests/data/radar/test.json'

with open(filepath) as f:
    data = json.load(f)
    print(list(data))