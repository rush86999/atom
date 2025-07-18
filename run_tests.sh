#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 -m unittest discover atomic-docker/project/functions/python_api_service/tests
