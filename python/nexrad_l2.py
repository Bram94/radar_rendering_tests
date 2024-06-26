# Copyright (C) 2016-2024 Bram van 't Veen, bramvtveen94@hotmail.com
# This is a substantially modified version of https://github.com/ARM-DOE/pyart/blob/main/pyart/io/nexrad_level2.py


# This file is part of the Py-ART, the Python ARM Radar Toolkit
# https://github.com/ARM-DOE/pyart

# Care has been taken to keep this file free from extraneous dependancies
# so that it can be used by other projects with no/minimal modification.

# Please feel free to use this file in other project provided the license
# below is followed. Keeping the above comment lines would also be helpful
# to direct other back to the Py-ART project and the source of this file.


LICENSE = """
Copyright (c) 2013, UChicago Argonne, LLC
All rights reserved.

Copyright 2013 UChicago Argonne, LLC. This software was produced under U.S.
Government contract DE-AC02-06CH11357 for Argonne National Laboratory (ANL),
which is operated by UChicago Argonne, LLC for the U.S. Department of Energy.
The U.S. Government has rights to use, reproduce, and distribute this
software. NEITHER THE GOVERNMENT NOR UCHICAGO ARGONNE, LLC MAKES ANY
WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY FOR THE USE OF THIS
SOFTWARE. If software is modified to produce derivative works, such modified
software should be clearly marked, so as not to confuse it with the version
available from ANL.

Additionally, redistribution and use in source and binary forms, with or
without modification, are permitted provided that the following conditions
are met:

    * Redistributions of source code must retain the above copyright
      notice, this list of conditions and the following disclaimer.

    * Redistributions in binary form must reproduce the above copyright
      notice, this list of conditions and the following disclaimer in the
      documentation and/or other materials provided with the distribution.

    * Neither the name of UChicago Argonne, LLC, Argonne National
      Laboratory, ANL, the U.S. Government, nor the names of its
      contributors may be used to endorse or promote products derived
      from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY UCHICAGO ARGONNE, LLC AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL UCHICAGO ARGONNE, LLC OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import bz2
import gzip
import re
import struct
import warnings
from datetime import datetime, timedelta
import os
import copy
import time as pytime

import numpy as np


class NEXRADLevel2File:
    """
    Class for accessing data in a NEXRAD (WSR-88D) Level II file.

    NEXRAD Level II files [1]_, also know as NEXRAD Archive Level II or
    WSR-88D Archive level 2, are available from the NOAA National Climate Data
    Center [2]_ as well as on the UCAR THREDDS Data Server [3]_. Files with
    uncompressed messages and compressed messages are supported. This class
    supports reading both "message 31" and "message 1" type files.

    Parameters
    ----------
    filename : str
        Filename of Archive II file to read.

    Attributes
    ----------
    radial_records : list
        Radial (1 or 31) messages in the file.
    nscans : int
        Number of scans in the file.
    scan_msgs : list of arrays
        Each element specifies the indices of the message in the
        radial_records attribute which belong to a given scan.
    volume_header : dict
        Volume header.
    vcp : dict
        VCP information dictionary.
    _records : list
        A list of all records (message) in the file.
    _fh : file-like
        File like object from which data is read.
    _msg_type : '31' or '1':
        Type of radial messages in file.

    References
    ----------
    .. [1] http://www.roc.noaa.gov/WSR88D/Level_II/Level2Info.aspx
    .. [2] http://www.ncdc.noaa.gov/
    .. [3] http://thredds.ucar.edu/thredds/catalog.html

    """

    def __init__(self, filename, read_mode="all", moments=None):
        return self.decode_file(filename, read_mode, moments)
        
    def __call__(self, startend_pos, moments=None):
        # For repeated access to files, after initialisation
        return self.decode_file(self._fh, startend_pos, moments)
        
    def decode_file(self, file_name_or_obj, read_mode="all", moments=None):
        """
        - read_mode can be one of "all", "all-meta", "min-meta" or a list with sublists of start and end positions
        of parts of the file that should be read
        - moments specifies which moments should be obtained. If not specified, all moments will be obtained. 
        Can be either a single string or a list of strings.
        """
        self._decode_meta = type(read_mode) == str and read_mode.endswith('meta')
        self._read_mode = read_mode
        self._moments = moments
        
        """initalize the object."""
        if hasattr(file_name_or_obj, "read"):
            # Passing a file handle should only be done after initialisation with a filename.
            # It is meant for repeated access to a file, of which the content then won't be decompressed more than once.
            self._fh = file_name_or_obj
            if self._fh.closed:
                if self._bzip2_compression:
                    self._fh = open(self._fh.name, "rb")
                else:
                    # If a gzipped file is closed it must be fully decompressed again. So in this case there is no
                    # benefit of passing a file handle, and an exception is raised. This is not the case for
                    # bzip2-compressed files, which consist of separate compressed blocks that can be handled independently. 
                    raise Exception('Gzipped files should not be closed when using this option')
        else:
            if file_name_or_obj.endswith('.gz'):
                self._fh = gzip.open(file_name_or_obj,'rb')
            else:
                self._fh = open(file_name_or_obj, "rb")
            
            # read in the volume header and compression_record
            size = _structure_size['VOLUME_HEADER']
            self.volume_header = _unpack_structure(self._fh.read(size), 'VOLUME_HEADER')
            compression_record = self._fh.read(COMPRESSION_RECORD_SIZE)
    
            # read the records in the file, decompressing as needed
            compression_slice = slice(CONTROL_WORD_SIZE, CONTROL_WORD_SIZE + 2)
            compression_or_ctm_info = compression_record[compression_slice]
            self._bzip2_compression = compression_or_ctm_info == b"BZ"
            
            self._buf = {} if self._bzip2_compression else b''

            
        if self._decode_meta:
            # For read_mode = 'min-meta' it is attempted to decode only the minimum amount of data needed to capture all
            # relevant meta-data
            if self._bzip2_compression:
                # Make sure that for bzip2 compression also the 1st compressed message gets included below
                self._fh.seek(0)
                self._cbuf = self._fh.read()
                self._bzip2_start_pos = _get_bzip2_start_indices(self._cbuf)
                diffs = np.diff(np.array(self._bzip2_start_pos+[len(self._cbuf)]))
                # Sometimes very small messages are included that clearly contain no data, and that can screw up the
                # 'min-meta' check down below. These are removed here
                self._bzip2_start_pos = [j for i,j in enumerate(self._bzip2_start_pos) if diffs[i] > 1000]
                
                bzip2_read_indices = 'all'
                if read_mode == 'min-meta':
                    buf = _decompress_records_meta(self._cbuf, self._bzip2_start_pos, [0])
                    self._read_records(buf)
                    self._get_vcp()
                    cut_params = self.vcp.get('cut_parameters', [])
                    if self.vcp:
                        bzip2_read_indices = [0]
                        expected_last_bzip2_index = 0
                        for scan in cut_params:
                            expected_last_bzip2_index += 3+3*(scan['super_resolution'] in (11, 7))
                            if expected_last_bzip2_index < len(self._bzip2_start_pos):
                                # With AVSET the volume can end before reaching the last scan in the VCP
                                bzip2_read_indices.append(expected_last_bzip2_index)
                    else:
                        # Is the case for TDWR data
                        bzip2_read_indices = list(range(2, len(self._bzip2_start_pos), 3))
                    if bzip2_read_indices[-1]+1 != len(self._bzip2_start_pos):
                        bzip2_read_indices.append(len(self._bzip2_start_pos)-1)
                        print('add len(self._bzip2_start_pos)-1')
                        # # Means that either self.vcp is empty or that the number of BZ2 messages differs from 
                        # # what is expected based on the number of scans and whether they are super-res
                        # print('reopen', bzip2_read_indices, len(self._bzip2_start_pos))
                        # self.decode_file(self._fh, read_mode='all-meta')
                        # return
                buf = _decompress_records_meta(self._cbuf, self._bzip2_start_pos, bzip2_read_indices)
                self._bzip2_read_indices = list(range(len(self._bzip2_start_pos))) if bzip2_read_indices == 'all' else\
                                           bzip2_read_indices
            else:
                buf = self._read_gzip()
                if read_mode == 'min-meta':
                    self.indices = []
                    i = 0
                    while i < len(buf):
                        header = _unpack_from_buf(buf, i, 'MSG_HEADER')
                        msg_size, msg_type = header['size'], header['type']
                        if msg_type == 31:
                            self.indices.append(i)
                            size = msg_size*2-4+_structure_size['MSG_HEADER']
                        elif msg_type == 29:
                            if msg_size == 65535:
                                msg_size = header['segments'] << 16 | header['seg_num']
                            size = msg_size+_structure_size['MSG_HEADER']
                        else:
                            if msg_type == 1:
                                self.indices.append(i)
                            size = RECORD_SIZE
                        i += size
                        
                    n = len(self.indices)
                    gzip_indices_step = 30
                    indices_select = list(range(0, n, gzip_indices_step))
                    buf = [buf[:self.indices[0]]]+\
                          [buf[slice(self.indices[i], self.indices[i+1] if i+1 < n else None)] for i in indices_select]
                    
        elif read_mode == 'all':
            buf = self._read_bzip2() if self._bzip2_compression else self._read_gzip()
        elif isinstance(read_mode, list):
            if not isinstance(read_mode[0], list):
                read_mode = [read_mode]
            # First sort the indices, to make sure that no issues occur with reaching end-of-file marker halfway through reading the desired scans.
            # This has no effect on handling the resulting data, since scans will be sorted in self.scan_msgs anyway here below.
            read_mode = sorted(read_mode)             
            buf = b""
            for startend_pos in read_mode:
                buf += self._read_bzip2(startend_pos) if self._bzip2_compression else self._read_gzip(startend_pos)
        
        self._read_records(buf)

        # pull out radial records (1 or 31) which contain the moment data.
        self.radial_records = []
        radial_records_start_pos = []
        
        msg_types = [r["header"]["type"] for r in self._records]
        msg_types_counts = {j:msg_types.count(j) for j in (1,31)}
        # It has been observed in at least 1 erroneous file that both MSG1 and MSG31 formats are present. In that case include only those 
        # of the type that is present most.
        self._msg_type = max(msg_types_counts, key=msg_types_counts.get)
        for i, r in enumerate(self._records):
            if r["header"]["type"] == self._msg_type:
                self.radial_records.append(r)
                if self._decode_meta and self._bzip2_compression:
                    radial_records_start_pos.append(self._bzip2_read_indices[i])
                else:
                    radial_records_start_pos.append(self._records_start_pos[i])
                
        if len(self.radial_records) == 0:
            raise ValueError("No MSG31 records found, cannot read file")
            
        elev_nums = np.array(
            [m["msg_header"]["elevation_number"] for m in self.radial_records]
        )
        self.scan_msgs = [
            np.where(elev_nums == i)[0] for i in range(elev_nums.min(), elev_nums.max()+1)
        ]
               
        azi_numbers = [j['msg_header']['azimuth_number'] for j in self.radial_records]
        wrong_indices_step = read_mode == 'min-meta' and not self._bzip2_compression and\
                             any(azi_i-azi_numbers[i-1] > 0 and azi_i-azi_numbers[i-1] != gzip_indices_step for i,azi_i in enumerate(azi_numbers))
        # For 'min-meta' a few additional checks are needed to ensure that the desired metadata has been obtained correctly.
        # min(msg_types_counts.values()) > 0 checks whether both MSG1 and MSG31 formats are present
        if read_mode == 'min-meta' and (min(msg_types_counts.values()) > 0 or wrong_indices_step or
        (self._bzip2_compression and (any(len(j) != 1 for j in self.scan_msgs) or
        any(any(i.get('ngates', -1) == 0 for i in self.radial_records[j[0]].values()) for j in self.scan_msgs)))):
            # In this mode it is expected that for each scan only 1 message gets included
            print('reopen')
            self.decode_file(self._fh, read_mode='all-meta')
            return
                
        # It has been observed that some elevations are not present, they are then removed here. This should be done after
        # the 'min-meta' check above
        self.scan_msgs = [j for j in self.scan_msgs if len(j)]
            
        self.nscans = len(self.scan_msgs)
        if self._decode_meta:
            scan_msgs = copy.deepcopy(self.scan_msgs)
            # It has been observed in erroneous files that 2 volumes are 'concatenated', i.e. the second correct volume
            # is concatenated to the first unfinished/incorrect volume. This can mean that certain elevation numbers occur at 2
            # places in the file (from both volumes), with in between those places different scans (elevation numbers). This leads
            # to errors, so here it is decided to include only the last volume. This is realised by checking whether indices in
            # msgs increase in steps of 1. If not, then keep only the last part with indices that do.
            for i, msgs in enumerate(scan_msgs):
                msgs = [msgs[-1]]+[j for i,j in enumerate(msgs[:-1][::-1]) if np.all(np.diff(msgs[-(i+2):]) == 1.)]
                if len(msgs) != len(scan_msgs[i]):
                    print('removing scan msgs')
                scan_msgs[i] = msgs[::-1]
            
            self.scan_startend_pos = []
            for i in range(len(scan_msgs)):
                idx_m1, idx, idx_p1 = [scan_msgs[j if 0 <= j < len(scan_msgs) else i][0] for j in (i-1, i, i+1)]
                pos_m1, pos, pos_p1 = [radial_records_start_pos[j] for j in (idx_m1, idx, idx_p1)]
                if self._bzip2_compression:
                    if read_mode == 'min-meta':
                        start_pos = self._bzip2_start_pos[pos_m1+1] if idx != idx_m1 else self._bzip2_start_pos[1]
                        end_pos = self._bzip2_start_pos[pos+1] if idx != idx_p1 else None
                    else:
                        start_pos = self._bzip2_start_pos[pos]
                        end_pos = self._bzip2_start_pos[pos_p1] if idx != idx_p1 else None
                else:
                    if read_mode == 'min-meta':
                        azi_num = self.radial_records[idx]['msg_header']['azimuth_number']
                        # Use maximum, since in incomplete files it can happen that the first azimuth number for the scan isn't 1
                        start_pos = self.indices[max(0, indices_select[idx]-azi_num+1)]
                        azi_num = self.radial_records[idx_p1]['msg_header']['azimuth_number']
                        end_pos = self.indices[indices_select[idx_p1]-azi_num+1] if idx != idx_p1 else None
                    else:
                        start_pos = pos
                        end_pos = pos_p1 if idx != idx_p1 else None
                self.scan_startend_pos.append([start_pos, end_pos])
            # print(self.scan_startend_pos, len(self.scan_startend_pos))
                
        if not hasattr(self, 'vcp'):
            self._get_vcp()


    def _read_bzip2(self, startend_pos=[0, None]):
        """Reads (parts of) a bzip2 compressed file, and stores the decompressed data in self._buf. 
        This is done in order to prevent repeated decompression."""
        key = str(startend_pos)
        if not key in self._buf:
            self._fh.seek(startend_pos[0])
            if startend_pos[1] is None:
                buf = self._fh.read()
            else:
                buf = self._fh.read(startend_pos[1]-startend_pos[0])
            self._buf[key] = _decompress_records(buf)
        return self._buf[key]

    def _read_gzip(self, startend_pos=None):
        """Reads (parts of) a gzipped file, and stores the decompressed data in self._buf. 
        This is done in order to prevent repeated decompression."""
        if startend_pos:
            l = len(self._buf)
            if not startend_pos[1]:
                self._buf += self._fh.read()
            elif l < startend_pos[1]:
                self._buf += self._fh.read(startend_pos[1]-l)
            return self._buf[startend_pos[0]:startend_pos[1]]
        else:
            self._buf += self._fh.read()
            return self._buf
        
    def _read_records(self, buf):
        self._records = []
        self._records_start_pos = []
        # read the records from the buffer
        if not isinstance(buf, list):
            buf = [buf]
        for i,b in enumerate(buf):
            buf_length = len(b)
            if buf_length == 0:
                # This could happen in an erroneous file, see e.g. function _decompress_records_meta. Still add an "empty" record, 
                # since otherwise matching records with self._bzip2_read_indices gets screwed up.
                self._records.append({'header':{'type':0}})
                self._records_start_pos.append(-1)
                continue
            pos = COMPRESSION_RECORD_SIZE if self._bzip2_compression else 0
            while pos < buf_length:
                self._records_start_pos.append(pos)
                pos, dic = _get_record_from_buf(b, pos, self._moments)
                if self._bzip2_compression and self._decode_meta and i > 0 and not 'RAD' in dic:
                    b = _decompress_records_meta(self._cbuf, self._bzip2_start_pos, bzip2_read_indices=[i], max_length=10000)[0]
                    buf_length = len(b)
                    pos = COMPRESSION_RECORD_SIZE
                    while pos < buf_length:
                        pos, dic = _get_record_from_buf(b, pos, self._moments)
                        if 'RAD' in dic:
                            break
                elif self._bzip2_compression and self._decode_meta and i == 0 and not dic["header"]["type"] in (1, 31, 5):
                    # Normally the first BZ2 block contains VCP pattern information, in which case only that record 
                    # is stored. But sometimes VCP information is missing, in which case the first block contains 
                    # normal scan data, of which the first record is needed for scan metadata
                    continue
                self._records.append(dic)
                if self._bzip2_compression and self._decode_meta:
                    # Only one record per BZ2 block is needed for metadata
                    break
                
    def _get_vcp(self):
        # pull out the vcp record
        msg_5 = [r for r in self._records if r["header"]["type"] == 5]
        if len(msg_5):
            self.vcp = msg_5[0]
        else:
            # There is no VCP Data.. This is uber dodgy
            if type(self._read_mode) == str:
                # Only emit this warning when VCP information is actually expected, which is not the case when self._read_mode is a list
                warnings.warn(
                    "No MSG5 detected. Setting to meaningless data. "
                    "Rethink your life choices and be ready for errors."
                    "Specifically fixed angle data will be missing"
                )
            self.vcp = {}
            
        

    def close(self):
        """Close the file."""
        self._fh.close()

    def location(self):
        """
        Find the location of the radar.

        Returns all zeros if location is not available.

        Returns
        -------
        latitude : float
            Latitude of the radar in degrees.
        longitude : float
            Longitude of the radar in degrees.
        height : int
            Height of radar and feedhorn in meters above mean sea level.

        """
        if self._msg_type == 31:
            dic = self.radial_records[0]["VOL"]
            height = dic["height"] + dic["feedhorn_height"]
            return dic["lat"], dic["lon"], height
        else:
            return 0.0, 0.0, 0.0

    def scan_info(self, scans=None):
        """
        Return a list of dictionaries with scan information.

        Parameters
        ----------
        scans : list ot None
            Scans (0 based) for which ray (radial) azimuth angles will be
            retrieved.  None (the default) will return the angles for all
            scans in the volume.

        Returns
        -------
        scan_info : list, optional
            A list of the scan performed with a dictionary with keys
            'moments', 'ngates', 'nrays', 'first_gate' and 'gate_spacing'
            for each scan.  The 'moments', 'ngates', 'first_gate', and
            'gate_spacing' keys are lists of the NEXRAD moments and gate
            information for that moment collected during the specific scan.
            The 'nrays' key provides the number of radials collected in the
            given scan.

        """
        info = []

        if scans is None:
            scans = range(self.nscans)
        for scan in scans:
            # nrays = self.get_nrays(scan)
            # if nrays < 2:
            #     self.nscans -= 1
            #     continue
            msg31_number = self.scan_msgs[scan][0]
            msg = self.radial_records[msg31_number]
            nexrad_moments = ["REF", "VEL", "SW", "ZDR", "PHI", "RHO", "CFP"]
            moments = [f for f in nexrad_moments if f in msg]
            ngates = [msg[f]["ngates"] for f in moments]
            gate_spacing = [msg[f]["gate_spacing"] for f in moments]
            first_gate = [msg[f]["first_gate"] for f in moments]
            info.append(
                {
                    # "nrays": nrays,
                    "ngates": ngates,
                    "gate_spacing": gate_spacing,
                    "first_gate": first_gate,
                    "moments": moments,
                }
            )
        return info

    def get_vcp_pattern(self):
        """
        Return the numerical volume coverage pattern (VCP) or None if unknown.
        """
        if not self.vcp:
            return None
        else:
            return self.vcp["msg5_header"]["pattern_number"]

    # helper functions for looping over scans
    def _msg_nums(self, scans):
        """Find the all message number for a list of scans."""
        return np.concatenate([self.scan_msgs[i] for i in scans])

    def _radial_array(self, scans, key):
        """
        Return an array of radial header elements for all rays in scans.
        """
        msg_nums = self._msg_nums(scans)
        temp = [self.radial_records[i]["msg_header"][key] for i in msg_nums]
        return np.array(temp)

    def _radial_sub_array(self, scans, key):
        """
        Return an array of RAD or msg_header elements for all rays in scans.
        """
        msg_nums = self._msg_nums(scans)
        if self._msg_type == 31:
            tmp = [self.radial_records[i]["RAD"][key] for i in msg_nums]
        else:
            tmp = [self.radial_records[i]["msg_header"][key] for i in msg_nums]
        return np.array(tmp)

    def get_times(self, scans=None):
        """
        Retrieve the times at which the rays were collected.

        Parameters
        ----------
        scans : list or None
            Scans (0-based) to retrieve ray (radial) collection times from.
            None (the default) will return the times for all scans in the
            volume.

        Returns
        -------
        time_start : Datetime
            Initial time.
        time : ndarray
            Offset in seconds from the initial time at which the rays
            in the requested scans were collected.

        """
        if scans is None:
            scans = range(self.nscans)
        days = self._radial_array(scans, "collect_date")
        secs = self._radial_array(scans, "collect_ms") / 1000.0
        offset = timedelta(days=int(days[0]) - 1, seconds=int(secs[0]))
        time_start = datetime(1970, 1, 1) + offset
        time = secs - int(secs[0]) + (days - days[0]) * 86400
        return time_start, time

    def get_azimuth_angles(self, scans=None):
        """
        Retrieve the azimuth angles of all rays in the requested scans.

        Parameters
        ----------
        scans : list ot None
            Scans (0 based) for which ray (radial) azimuth angles will be
            retrieved. None (the default) will return the angles for all
            scans in the volume.

        Returns
        -------
        angles : ndarray
            Azimuth angles in degress for all rays in the requested scans.

        """
        if scans is None:
            scans = range(self.nscans)
        if self._msg_type == 1:
            scale = 180 / (4096 * 8.0)
        else:
            scale = 1.0
        return self._radial_array(scans, "azimuth_angle") * scale

    def get_elevation_angles(self, scans=None):
        """
        Retrieve the elevation angles of all rays in the requested scans.

        Parameters
        ----------
        scans : list or None
            Scans (0 based) for which ray (radial) azimuth angles will be
            retrieved. None (the default) will return the angles for
            all scans in the volume.

        Returns
        -------
        angles : ndarray
            Elevation angles in degress for all rays in the requested scans.

        """
        if scans is None:
            scans = range(self.nscans)
        if self._msg_type == 1:
            scale = 180 / (4096 * 8.0)
        else:
            scale = 1.0
        return self._radial_array(scans, "elevation_angle") * scale

    def get_target_angles(self, scans=None):
        """
        Retrieve the target elevation angle of the requested scans.

        Parameters
        ----------
        scans : list or None
            Scans (0 based) for which the target elevation angles will be
            retrieved. None (the default) will return the angles for all
            scans in the volume.

        Returns
        -------
        angles : ndarray
            Target elevation angles in degress for the requested scans.

        """
        if scans is None:
            scans = range(self.nscans)
        if self._msg_type == 31:
            # Check self.nscans <= len(self.vcp["cut_parameters"]) is needed because it has been observed that VCP info is invalid for volume
            if self.vcp and self.nscans <= len(self.vcp["cut_parameters"]):
                cut_parameters = self.vcp["cut_parameters"]
            else:
                cut_parameters = [{"elevation_angle": 0.0}] * self.nscans
            scale = 360.0 / 65536.0
            return np.array(
                [cut_parameters[i]["elevation_angle"] * scale for i in scans],
                dtype="float32",
            )
        else:
            scale = 180 / (4096 * 8.0)
            msgs = [self.radial_records[self.scan_msgs[i][0]] for i in scans]
            return np.round(
                np.array(
                    [m["msg_header"]["elevation_angle"] * scale for m in msgs],
                    dtype="float32",
                ),
                1,
            )

    def get_nyquist_vel(self, scans=None):
        """
        Retrieve the Nyquist velocities of the requested scans.
        Parameters
        ----------
        scans : list or None
            Scans (0 based) for which the Nyquist velocities will be
            retrieved. None (the default) will return the velocities for all
            scans in the volume.
        Returns
        -------
        velocities : ndarray
            Nyquist velocities (in m/s) for the requested scans.
        """
        if scans is None:
            scans = range(self.nscans)
        return self._radial_sub_array(scans, "nyquist_vel") * 0.01
    
    def get_unambigous_range(self, scans=None):
        """
        Retrieve the unambiguous range of the requested scans.
        Parameters
        ----------
        scans : list or None
            Scans (0 based) for which the unambiguous range will be retrieved.
            None (the default) will return the range for all scans in the
            volume.
        Returns
        -------
        unambiguous_range : ndarray
            Unambiguous range (in meters) for the requested scans.
        """
        if scans is None:
            scans = range(self.nscans)
        # unambiguous range is stored in tenths of km, x100 for meters
        return self._radial_sub_array(scans, "unambig_range") * 100.0

    def get_data(self, moment, max_ngates, scans=None, raw_data=False):
        """
        Retrieve moment data for a given set of scans.

        Masked points indicate that the data was not collected, below
        threshold or is range folded.

        Parameters
        ----------
        moment : 'REF', 'VEL', 'SW', 'ZDR', 'PHI', 'RHO', or 'CFP'
            Moment for which to to retrieve data.
        max_ngates : int
            Maximum number of gates (bins) in any ray.
            requested.
        raw_data : bool
            True to return the raw data, False to perform masking as well as
            applying the appropiate scale and offset to the data.  When
            raw_data is True values of 1 in the data likely indicate that
            the gate was not present in the sweep, in some cases in will
            indicate range folded data.
        scans : list or None.
            Scans to retrieve data from (0 based). None (the default) will
            get the data for all scans in the volume.

        Returns
        -------
        data : ndarray

        """
        if scans is None:
            scans = range(self.nscans)

        # determine the number of rays
        msg_nums = self._msg_nums(scans)
        nrays = len(msg_nums)
        # extract the data
        set_datatype = False
        data = np.ones((nrays, max_ngates), ">B")
        for i, msg_num in enumerate(msg_nums):
            msg = self.radial_records[msg_num]
            if moment not in msg.keys():
                continue
            if not set_datatype:
                data = data.astype(">" + _bits_to_code(msg, moment))
                set_datatype = True

            ngates = min(msg[moment]["ngates"], max_ngates, len(msg[moment]["data"]))
            data[i, :ngates] = msg[moment]["data"][:ngates]
        # return raw data if requested
        if raw_data:
            return data

        # mask, scan and offset, assume that the offset and scale
        # are the same in all scans/gates
        for scan in scans:  # find a scan which contains the moment
            msg_num = self.scan_msgs[scan][0]
            msg = self.radial_records[msg_num]
            if moment in msg.keys():
                offset = np.float32(msg[moment]["offset"])
                scale = np.float32(msg[moment]["scale"])
                mask = data <= 1
                scaled_data = (data - offset) / scale
                return np.ma.array(scaled_data, mask=mask)

        # moment is not present in any scan, mask all values
        return np.ma.masked_less_equal(data, 1)


def _bits_to_code(msg, moment):
    """
    Convert number of bits to the proper code for unpacking.
    Based on the code found in MetPy:
    https://github.com/Unidata/MetPy/blob/40d5c12ab341a449c9398508bd41
    d010165f9eeb/src/metpy/io/_tools.py#L313-L321
    """
    if msg["header"]["type"] == 1:
        word_size = msg[moment]["data"].dtype
        if word_size == "uint16":
            return "H"
        elif word_size == "uint8":
            return "B"
        else:
            warnings.warn(('Unsupported bit size: %s. Returning "B"', word_size))
            return "B"

    elif msg["header"]["type"] == 31:
        word_size = msg[moment]["word_size"]
        if word_size == 16:
            return "H"
        elif word_size == 8:
            return "B"
        else:
            warnings.warn(('Unsupported bit size: %s. Returning "B"', word_size))
            return "B"
    else:
        raise TypeError("Unsupported msg type %s", msg["header"]["type"])


def _decompress_records(cbuf):
    """
    Decompress the records from an BZ2 compressed Archive 2 file.
    """
    bzip2_start_pos = _get_bzip2_start_indices(cbuf)
    n = len(bzip2_start_pos)
    # Remove the end-of-stream markers at the end of each bzip2 stream in order to enable decompression in one shot
    cbuf = b''.join([cbuf[s:(bzip2_start_pos[i+1]-4 if i+1 < n else None)] for i,s in enumerate(bzip2_start_pos)])
    buf = bz2.decompress(cbuf)
    return buf

def _get_bzip2_start_indices(cbuf):
    bzip2_start_pos = [i.start() for i in re.finditer(b'BZh', cbuf)]
    return [i for i in bzip2_start_pos if cbuf[i+5:i+10] in b'AY&SY']
        
def _decompress_records_meta(cbuf, bzip2_start_pos, bzip2_read_indices='all', max_length=300):
    n = len(bzip2_start_pos)
    if bzip2_read_indices == 'all':
        bzip2_read_indices = range(n)
    buf = []
    for i in bzip2_read_indices:
        i1 = bzip2_start_pos[i]
        i2 = bzip2_start_pos[i+1]-4 if i+1 < n else None
        decompressor = bz2.BZ2Decompressor()
        # Always read the first BZ2 block fully, since it contains important metadata like VCP pattern characteristics
        try:
            buf.append(decompressor.decompress(cbuf[i1:i2], max_length if i > 0 else -1))
        except Exception as e:
            print(e, i, '_decompress_records_meta')
            # In case of an error add an empty string. This can be properly dealt with in the function _read_records
            buf.append(b'')
    return buf


def _get_record_from_buf(buf, pos, moments=None):
    """Retrieve and unpack a NEXRAD record from a buffer."""
    dic = {"header": _unpack_from_buf(buf, pos, 'MSG_HEADER')}
    msg_type = dic["header"]["type"]
    if msg_type == 31:
        new_pos = _get_msg31_from_buf(buf, pos, dic, moments)
    elif msg_type == 5:
        # Sometimes we encounter incomplete buffers
        try:
            new_pos = _get_msg5_from_buf(buf, pos, dic)
        except struct.error:
            warnings.warn(
                "Encountered incomplete MSG5. File may be corrupt.", RuntimeWarning
            )
            new_pos = pos + RECORD_SIZE
    elif msg_type == 29:
        new_pos = _get_msg29_from_buf(pos, dic)
        warnings.warn("Message 29 encountered, not parsing.", RuntimeWarning)
    elif msg_type == 1:
        new_pos = _get_msg1_from_buf(buf, pos, dic)
    else:  # not message 31 or 1, no decoding performed
        new_pos = pos + RECORD_SIZE
    return new_pos, dic


def _get_msg29_from_buf(pos, dic):
    msg_size = dic["header"]["size"]
    if msg_size == 65535:
        msg_size = dic["header"]["segments"] << 16 | dic["header"]["seg_num"]
    msg_header_size = _structure_size['MSG_HEADER']
    new_pos = pos + msg_header_size + msg_size
    return new_pos


block_pointers = [f'block_pointer_{j}' for j in range(1, 11)]
def _get_msg31_from_buf(buf, pos, dic, moments=None):
    """Retrieve and unpack a MSG31 record from a buffer."""
    msg_size = dic["header"]["size"] * 2 - 4
    msg_header_size = _structure_size['MSG_HEADER']
    new_pos = pos + msg_header_size + msg_size
    mbuf = buf[pos + msg_header_size : new_pos]
    msg_31_header = _unpack_from_buf(mbuf, 0, 'MSG_31')
    for p in block_pointers:
        if msg_31_header.get(p, 0) > 0:
            block_name, block_dic = _get_msg31_data_block(mbuf, msg_31_header[p], moments)
            dic[block_name] = block_dic

    dic["msg_header"] = msg_31_header
    return new_pos


def _get_msg31_data_block(buf, ptr, moments=None):
    """Unpack a msg_31 data block into a dictionary."""
    block_name = buf[ptr + 1 : ptr + 4].decode("ascii").strip()

    if block_name == "VOL":
        dic = _unpack_from_buf(buf, ptr, 'VOLUME_DATA_BLOCK')
    elif block_name == "ELV":
        dic = _unpack_from_buf(buf, ptr, 'ELEVATION_DATA_BLOCK')
    elif block_name == "RAD":
        dic = _unpack_from_buf(buf, ptr, 'RADIAL_DATA_BLOCK')
    elif block_name in ["REF", "VEL", "SW", "ZDR", "PHI", "RHO", "CFP"]:
        if moments and not block_name in moments:
            return 'None', {}
        dic = _unpack_from_buf(buf, ptr, 'GENERIC_DATA_BLOCK', block_name)
        ngates = dic["ngates"]
        ptr2 = ptr + _structure_size['GENERIC_DATA_BLOCK']
        data = []
        if dic["word_size"] == 16:
            # data = slice(ptr2, ptr2 + ngates * 2)
            data = np.frombuffer(buf[ptr2 : ptr2 + ngates * 2], ">u2")
        elif dic["word_size"] == 8:
            # data = slice(ptr2, ptr2 + ngates)
            data = np.frombuffer(buf[ptr2 : ptr2 + ngates], ">u1")
        else:
            warnings.warn(
                'Unsupported bit size: %s. Returning array dtype "B"', dic["word_size"]
            )
        dic["data"] = data
    else:
        dic = {}
    return block_name, dic


def _get_msg1_from_buf(buf, pos, dic, moments=None):
    """Retrieve and unpack a MSG1 record from a buffer."""
    msg_header_size = _structure_size['MSG_HEADER']
    msg1_header = _unpack_from_buf(buf, pos + msg_header_size, 'MSG_1')
    dic["msg_header"] = msg1_header

    sur_nbins = int(msg1_header["sur_nbins"])
    doppler_nbins = int(msg1_header["doppler_nbins"])

    sur_step = int(msg1_header["sur_range_step"])
    doppler_step = int(msg1_header["doppler_range_step"])

    sur_first = int(msg1_header["sur_range_first"])
    doppler_first = int(msg1_header["doppler_range_first"])
    if doppler_first > 2**15:
        doppler_first = doppler_first - 2**16

    if msg1_header["sur_pointer"] and (not moments or 'REF' in moments): 
        offset = pos + msg_header_size + msg1_header["sur_pointer"]
        data = np.frombuffer(buf[offset : offset + sur_nbins], ">u1")
        dic["REF"] = {
            "ngates": sur_nbins,
            "gate_spacing": sur_step,
            "first_gate": sur_first,
            "data": data,
            "scale": 2.0,
            "offset": 66.0,
        }
    if msg1_header["vel_pointer"] and (not moments or 'VEL' in moments): 
        offset = pos + msg_header_size + msg1_header["vel_pointer"]
        data = np.frombuffer(buf[offset : offset + doppler_nbins], ">u1")
        dic["VEL"] = {
            "ngates": doppler_nbins,
            "gate_spacing": doppler_step,
            "first_gate": doppler_first,
            "data": data,
            "scale": 2.0,
            "offset": 129.0,
        }
        if msg1_header["doppler_resolution"] == 4:
            # 1 m/s resolution velocity, offset remains 129.
            dic["VEL"]["scale"] = 1.0
    if msg1_header["width_pointer"] and (not moments or 'REF' in moments):
        offset = pos + msg_header_size + msg1_header["width_pointer"]
        data = np.frombuffer(buf[offset : offset + doppler_nbins], ">u1")
        dic["SW"] = {
            "ngates": doppler_nbins,
            "gate_spacing": doppler_step,
            "first_gate": doppler_first,
            "data": data,
            "scale": 2.0,
            "offset": 129.0,
        }
    return pos + RECORD_SIZE


def _get_msg5_from_buf(buf, pos, dic):
    """Retrieve and unpack a MSG1 record from a buffer."""
    msg_header_size = _structure_size['MSG_HEADER']
    msg5_header_size = _structure_size['MSG_5']
    msg5_elev_size = _structure_size['MSG_5_ELEV']

    dic["msg5_header"] = _unpack_from_buf(buf, pos + msg_header_size, 'MSG_5')
    dic["cut_parameters"] = []
    for i in range(dic["msg5_header"]["num_cuts"]):
        pos2 = pos + msg_header_size + msg5_header_size + msg5_elev_size * i
        dic["cut_parameters"].append(_unpack_from_buf(buf, pos2, 'MSG_5_ELEV'))
    return pos + RECORD_SIZE


_structure_names = ('VOLUME_HEADER', 'MSG_HEADER', 'MSG_31', 'MSG_1', 'MSG_5', 'MSG_5_ELEV', 'GENERIC_DATA_BLOCK', 
                   'VOLUME_DATA_BLOCK', 'ELEVATION_DATA_BLOCK', 'RADIAL_DATA_BLOCK')

dic_before = {name:'' for name in _structure_names}
dic_before['GENERIC_DATA_BLOCK'] = {}
s_before = copy.deepcopy(dic_before)
def _unpack_from_buf(buf, pos, structure_name, product=None):
    global dic_before, s_before
    """Unpack a structure from a buffer."""
    size = _structure_size[structure_name]
    s = buf[pos : pos + size]
    s_b = s_before[structure_name] if structure_name != 'GENERIC_DATA_BLOCK' else s_before['GENERIC_DATA_BLOCK'].get(product, '')
    if s != s_b:
        dic = _unpack_structure(s, structure_name)
        if structure_name == 'GENERIC_DATA_BLOCK':
            dic_before[structure_name][product], s_before[structure_name][product] = dic.copy(), s
        else:
            dic_before[structure_name], s_before[structure_name] = dic, s
    else:
        if structure_name == 'GENERIC_DATA_BLOCK':
            dic = dic_before[structure_name][product].copy()
        else:
            dic = dic_before[structure_name]
    return dic


def _unpack_structure(string, structure_name):
    """Unpack a structure from a string."""
    fmt = _structure_format[structure_name]  # NEXRAD is big-endian
    lst = struct.unpack(fmt, string)
    return dict(zip(_structure_content[structure_name], lst))


# NEXRAD Level II file structures and sizes
# The deails on these structures are documented in:
# "Interface Control Document for the Achive II/User" RPG Build 12.0
# Document Number 2620010E
# and
# "Interface Control Document for the RDA/RPG" Open Build 13.0
# Document Number 2620002M
# Tables and page number refer to those in the second document unless
# otherwise noted.
RECORD_SIZE = 2432
COMPRESSION_RECORD_SIZE = 12
CONTROL_WORD_SIZE = 4

# format of structure elements
# section 3.2.1, page 3-2
CODE1 = "B"
CODE2 = "H"
INT1 = "B"
INT2 = "H"
INT4 = "I"
REAL4 = "f"
REAL8 = "d"
SINT1 = "b"
SINT2 = "h"
SINT4 = "i"

# Figure 1 in Interface Control Document for the Archive II/User
# page 7-2
VOLUME_HEADER = (
    ("tape", "9s"),
    ("extension", "3s"),
    ("date", "I"),
    ("time", "I"),
    ("icao", "4s"),
)

# Table II Message Header Data
# page 3-7
MSG_HEADER = (
    ("size", INT2),  # size of data, no including header
    ("channels", INT1),
    ("type", INT1),
    ("seq_id", INT2),
    ("date", INT2),
    ("ms", INT4),
    ("segments", INT2),
    ("seg_num", INT2),
)

# Table XVII Digital Radar Generic Format Blocks (Message Type 31)
# pages 3-87 to 3-89
MSG_31 = (
    ("id", "4s"),  # 0-3
    ("collect_ms", INT4),  # 4-7
    ("collect_date", INT2),  # 8-9
    ("azimuth_number", INT2),  # 10-11
    ("azimuth_angle", REAL4),  # 12-15
    ("compress_flag", CODE1),  # 16
    ("spare_0", INT1),  # 17
    ("radial_length", INT2),  # 18-19
    ("azimuth_resolution", CODE1),  # 20
    ("radial_spacing", CODE1),  # 21
    ("elevation_number", INT1),  # 22
    ("cut_sector", INT1),  # 23
    ("elevation_angle", REAL4),  # 24-27
    ("radial_blanking", CODE1),  # 28
    ("azimuth_mode", SINT1),  # 29
    ("block_count", INT2),  # 30-31
    ("block_pointer_1", INT4),  # 32-35  Volume Data Constant XVII-E
    ("block_pointer_2", INT4),  # 36-39  Elevation Data Constant XVII-F
    ("block_pointer_3", INT4),  # 40-43  Radial Data Constant XVII-H
    ("block_pointer_4", INT4),  # 44-47  Moment "REF" XVII-{B/I}
    ("block_pointer_5", INT4),  # 48-51  Moment "VEL"
    ("block_pointer_6", INT4),  # 52-55  Moment "SW"
    ("block_pointer_7", INT4),  # 56-59  Moment "ZDR"
    ("block_pointer_8", INT4),  # 60-63  Moment "PHI"
    ("block_pointer_9", INT4),  # 64-67  Moment "RHO"
    ("block_pointer_10", INT4),  # Moment "CFP"
)


# Table III Digital Radar Data (Message Type 1)
# pages 3-7 to
MSG_1 = (
    ("collect_ms", INT4),  # 0-3
    ("collect_date", INT2),  # 4-5
    ("unambig_range", SINT2),  # 6-7
    ("azimuth_angle", CODE2),  # 8-9
    ("azimuth_number", INT2),  # 10-11
    ("radial_status", CODE2),  # 12-13
    ("elevation_angle", INT2),  # 14-15
    ("elevation_number", INT2),  # 16-17
    ("sur_range_first", CODE2),  # 18-19
    ("doppler_range_first", CODE2),  # 20-21
    ("sur_range_step", CODE2),  # 22-23
    ("doppler_range_step", CODE2),  # 24-25
    ("sur_nbins", INT2),  # 26-27
    ("doppler_nbins", INT2),  # 28-29
    ("cut_sector_num", INT2),  # 30-31
    ("calib_const", REAL4),  # 32-35
    ("sur_pointer", INT2),  # 36-37
    ("vel_pointer", INT2),  # 38-39
    ("width_pointer", INT2),  # 40-41
    ("doppler_resolution", CODE2),  # 42-43
    ("vcp", INT2),  # 44-45
    ("spare_1", "8s"),  # 46-53
    ("spare_2", "2s"),  # 54-55
    ("spare_3", "2s"),  # 56-57
    ("spare_4", "2s"),  # 58-59
    ("nyquist_vel", SINT2),  # 60-61
    ("atmos_attenuation", SINT2),  # 62-63
    ("threshold", SINT2),  # 64-65
    ("spot_blank_status", INT2),  # 66-67
    ("spare_5", "32s"),  # 68-99
    # 100+  reflectivity, velocity and/or spectral width data, CODE1
)

# Table XI Volume Coverage Pattern Data (Message Type 5 & 7)
# pages 3-51 to 3-54
MSG_5 = (
    ("msg_size", INT2),
    ("pattern_type", CODE2),
    ("pattern_number", INT2),
    ("num_cuts", INT2),
    ("clutter_map_group", INT2),
    ("doppler_vel_res", CODE1),  # 2: 0.5 degrees, 4: 1.0 degrees
    ("pulse_width", CODE1),  # 2: short, 4: long
    ("spare", "10s"),  # halfwords 7-11 (10 bytes, 5 halfwords)
)

MSG_5_ELEV = (
    ("elevation_angle", CODE2),  # scaled by 360/65536 for value in degrees.
    ("channel_config", CODE1),
    ("waveform_type", CODE1),
    ("super_resolution", CODE1),
    ("prf_number", INT1),
    ("prf_pulse_count", INT2),
    ("azimuth_rate", CODE2),
    ("ref_thresh", SINT2),
    ("vel_thresh", SINT2),
    ("sw_thresh", SINT2),
    ("zdr_thres", SINT2),
    ("phi_thres", SINT2),
    ("rho_thres", SINT2),
    ("edge_angle_1", CODE2),
    ("dop_prf_num_1", INT2),
    ("dop_prf_pulse_count_1", INT2),
    ("spare_1", "2s"),
    ("edge_angle_2", CODE2),
    ("dop_prf_num_2", INT2),
    ("dop_prf_pulse_count_2", INT2),
    ("spare_2", "2s"),
    ("edge_angle_3", CODE2),
    ("dop_prf_num_3", INT2),
    ("dop_prf_pulse_count_3", INT2),
    ("spare_3", "2s"),
)

# Table XVII-B Data Block (Descriptor of Generic Data Moment Type)
# pages 3-90 and 3-91
GENERIC_DATA_BLOCK = (
    ("block_type", "1s"),
    ("data_name", "3s"),  # VEL, REF, SW, RHO, PHI, ZDR
    ("reserved", INT4),
    ("ngates", INT2),
    ("first_gate", SINT2),
    ("gate_spacing", SINT2),
    ("thresh", SINT2),
    ("snr_thres", SINT2),
    ("flags", CODE1),
    ("word_size", INT1),
    ("scale", REAL4),
    ("offset", REAL4),
    # then data
)

# Table XVII-E Data Block (Volume Data Constant Type)
# page 3-92
VOLUME_DATA_BLOCK = (
    ("block_type", "1s"),
    ("data_name", "3s"),
    ("lrtup", INT2),
    ("version_major", INT1),
    ("version_minor", INT1),
    ("lat", REAL4),
    ("lon", REAL4),
    ("height", SINT2),
    ("feedhorn_height", INT2),
    ("refl_calib", REAL4),
    ("power_h", REAL4),
    ("power_v", REAL4),
    ("diff_refl_calib", REAL4),
    ("init_phase", REAL4),
    ("vcp", INT2),
    ("spare", "2s"),
)

# Table XVII-F Data Block (Elevation Data Constant Type)
# page 3-93
ELEVATION_DATA_BLOCK = (
    ("block_type", "1s"),
    ("data_name", "3s"),
    ("lrtup", INT2),
    ("atmos", SINT2),
    ("refl_calib", REAL4),
)

# Table XVII-H Data Block (Radial Data Constant Type)
# pages 3-93
RADIAL_DATA_BLOCK = (
    ("block_type", "1s"),
    ("data_name", "3s"),
    ("lrtup", INT2),
    ("unambig_range", SINT2),
    ("noise_h", REAL4),
    ("noise_v", REAL4),
    ("nyquist_vel", SINT2),
    ("spare", "2s"),
)


_structure_content = {structure:[i[0] for i in globals()[structure]] for structure in _structure_names}
_structure_format = {structure:">" + "".join([i[1] for i in globals()[structure]]) for structure in _structure_names}
_structure_size = {structure:struct.calcsize(struct_format) for structure,struct_format in _structure_format.items()}


import json
import gzip
import blosc
import zarr

date = '20110524'
if __name__ == "__main__":
    
    #%%
    directory = '../data/radar/'
    filenames = [directory+'nexrad_l2/'+j for j in os.listdir(directory+'nexrad_l2') if j[-3:] == '.gz' and date in j]

    for i,filename in enumerate(filenames):
        test = NEXRADLevel2File(filename, read_mode="all")
        for j in range(16):
            print(i, j)
            info = test.scan_info(scans=[j])[0]
            ngates = info['ngates'][0]
            dr = info['gate_spacing'][0]
            first_gate = info['first_gate'][0]
            radials = np.arange(ngates, dtype='int16')
            
            vmin, vmax = -32.5, 80
            values = test.get_data('REF', max_ngates=ngates, scans=[j]).astype('float32').filled(vmin)
            values[values < vmin] = vmin
            values[values > vmax] = vmax
            values = (255*(values-vmin)/(vmax-vmin)).astype('uint8')
            
            azimuths = test.get_azimuth_angles(scans=[j]).astype('float32')
            i_start = azimuths.argmin()
            values = np.roll(values, -i_start, axis=0)
            azimuths = np.roll(azimuths, -i_start)
                        
            save_dir = directory+f'test_numpy_zarr/'
            os.makedirs(save_dir, exist_ok=True)
            z = zarr.open(save_dir+f'test_{i}_{j}.zarr', mode='w', shape=values.shape, chunks = values.shape, dtype='u1')
            z[:] = values
            z.attrs['first_gate'] = first_gate
            z.attrs['gate_spacing'] = dr
            z.attrs['ngates'] = ngates
            z.attrs['azimuths'] = azimuths.tolist()
            
    
    #%%
    directory = '../data/radar/'
    filenames = [directory+'nexrad_l2/'+j for j in os.listdir(directory+'nexrad_l2') if j[-3:] == '.gz' and date in j]
    print(len(filenames))

    for i,filename in enumerate(filenames):
        test = NEXRADLevel2File(filename, read_mode="all")
        for j in range(16):
            t = pytime.time()
            print(i, j)
            info = test.scan_info(scans=[j])[0]
            ngates = info['ngates'][0]
            dr = info['gate_spacing'][0]
            first_gate = info['first_gate'][0]
            radials = np.arange(ngates, dtype='int16')
            
            values = test.get_data('REF', max_ngates=ngates, scans=[j]).astype('float32')
            vmin, vmax = -10, 70
            values[values < vmin] = vmin
            values[values > vmax] = vmax
            values = (255*(values-vmin)/(vmax-vmin)).astype('uint8')
            
            azimuths = test.get_azimuth_angles(scans=[j]).astype('float32')
            i_start = azimuths.argmin()
            values = np.roll(values, -i_start, axis=0)
            azimuths = np.roll(azimuths, -i_start)
            
            total_bins = 0
            json_data = {'first_gate':first_gate, 'gate_spacing':dr, 'radial_deltas':[], 'values':[], 'azimuths':[round(j, 2) for j in azimuths.tolist()]}
            for k in range(len(values)):
                radials_k = radials[~values[k].mask]
                deltas = np.diff(radials_k)
                select = deltas == 1
                change1 = np.append(select[0], select[1:] & ~select[:-1])
                change2 = np.append(~select[1:] & select[:-1], select[-1])
                idx1, idx2 = np.nonzero(change1)[0], np.nonzero(change2)[0]
                n_ones = idx2-idx1+1
                for i1,i2,n in zip(idx1, idx2, n_ones):
                    if n > 1:
                        deltas[i1] = -n
                        deltas[i1+1:i2+1] = 0
                deltas = deltas[deltas != 0]
                
                radial_deltas = [int(radials_k[0])]+deltas.tolist()
                values_k = values[k][~values[k].mask].filled()
                json_data['radial_deltas'].append(radial_deltas)
                json_data['values'].append(values_k.tolist())
                total_bins += len(radials_k)
            json_data['total_bins'] = total_bins
            print(pytime.time()-t, 't', i, j)    
            save_dir = directory+f'test_gzip_uint8_radial_deltas_round_azis_minus_{date}/'
            os.makedirs(save_dir, exist_ok=True)
            with gzip.open(save_dir+f'test_{i}_{j}.json.gz', 'wt', encoding="ascii") as zipfile:
                json.dump(json_data, zipfile)
            # with open(directory+f'test_gzip/test_{i}_{j}.json', 'w') as f:
            #     json.dump(json_data, f)    
    
    
    #%%
    directory = '../data/radar/'
    filenames = [directory+'nexrad_l2/'+j for j in os.listdir(directory+'nexrad_l2') if j[-3:] == '.gz' and date in j]

    for i,filename in enumerate(filenames):
        test = NEXRADLevel2File(filename, read_mode="all")
        for j in range(16):
            print(i, j)
            info = test.scan_info(scans=[j])[0]
            ngates = info['ngates'][0]
            dr = info['gate_spacing'][0]
            first_gate = info['first_gate'][0]
            radials = np.arange(ngates, dtype='uint16')
            
            values = test.get_data('REF', max_ngates=ngates, scans=[j]).astype('float32')
            vmin, vmax = -10, 70
            values[values < vmin] = vmin
            values[values > vmax] = vmax
            values = (255*(values-vmin)/(vmax-vmin)).astype('uint8')
            
            azimuths = test.get_azimuth_angles(scans=[j]).astype('float32')
            i_start = azimuths.argmin()
            values = np.roll(values, -i_start, axis=0)
            azimuths = np.roll(azimuths, -i_start)
            
            total_bins = 0
            json_data = {'first_gate':first_gate, 'gate_spacing':dr, 'radial_deltas':[], 'values':[], 'azimuths':[round(j, 2) for j in azimuths.tolist()]}
            for k in range(len(values)):
                radials_k = radials[~values[k].mask]
                radials_k_deltas = [int(radials_k[0])]+np.diff(radials_k).tolist()
                values_k = values[k][~values[k].mask].filled()
                json_data['radial_deltas'].append(radials_k_deltas)
                json_data['values'].append(values_k.tolist())
                total_bins += len(radials_k)
            json_data['total_bins'] = total_bins
                
            save_dir = directory+'test_gzip_uint8_radial_deltas_round_azis/'
            os.makedirs(save_dir, exist_ok=True)
            with gzip.open(save_dir+f'test_{i}_{j}.json.gz', 'wt', encoding="ascii") as zipfile:
                json.dump(json_data, zipfile)
            # with open(directory+f'test_gzip/test_{i}_{j}.json', 'w') as f:
            #     json.dump(json_data, f)
                        
            
    #%%        
    directory = '../data/radar/'
    filenames = [directory+'nexrad_l2/'+j for j in os.listdir(directory+'nexrad_l2') if j[-3:] == '.gz']

    for i,filename in enumerate(filenames):
        test = NEXRADLevel2File(filename, read_mode="all")
        for j in range(16):
            print(i, j)
            info = test.scan_info(scans=[j])[0]
            ngates = info['ngates'][0]
            dr = info['gate_spacing'][0]
            first_gate = info['first_gate'][0]
            
            vmin, vmax = -32.5, 80            
            values = test.get_data('REF', max_ngates=ngates, scans=[j]).astype('float32').filled(vmin)
            values[values < vmin] = vmin
            values[values > vmax] = vmax
            values = (255*(values-vmin)/(vmax-vmin)).astype('uint8')
            
            azimuths = test.get_azimuth_angles(scans=[j]).astype('float32')
            i_start = azimuths.argmin()
            values = np.roll(values, -i_start, axis=0)
            azimuths = np.roll(azimuths, -i_start)
            
            json_data = {'first_gate':first_gate, 'gate_spacing':dr, 'values':values.tolist(), 'azimuths':azimuths.tolist()}
                
            save_dir = directory+f'test_gzip_uint8_fullarr_{date}/'
            os.makedirs(save_dir, exist_ok=True)
            with gzip.open(save_dir+f'test_{i}_{j}.json.gz', 'wt', encoding="ascii") as zipfile:
                json.dump(json_data, zipfile)
            # with open(directory+f'test_gzip/test_{i}_{j}.json', 'w') as f:
            #     json.dump(json_data, f)