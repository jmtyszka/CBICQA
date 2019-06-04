#!/usr/bin/env python3
"""
Lightweight QC analysis and reporting for daily phantom scans

Authors
----
Mike Tyszka, Caltech Brain Imaging Center

Dates
----
2016-08-03 JMT From scratch
2016-11-04 JMT Add session directory to DICOM heirarchy
2017-11-09 JMT Added support for DWI, no sessions, IntendedFor and TaskName
2018-03-09 JMT Fixed IntendedFor handling (#20, #27) and run-number issues (#28)
               Migrated to pydicom v1.0.1 (note namespace change to pydicom)
2019-02-25 JMT Fixed arbitrary run ordering (sorted glob)
2019-03-20 JMT Restructure as PyPI application with BIDS 1.2 compliance
2019-03-22 JMT Add BIDS validation
2019-05-20 JMT Port to nipype workflow

MIT License

Copyright (c) 2019 Mike Tyszka

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import os
import sys
import argparse
import pkg_resources

from cbicqc.workflow import CBICQCWorkflow


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Lightweight daily phantom QC analysis and reporting')
    parser.add_argument('-d', '--qcdir', required=True, help='QC dataset directory (BIDS format)')
    parser.add_argument('-sge', action='store_true', help='Submit QC workflow to Sun Grid Engine')

    # Parse command line arguments
    args = parser.parse_args()
    bids_dir = os.path.realpath(args.qcdir)

    # Read version from setup.py
    ver = pkg_resources.get_distribution('cbicqc').version

    # Splash
    print('')
    print('-----------------------------')
    print('CBIC Quality Control Pipeline')
    print('-----------------------------')
    print('Version : {}'.format(ver))
    print('')

    # Setup workflow for QC on all sessions in BIDS directory
    print('Setting up workflow')
    qc_wf = CBICQCWorkflow(bids_dir)
    qc_wf.run(args.sge)

    # Clean exit
    sys.exit(0)


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()