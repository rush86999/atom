#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)/atomic-docker
cd atomic-docker && python3 -m unittest discover -s . -p "test_*.py"
