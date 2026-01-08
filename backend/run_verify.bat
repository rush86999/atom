@echo off
python -u verify_phase_2.py > verify_output.log 2>&1
type verify_output.log
