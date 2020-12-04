#!/usr/bin/env python3
"""
Create summary PDF report

AUTHORS
----
Mike Tyszka, Ph.D., Caltech Brain Imaging Center

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
import shutil
import tempfile
from datetime import datetime

import matplotlib.pyplot as plt
from pandas.plotting import register_matplotlib_converters
import numpy as np
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate,
                                Paragraph,
                                Spacer,
                                Image,
                                Table,
                                PageBreak)

from .graphics import (metric_trend_plot)


class SummaryPDF:

    def __init__(self, report_dir, metrics, summary_months):
        """
        Construct summary report PDF

        :param report_dir: str, report output directory in derivatives
        :param metrics: list, session metric dictionaries including metadata
        :param summary_months: int, number of past months to summarize
        """

        # For datetime axis labeling without warnings
        register_matplotlib_converters()

        self._report_dir = report_dir
        self._metrics = metrics
        self._subject = metrics[0]['Subject']
        self._summary_months = summary_months
        self._summary_pdf = os.path.join(report_dir, '{}_summary.pdf'.format(self._subject))

        # Create working directory for images
        self._work_dir = tempfile.mkdtemp()

        # Contents - list of flowables to be built into a document
        self._contents = []

        # Add a justified paragraph style
        self._pstyles = getSampleStyleSheet()
        self._pstyles.add(ParagraphStyle(name='Justify', alignment=TA_JUSTIFY))

        self._init_pdf()
        self._add_coverpage()
        self._add_metric_graphs('Noise')
        self._add_metric_graphs('Spike/Drift')

        self._doc.build(self._contents)

        # Delete working directory
        shutil.rmtree(self._work_dir)

    def _add_metric_graphs(self, metric='Noise'):
        """
        Add timecourse and histogram plots for the given metric class ('Noise' or 'Spike/Drift')
        :return:
        """

        if 'Noise' in metric:
            metric_list = [
                'SNR',
                'SFNR',
                'NoiseFloor'
            ]
        elif 'Spike/Drift' in metric:
            metric_list = [
                'Drift',
                'NyquistSpikes',
                'AirSpikes'
            ]
        else:
            print('* Unknown metric class : {:s} - skipping'.format(metric))
            return

        # Page break
        self._contents.append(PageBreak())

        ptext = '<font size=14><b>Session {:s}} Trends</b></font>'.format(metric)
        self._contents.append(Paragraph(ptext, self._pstyles['Justify']))
        self._contents.append(Spacer(1, 0.25 * inch))

        trend_png_fname = self._plot_trends(metric_list)
        trends_img = Image(trend_png_fname, 6.0 * inch, 6.0 * inch, hAlign='LEFT')
        self._contents.append(trends_img)

    def _init_pdf(self):

        # Create a new PDF document
        self._doc = SimpleDocTemplate(self._summary_pdf,
                                      pagesize=letter,
                                      rightMargin=0.5 * inch,
                                      leftMargin=0.5 * inch,
                                      topMargin=0.5 * inch,
                                      bottomMargin=0.5 * inch)

    def _add_coverpage(self):

        ptext = '<font size=24>CBIC Quality Control Summary</font>'
        self._contents.append(Paragraph(ptext, self._pstyles['Justify']))
        self._contents.append(Spacer(1, 0.5 * inch))

        timestamp = datetime.now().strftime('%Y-%m-%d at %H:%M:%S')
        ptext = '<font size=12>Generated by CBICQC on {}</font>'.format(timestamp)
        self._contents.append(Paragraph(ptext, self._pstyles['Justify']))
        self._contents.append(Spacer(1, 0.25 * inch))

        ptext = '<font size=14><b>Subject Details</b></font>'
        self._contents.append(Paragraph(ptext, self._pstyles['Justify']))
        self._contents.append(Spacer(1, 0.1 * inch))

        # First session metadata - assume identical for all sessions
        m = self._metrics[0]

        meta = [['Subject', self._subject],
                ['Scanner', m['StationName'] + ' ' + m['DeviceSerialNumber']],
                ['Software Version', m['SoftwareVersions']],
                ['Coil Name', m['ReceiveCoilName']]]

        self._contents.append(Table(meta, hAlign='LEFT'))
        self._contents.append(Spacer(1, 0.25 * inch))

    def _plot_trends(self, metric_list):
        """
        Generate a PNG of the trends and histogram for each of the passed metrics

        :param metric_list: str list
            List of metrics to plots
        :return:
        """

        nm = len(metric_list)

        t = []
        mm = []

        for mt in self._metrics:

            if 'AcquisitionDateTime' in mt.keys():
                dt = datetime.strptime(mt['AcquisitionDateTime'], '%Y-%m-%dT%H:%M:%S.%f')
                t.append(dt)
                mm.append([mt[m_name] for m_name in metric_list])
            else:
                print('* Acquisition time unknown - skipping')

        t, mm = np.array(t), np.array(mm)

        # Output PNG filenames
        png_fname = os.path.join(self._work_dir, 'metric_trends.png')

        # Create a subplot matrix to hold trend and histogram plots
        fig, axs = plt.subplots(nm, 2, figsize=(nm * 2.0, 7.0))

        # Fill each of the subplots
        for mc, m_name in enumerate(metric_list):
            metric_trend_plot(m_name, t, mm[:, mc], axs[mc, 0])
            #metric_histogram(m_name, t, mm[:, mc], axs[mc, 1])

        # Tweak subplot margins and spacing
        plt.subplots_adjust(bottom=0.0, top=0.9, left=0.0, right=1.0)
        plt.tight_layout()

        # Save plot to file
        plt.savefig(png_fname, dpi=300)

        return png_fname
