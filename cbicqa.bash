#!/bin/bash
#
# Single QA analysis script
#
# AUTHOR : Mike Tyszka, Ph.D.
# PLACE  : Caltech Brain Imaging Center
# DATES  : 10/10/2011 JMT From scratch
#
# This file is part of CBICQA.
#
#    CBICQA is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    CBICQA is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#   along with CBICQA.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2011-2013 California Institute of Technology.

if [ $# -lt 2 ]; then
  echo "-----------------"
  echo "SYNTAX : cbicqa.bash <QA Date> <Overwrite [Y|N]>"
  echo "<QA Date> has format: YYYYMMDD"
  echo "This script is designed to be called by cbicqa_all.bash, but can be run manually"
  exit
fi

# Construct QA analysis directory name
qa_date=$1
qa_overwrite=$2
qa_dir=${CBICQA_DATA}/${qa_date}

# Full paths to commands (for XGrid if used)
cmd_getdicom=${CBICQA_BIN}/cbicqa_getdicom.bash
cmd_convert=${CBICQA_BIN}/cbicqa_dicom2nifti.bash
cmd_moco=${CBICQA_BIN}/cbicqa_moco.bash
cmd_timeseries=${CBICQA_BIN}/cbicqa_timeseries.bash
cmd_stats=${CBICQA_BIN}/cbicqa_stats.py
cmd_report=${CBICQA_BIN}/cbicqa_report.py

# Check if directory already exists - if not, get data and analyze
if [ ! -d ${qa_dir} -o ${qa_overwrite} == "Y" ]
then

  echo ""
  echo "----------------------------"
  echo "NEW QA ANALYSIS : ${qa_date}"
  echo "----------------------------"
  
  if [ -s ${qa_dir}/qa.nii.gz ]
  then
  
    echo "  DICOM data has already been retrieved and converted - skipping"
  
  else
  
    # Retrieve QA DICOM stack from local OsiriX
    $cmd_getdicom $qa_dir $qa_date

    # Convert QA DICOM stack to 4D Nifti-1 volume
    $cmd_convert $qa_dir
	
  fi

  if [ -s ${qa_dir}/qa_mcf.nii.gz ]
  then

    echo "  Motion correction has already been performed - skipping"

  else

    # Motion correct QA series
    $cmd_moco $qa_dir

  fi
  
  # Generate QA timeseries
  $cmd_timeseries $qa_date

  # Calculate QA stats
  $cmd_stats $qa_date

  # Generate HTML report and summary files
  $cmd_report $qa_date
  
  echo "  Complete"
  
fi
