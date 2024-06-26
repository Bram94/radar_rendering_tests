# -*- coding: utf-8 -*-
"""
Created on Wed Jun 26 15:47:13 2024

@author: bramv
"""

def string_to_list(s, separator=','):
    l = []
    index = s.find(separator)
    while index!=-1:
        l.append(s[:index].strip())
        s = s[index+len(separator):]
        s = s.strip()
        index = s.find(separator)
    l.append(s)
    return l

def get_datalines(data):
    lines = []
    index = data.find('\n')
    while index!=-1:
        lines.append(data[:index])
        data = data[index:].strip()
        index = data.find('\n')
    lines.append(data)
    if lines[-1]=='': lines.pop()
    
    return lines

def list_data(data, separator=','):
    lines = get_datalines(data)
    lines_list = [string_to_list(j, separator) for j in lines]
    return lines_list

def _hex(val):
    h = hex(int(val))[2:]
    return h if len(h) == 2 else '0'+h
def uint(val, vmin, vmax):
    return int(round((val-vmin)/(vmax-vmin)*255))

filepath = 'D:/NLradar/NLradar/Input_files/Color_tables/colortable_Z.csv'
with open(filepath) as f:
    data = [[float(j[0])]+j[1:] for j in list_data(f.read())[1:]]
    vmin, vmax = data[0][0]-1, data[-1][0]
    
    s = ''
    values = []
    for i,j in enumerate(data):
        if len(j) == 7:
            values.append(uint(j[0], vmin, vmax))
            color = '#'+_hex(j[1])+_hex(j[2])+_hex(j[3])+'ff'
            s += "'"+color+"',\n"
            
            values.append(uint(data[i+1][0], vmin, vmax))
            color = '#'+_hex(j[4])+_hex(j[5])+_hex(j[6])+'ff'
            s += "'"+color+"',\n"
    s = s[:-2]
    print(s, values)