#!/bin/bash

### README
# Have you set the dataList name?
# Have you set the phAdv name?
# Have you set the RVC name?
# Have you set the descriptive fit name?
# Have you set the modelRecovery status/type?
#
# e.g. calls
# sh batchDescr_par.sh V1_orig/ 1 1 0 // fit both rvc, sf; no bootstrapping
# sh batchDescr_par.sh V1/ 1 1 250 // fit both rvc, sf; 250 bootstrap reps.
#
### Go to descr_fits.py first

# arguments are
#   1 - cell #
#   2 - dispersion (index into the list of dispersions for that cell; not used in descr/DoG fits)
#   3 - data directory (e.g. LGN/ or V1/)
#   4 - make phase advance fits (yes [1], no [0], vec correction for F1 [-1])
#   5 - make RVC fits
#   6 - make RVC f0-only fits
#   7 - which RVC model? (see hf::rvc_fit_name)
#       0 - Movshon/Kiorpes (only for LGN)
#       1 - Naka-Rushton 
#       2 - Peirce-adjustment of Naka-Rushton (can super-saturate)
#   8 - make descriptive (DoG) fits (1 or 0)
#   9 - DoG model (flexGauss [0; not DoG] or sach [1] or tony [2])
#   10 - loss type (for DoG fit); 
#       1 - lsq
#       2 - sqrt
#       3 - poiss [was previously default]
#       4 - Sach sum{[(exp-obs)^2]/[k+sigma^2]} where
#           k := 0.01*max(obs); sigma := measured variance of the response
#   11 - bootstrap fits (0 - no; nBoots[>0] - yes) //see hf.dog_fit for details
#   12 - joint fitting (0 - no; 1 - yes) //see hf.dog_fit for details
#   [13 - phase direction (pos or neg)]; default is pos (1); neg (-1); or NEITHER (0)
#   [14 - modRecov]; default is None; 1 for yes, 0 for no
#   [15 - cross_val]; default is None (i.e. don't do cross-validation); 1 if you want to do so
#   [16 - vol_lam]; default is 0; if doing cross_val, what's the constant on the gain penalty
#   [17 - regularization for gain term (>0 means penalize for high gain)] default is 0

### GUIDE (as of 19.11.05)
# V1/ - use dataList_glx.npy, was 35 cells -- now 56 (as of m681)
# V1/ - model recovery (dataList_glx_mr; mr_fitList...), 10 cells
# V1_orig/ - model recovery (dataList_mr; mr_fitList...), 10 cells
# V1_orig/ - standard, 59 cells
# altExp   - standard, 8 cells
# LGN/ - standard, 88 cells (as of 21.05.24)

########
### NOTES: 
###   If running only SF descr or RVC-f0 fits, do not need to run separately for all disp
###   
########

CELL=$1
EXP_DIR=$2
RVC_FIT=$3
DESCR_FIT=$4
BOOT_REPS=$5
JOINT=${6:-0}
MOD_RECOV=${7:-0}
LOSS=${8:-2}

if [ "$EXP_DIR" = "V1/" ]; then
  # V1/ -- vec F1 adjustment with full dataset
  if [ $RVC_FIT -eq 1 ]; then
    ## RVCs ONLY with NO phase adjustment (instead, vector correction for F1)
    # -- Naka-Rushton
    python3.6 descr_fits.py $CELL 0 V1/ -1 1 0 1 0 0 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV 
    python3.6 descr_fits.py $CELL 1 V1/ -1 1 0 1 0 0 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV
    python3.6 descr_fits.py $CELL 2 V1/ -1 1 0 1 0 0 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV
    python3.6 descr_fits.py $CELL 3 V1/ -1 1 0 1 0 0 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV
    # -- Movshon RVC
    python3.6 descr_fits.py $CELL 0 V1/ -1 1 0 0 0 0 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV
    python3.6 descr_fits.py $CELL 1 V1/ -1 1 0 0 0 0 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV
    python3.6 descr_fits.py $CELL 2 V1/ -1 1 0 0 0 0 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV
    python3.6 descr_fits.py $CELL 3 V1/ -1 1 0 0 0 0 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV
  fi
  if [ $DESCR_FIT -eq 1 ]; then
    # then, just SF tuning (again, vec corr. for F1, not phase adjustment);
    # -- responses derived from vecF1 corrections, if F1 responses
    #python3.6 descr_fits.py $CELL 0 V1/ -1 0 0 1 1 0 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV # flex gauss
    #python3.6 descr_fits.py $CELL 0 V1/ -1 0 0 1 1 0 4 $BOOT_REPS $JOINT 0 $MOD_RECOV # flex gauss, sach loss (to account for variability)
    #python3.6 descr_fits.py $CELL 0 V1/ -1 0 0 1 1 3 4 $BOOT_REPS $JOINT 0 $MOD_RECOV # d-DoG-S, sach loss (to account for variability)
    #python3.6 descr_fits.py $CELL 0 V1/ -1 0 0 1 1 3 4 $BOOT_REPS $JOINT 0 $MOD_RECOV # d-DoG-S, sach loss
    #python3.6 descr_fits.py $CELL 0 V1/ -1 0 0 1 1 5 4 $BOOT_REPS $JOINT 0 $MOD_RECOV # d-DoG-S Hawk, sachloss
    python3.6 descr_fits.py $CELL 0 V1/ -1 0 0 1 1 3 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV # d-DoG-S, sqrt loss
    #python3.6 descr_fits.py $CELL 0 V1/ -1 0 0 1 1 5 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV # d-DoG-S HAWK, sqrt loss
    #python3.6 descr_fits.py $CELL 0 V1/ -1 0 0 1 1 2 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV # Tony DoG
    #python3.6 descr_fits.py $CELL 0 V1/ -1 0 0 1 1 1 $LOSS $BOOT_REPS $JOINT 0 $MOD_RECOV # sach DoG
  fi
fi

if [ "$EXP_DIR" = "V1_BB/" ]; then
  python3.6 descr_fits_sfBB.py $CELL $RVC_FIT $DESCR_FIT 1 3 $LOSS $BOOT_REPS $JOINT
fi


if [ "$EXP_DIR" = "V1_orig/" ]; then
  if [ $RVC_FIT -eq 1 ]; then
    # V1_orig/ -- rvc_f0 and descr only
    python3.6 descr_fits.py $CELL 0 V1_orig/ -1 0 1 1 0 0 $LOSS $BOOT_REPS $JOINT
  fi
  wait
  if [ $DESCR_FIT -eq 1 ]; then
    # then, just SF tuning (again, vec corr. for F1, not phase adjustment);
    python3.6 descr_fits.py $CELL 0 V1_orig/ -1 0 0 1 1 3 $LOSS $BOOT_REPS $JOINT # d-DoG-S
    #python3.6 descr_fits.py $CELL 0 V1_orig/ -1 0 0 1 1 5 $LOSS $BOOT_REPS $JOINT # d-DoG-S - Hawk
    #python3.6 descr_fits.py $CELL 0 V1_orig/ -1 0 0 1 1 0 $LOSS $BOOT_REPS $JOINT # flex. gauss
    #python3.6 descr_fits.py $CELL 0 V1_orig/ -1 0 0 1 1 0 4 $BOOT_REPS $JOINT  # flex. gauss, sach loss
    #python3.6 descr_fits.py $CELL 0 V1_orig/ -1 0 0 1 1 2 $LOSS $BOOT_REPS $JOINT # Tony DoG
    #python3.6 descr_fits.py $CELL 0 V1_orig/ -1 0 0 1 1 1 $LOSS $BOOT_REPS $JOINT # sach DoG
  fi
fi

if [ "$EXP_DIR" = "altExp/" ]; then
  if [ $RVC_FIT -eq 1 ]; then
    # altExp/ -- rvc_f0 and descr only
    python3.6 descr_fits.py $CELL 0 altExp/ -1 0 1 1 0 0 $LOSS $BOOT_REPS $JOINT
  fi
  wait
  if [ $DESCR_FIT -eq 1 ]; then
    python3.6 descr_fits.py $CELL 0 altExp/ -1 0 0 1 1 3 $LOSS $BOOT_REPS $JOINT # d-DoG-S
    # then, just SF tuning (again, vec corr. for F1, not phase adjustment);
    #python3.6 descr_fits.py $CELL 0 altExp/ -1 0 0 1 1 0 $LOSS $BOOT_REPS $JOINT # flex. gauss
    #python3.6 descr_fits.py $CELL 0 altExp/ -1 0 0 1 1 0 4 $BOOT_REPS $JOINT # flex. gauss, sach loss
    #python3.6 descr_fits.py $CELL 0 altExp/ -1 0 0 1 1 2 $LOSS $BOOT_REPS $JOINT # Tony DoG
    #python3.6 descr_fits.py $CELL 0 altExp/ -1 0 0 1 1 1 $LOSS $BOOT_REPS $JOINT # sach DoG

  fi
fi

if [ "$EXP_DIR" = "LGN/" ]; then
  ## LGN - phase adjustment (will be done iff LGN/ 1; not if LGN/ 0 ) and F1 rvc
  if [ $RVC_FIT -eq 1 ]; then
    # phase adj
    python3.6 descr_fits.py $CELL 0 LGN/ 1 0 0 0 0 0 $LOSS $BOOT_REPS $JOINT
    # RVC (movshon)
    python3.6 descr_fits.py $CELL 0 LGN/ 0 1 0 0 0 0 $LOSS $BOOT_REPS $JOINT
    python3.6 descr_fits.py $CELL 1 LGN/ 0 1 0 0 0 0 $LOSS $BOOT_REPS $JOINT
    python3.6 descr_fits.py $CELL 2 LGN/ 0 1 0 0 0 0 $LOSS $BOOT_REPS $JOINT
    python3.6 descr_fits.py $CELL 3 LGN/ 0 1 0 0 0 0 $LOSS $BOOT_REPS $JOINT
    # RVC (Naka-Rushton)
    python3.6 descr_fits.py $CELL 0 LGN/ 0 1 0 1 0 0 $LOSS $BOOT_REPS $JOINT
    python3.6 descr_fits.py $CELL 1 LGN/ 0 1 0 1 0 0 $LOSS $BOOT_REPS $JOINT
    python3.6 descr_fits.py $CELL 2 LGN/ 0 1 0 1 0 0 $LOSS $BOOT_REPS $JOINT
    python3.6 descr_fits.py $CELL 3 LGN/ 0 1 0 1 0 0 $LOSS $BOOT_REPS $JOINT
  fi
  wait
  if [ $DESCR_FIT -eq 1 ]; then
    # Descr fits (based on Movshon RVCs)   
    ### with model recovery
    python3.6 descr_fits.py $CELL 0 LGN/ 0 0 0 0 1 1 $LOSS $BOOT_REPS $JOINT 1 $MOD_RECOV # sach DoG, sqrt
  fi
  wait
fi