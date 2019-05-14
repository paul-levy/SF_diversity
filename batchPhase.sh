#!/bin/bash

source activate lcv-python

# 1st arg - cell #
# 2nd arg - dispersion (0 - single gratings; 1 - mixture)
# 3rd arg - exp dir (e.g. V1/ or LGN/)
# 4th arg - plot phase/response by condition?
# 5th arg - make summary plots of rvc fits, phase advance fits?
# 6th arg - optional: direction (default is ??) 

for run in {1..5}
do
  python phase_plotting.py $run 0 V1/ 1 1 1 & 
  #python phase_plotting.py $run 0 V1/ 1 1 1 & 

  python phase_plotting.py $run 0 V1/ 1 1 -1 & 
  #python phase_plotting.py $run 0 V1/ 1 1 -1 & 
done

# leave a blank line at the end