#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 -m unittest atomic-docker/project/functions/test_research_agent.py
