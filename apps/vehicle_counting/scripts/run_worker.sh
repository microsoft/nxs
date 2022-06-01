#!/bin/bash

export PYTHONPATH=/app

python3 apps/vehicle_counting/worker/worker.py \
--object_detector_uuid $DETECTOR_UUID \
--tracker_uuid $TRACKER_UUID \
--debug $DEBUG