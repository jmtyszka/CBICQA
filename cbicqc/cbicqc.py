#!/usr/bin/env python3
"""
CBICQC quality control analysis and reporting class
The main analysis and reporting workflow is handled from here

AUTHORS
----
Mike Tyszka, Ph.D., Caltech Brain Imaging Center

DATES
----
2019-05-30 JMT Split out from workflow into single class for easy testing

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
import json
import tempfile
import shutil
import numpy as np
import nibabel as nb
import datetime as dt

from bids import BIDSLayout

from .timeseries import temporal_mean_sd, extract_timeseries, detrend_timeseries
from .graphics import (plot_roi_timeseries, plot_roi_powerspec,
                       plot_mopar_timeseries, plot_mopar_powerspec,
                       orthoslices,
                       roi_demeaned_ts)
from .rois import roi_labels
from .metrics import qc_metrics
from .moco import moco_phantom, moco_live
from .report import ReportPDF


class CBICQC:

    def __init__(self, bids_dir, subject, session):

        self._bids_dir = bids_dir
        self._subject = subject
        self._session = session

        # Create work and report directories
        self._work_dir = tempfile.mkdtemp()
        self._report_dir = os.path.join(self._bids_dir, 'derivatives', 'cbicqc')
        os.makedirs(self._report_dir, exist_ok=True)

        # Intermediate filenames
        self._report_pdf = os.path.join(self._report_dir, '{}_{}_qc.pdf'.format(self._subject, self._session))
        self._tmean_fname = os.path.join(self._work_dir, 'tmean.nii.gz')
        self._tsd_fname = os.path.join(self._work_dir, 'tsd.nii.gz')
        self._roi_labels_fname = os.path.join(self._work_dir, 'roi_labels.nii.gz')
        self._roi_ts_png = os.path.join(self._work_dir, 'roi_timeseries.png')
        self._roi_ps_png = os.path.join(self._work_dir, 'roi_powerspec.png')
        self._mopar_ts_png = os.path.join(self._work_dir, 'mopar_timeseries.png')
        self._mopar_pspec_png = os.path.join(self._work_dir, 'mopar_powerspec.png')
        self._tmean_montage_png = os.path.join(self._work_dir, 'tmean_montage.png')
        self._tsd_montage_png = os.path.join(self._work_dir, 'tsd_montage.png')
        self._rois_montage_png = os.path.join(self._work_dir, 'rois_montage.png')
        self._rois_demeaned_png = os.path.join(self._work_dir, 'rois_demeaned.png')

        # Flags
        self._save_intermediates = False

    def run(self):

        print('')
        print('Starting CBIC QC analysis')

        # Get BIDS layout
        # Index BIDS directory
        layout = BIDSLayout(self._bids_dir,
                            absolute_paths=True,
                            ignore=['work', 'derivatives', 'exclude'])

        # Get first QC image for this subject/session
        img_list = layout.get(subject=self._subject,
                              session=self._session,
                              suffix='T2star',
                              extensions=['nii', 'nii.gz'],
                              return_type='file')
        if not img_list:
            print('* No QC images found for subject {} session {} - exiting'.
                  format(self._subject, self._session))
            sys.exit(1)

        qc_img_fname = img_list[0]
        qc_meta_fname = qc_img_fname.replace('.nii.gz', '.json')

        # Load 4D QC phantom image
        print('  Loading QC timeseries image')
        qc_nii = nb.load(qc_img_fname)

        # Load metadata if available
        print('  Loading QC metadata')
        try:
            with open(qc_meta_fname, 'r') as fd:
                meta = json.load(fd)
        except IOError:
            print('* Could not open image metadata {}'.format(qc_meta_fname))
            print('* Using default imaging parameters')
            meta = self._default_metadata()

        # Integrate additional meta data from Nifti header and filename
        meta['Subject'] = self._subject
        meta['Session'] = self._session
        meta['VoxelSize'] = ' x '.join(str(x) for x in qc_nii.header.get('pixdim')[1:4])
        meta['MatrixSize'] = ' x '.join(str(x) for x in qc_nii.shape)

        # Perform rigid body motion correction on QC series
        print('  Starting motion correction')
        t0 = dt.datetime.now()

        qc_moco_nii, qc_moco_pars = self._moco(qc_nii, skip=False)

        t1 = dt.datetime.now()
        print('  Completed motion correction in {} seconds'.format((t1-t0).seconds))

        # Temporal mean and sd images
        print('  Calculating temporal mean image')
        tmean_nii, tsd_nii, tsfnr_nii = temporal_mean_sd(qc_moco_nii)

        # Create ROI labels
        print('  Constructing ROI labels')
        rois_nii = roi_labels(tmean_nii)

        # Extract ROI time series
        print('  Extracting ROI time series')
        s_mean_t = extract_timeseries(qc_moco_nii, rois_nii)

        # Detrend time series
        print('  Detrending time series')
        fit_results, s_detrend_t = detrend_timeseries(s_mean_t)

        # Calculate QC metrics
        metrics = qc_metrics(fit_results, tsfnr_nii, rois_nii)

        # Time vector (seconds)
        t = np.arange(0, s_mean_t.shape[1]) * meta['RepetitionTime']

        #
        # Generate PDF Report
        #

        print('')
        print('Generating Report')

        # Create report images
        print('  Creating report images')

        print('    ROI Timeseries')
        plot_roi_timeseries(t, s_mean_t, s_detrend_t, self._roi_ts_png)
        plot_roi_powerspec(t, s_detrend_t, self._roi_ps_png)

        print('    Motion Timeseries')
        plot_mopar_timeseries(t, qc_moco_pars, self._mopar_ts_png)
        plot_mopar_powerspec(t, qc_moco_pars, self._mopar_pspec_png)

        print('    ROI Residuals')
        roi_demeaned_ts(qc_moco_nii, rois_nii, self._rois_demeaned_png)

        print('    Orthoslices')
        orthoslices(tmean_nii, self._tmean_montage_png, cmap='gray', irng='robust')
        orthoslices(tsd_nii, self._tsd_montage_png, cmap='viridis', irng='robust')
        orthoslices(rois_nii, self._rois_montage_png, cmap='tab20', irng='noscale')

        # OPTIONAL: Save intermediate images
        if self._save_intermediates:

            print('  Saving intermediate images')
            nb.save(tmean_nii, self._tmean_fname)
            nb.save(tsd_nii, self._tsd_fname)
            nb.save(rois_nii, self._roi_labels_fname)

        # Construct filename dictionary to pass to PDF generator
        fnames = dict(WorkDir=self._work_dir,
                      ReportPDF=self._report_pdf,
                      ROITimeseries=self._roi_ts_png,
                      ROIPowerspec=self._roi_ps_png,
                      MoparTimeseries=self._mopar_ts_png,
                      MoparPowerspec=self._mopar_pspec_png,
                      TMeanMontage=self._tmean_montage_png,
                      TSDMontage=self._tsd_montage_png,
                      ROIsMontage=self._rois_montage_png,
                      ROIDemeanedTS=self._rois_demeaned_png,
                      TMean=self._tmean_fname,
                      TSD=self._tsd_fname,
                      ROILabels=self._roi_labels_fname)

        # Build PDF report
        print('  Building PDF')
        ReportPDF(fnames, meta, metrics)

        # Cleanup temporary QC directory
        self.cleanup(skip=True)

        return fnames

    def cleanup(self, skip=False):

        if skip:
            print('Retaining {}'.format(self._work_dir))
        else:
            print('Deleting work directory')
            shutil.rmtree(self._work_dir)

    def _default_metadata(self):

        meta = dict(Manufacturer='Unkown',
                    Scanner='Unknown',
                    RepetitionTime=3.0,
                    EchoTime=0.030)

        return meta

    def _parse_filename(self, fname):

        bname = os.path.basename(fname)

        # Split at underscores
        keyvals = bname.split('_')

        subject, session = 'Unknown', 'Unknown'

        for kv in keyvals:

            if '-' in kv and len(kv) >= 3:

                k, v = kv.split('-')

                if 'sub' in k:
                    subject = v
                if 'ses' in k:
                    session = v

        return subject, session

    def _moco(self, img_nii, mode='phantom', skip=True):
        """
        Motion correction wrapper

        :param img_nii: Nifti, image object
        :param mode: str, QC mode ('phantom' or 'live')
        :param skip: bool, skip moco flag
        :return moco_nii: Nifti, motion corrected image object
        :return moco_pars: array, motion parameter timeseries
        """

        if skip:

            moco_nii = img_nii
            moco_pars = np.zeros([img_nii.shape[3], 6])

        else:

            if 'phantom' in mode:

                moco_nii, moco_pars = moco_phantom(img_nii)

            else:

                moco_nii, moco_pars = moco_live(img_nii, self._work_dir)

        return moco_nii, moco_pars

    def _save_report(self, src_pdf, dest_pdf):

        if os.path.isfile(dest_pdf):
            os.remove(dest_pdf)
        elif os.path.isdir(dest_pdf):
            shutil.rmtree(dest_pdf)

        print('Saving QC report to {}'.format(dest_pdf))
        shutil.copyfile(src_pdf, dest_pdf)




