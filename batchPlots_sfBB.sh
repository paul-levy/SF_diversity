#!/bin/bash

### README
### WARN: have you set the fitList base name?

# NOTE: assumes normType = 1 (flat) and normType = 2 (gauss) are present
# -- will choose normType = 1 for LGN, =2 for non-LGN front-end

# 2nd param is excType: 1 (gaussian deriv); 2 (flex. gauss)
# 3rd param is loss_type:
	# 1 - square root
	# 2 - poisson
	# 3 - modulated poission
	# 4 - chi squared
# 4 param is expDir (e.g. altExp/ or LGN/)
# 5 param is lgnFrontEnd (choose LGN type; will be comparing against non-LGN type)
# 6 param is diffPlot (i.e. plot everything relative to flat model prediction)
# 7 param is interpModel (i.e. interpolate model?)
# 8th param is kMult (0.01, 0.05, 0.10, usually...)
# 9th param is whether (1) or not (0) to do vector correction F1
# 10th param is whether to include the onset transient correction for F1 responses (use onsetDur in mS to use (e.g. 100); 0 to do without)
# 11th param is respExpFixed (-1 for not fixed, then specific value for a fit with fixed respExp [e.g. 1 or 2])
# 12th param is std/sem as variance measure: (1 sem (default))

source activate pytorch-lcv

EXC_TYPE=$1
LOSS=$2
HPC=$3
NORM_TYPE=$4
WHICH_PLOT=$5
VEC_F1=${6:-0}

if [[ $WHICH_PLOT -eq 1 ]]; then
  PYCALL="plot_sfBB.py"
else
  PYCALL="plot_sfBB_sep.py"
fi

# 1 means the original type of weighted gain control; 2 means the newer type
# default is zero, i.e. not HPC fits...

# 20 cells if original datalist; 41 cells if dataList_210222
for run in {1..24} # was ..58 before cutting dataList_210721
do
  ######
  ## New version, model fits - the doubled (i.e. two-digit) inputs are, in order, normTypes, (lgn)conTypes, lgnFrontEnd
  ######
  # ------------------------e-------l------dir--nrm---lgn-dif-kmul--onsr--sem-----
  # -----------------------------------------------con---inp----cor-rExp-------
  # modA: flat, fixed RVC, lgn A; modB: wght, fixed RVC, lgnA
  #python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 12 44 11 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated
  # modA: flat, fixed RVC, lgn A; modB: wght, standard RVC, lgnA
  #python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 12 41 11 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated
  # modA: flat, standard RVC, lgn A; modB: wght, standard RVC, lgnA
  #python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 12 11 11 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated
  # pytorch mod; modA: wght, fixed RVC, lgn A; modB: wght, standard RVC, lgnA
  #python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 22 41 11 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated
  # modA: flat, no LGN; modB: wght, no LGN
  python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 12 11 00 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated
  # modA: flat, no LGN; modB: asym, no LGN
  #python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 10 11 00 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated

done
wait
for run in {25..47} # was ..58 before cutting dataList_210721
do
  ######
  ## New version, model fits - the doubled (i.e. two-digit) inputs are, in order, normTypes, (lgn)conTypes, lgnFrontEnd
  ######
  # ------------------------e-------l------dir--nrm---lgn-dif-kmul--onsr--sem-----
  # -----------------------------------------------con---inp----cor-rExp-------
  # modA: flat, fixed RVC, lgn A; modB: wght, fixed RVC, lgnA
  #python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 12 44 11 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated
  # modA: flat, fixed RVC, lgn A; modB: wght, standard RVC, lgnA
  #python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 12 41 11 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated
  # modA: flat, standard RVC, lgn A; modB: wght, standard RVC, lgnA
  #python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 12 11 11 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated
  # pytorch mod; modA: wght, fixed RVC, lgn A; modB: wght, standard RVC, lgnA
  #python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 22 41 11 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated
  # modA: flat, no LGN; modB: wght, no LGN
  python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 12 11 00 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated
  # modA: flat, no LGN; modB: asym, no LGN
  #python3.6 $PYCALL $run $EXC_TYPE $LOSS V1_BB/ 10 11 00 0 0 0.05 $VEC_F1 0 -1 1 $HPC & # no diff, not interpolated

done

# leave a blank line at the end

