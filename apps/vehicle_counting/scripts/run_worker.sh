#!/bin/bash

export PYTHONPATH=/app

python3 apps/vehicle_counting/worker/worker.py \
--object_detector_uuid $DETECTOR_UUID \
--tracker_uuid $TRACKER_UUID \
--counting_report_interval_secs $REPORT_INTERVAL_SECS \
--debug $DEBUG