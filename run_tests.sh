#!/bin/bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 -m unittest atomic-docker/project/functions/atom-agent/test_research_agent.py
