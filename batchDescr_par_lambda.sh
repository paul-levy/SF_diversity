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
#   [14 - regularization for gain term (>0 means penalize for high gain)] default is 0

### GUIDE (as of 19.11.05)
# V1/ - use dataList_glx.npy, was 35 cells -- now 56 (as of m681)
# V1/ - model recovery (dataList_glx_mr; mr_fitList...), 10 cells
# V1_orig/ - model recovery (dataList_mr; mr_fitList...), 10 cells
# V1_orig/ - standard, 59 cells
# altExp   - standard, 8 cells
# LGN/ - standard, 88 cells (as of 21.05.24)

source activate lcv-python

########
### NOTES: 
###   If running only SF descr or RVC-f0 fits, do not need to run separately for all disp
###   
########

EXP_DIR=$1
RVC_FIT=$2
DESCR_FIT=$3
BOOT_REPS=$4

if [ "$EXP_DIR" = "V1/" ]; then
  # V1/ -- vec F1 adjustment with full dataset
  if [[ $RVC_FIT -eq 1 ]]; then
    ## RVCs ONLY with NO phase adjustment (instead, vector correction for F1)
    # -- Naka-Rushton
    python3.6 descr_fits.py -181 0 V1/ -1 1 0 1 0 0 2 $BOOT_REPS 0 0 
    python3.6 descr_fits.py -181 1 V1/ -1 1 0 1 0 0 2 $BOOT_REPS 0 0
    python3.6 descr_fits.py -181 2 V1/ -1 1 0 1 0 0 2 $BOOT_REPS 0 0
    python3.6 descr_fits.py -181 3 V1/ -1 1 0 1 0 0 2 $BOOT_REPS 0 0
    # -- Movshon RVC
    python3.6 descr_fits.py -181 0 V1/ -1 1 0 0 0 0 2 $BOOT_REPS 0 0
    python3.6 descr_fits.py -181 1 V1/ -1 1 0 0 0 0 2 $BOOT_REPS 0 0
    python3.6 descr_fits.py -181 2 V1/ -1 1 0 0 0 0 2 $BOOT_REPS 0 0
    python3.6 descr_fits.py -181 3 V1/ -1 1 0 0 0 0 2 $BOOT_REPS 0 0
  fi
  if [[ $DESCR_FIT -eq 1 ]]; then
    # then, just SF tuning (again, vec corr. for F1, not phase adjustment);
    # -- responses derived from vecF1 corrections, if F1 responses
    python3.6 descr_fits.py -181 0 V1/ -1 0 0 1 1 0 2 $BOOT_REPS 0 0 # flex gauss
    python3.6 descr_fits.py -181 0 V1/ -1 0 0 1 1 0 4 $BOOT_REPS 0 0 # flex gauss, sach loss (to account for variability)
    python3.6 descr_fits.py -181 0 V1/ -1 0 0 1 1 3 4 $BOOT_REPS 0 0 # d-DoG-S, sach loss (to account for variability)
    python3.6 descr_fits.py -181 0 V1/ -1 0 0 1 1 3 2 $BOOT_REPS 0 0 # d-DoG-S, sqrt loss
    python3.6 descr_fits.py -181 0 V1/ -1 0 0 1 1 2 2 $BOOT_REPS 0 0 # Tony DoG
    #python3.6 descr_fits.py -181 0 V1/ -1 0 0 1 1 1 2 $BOOT_REPS 0 0 # sach DoG
  fi
fi

if [ "$EXP_DIR" = "V1_orig/" ]; then
  if [[ $RVC_FIT -eq 1 ]]; then
    # V1_orig/ -- rvc_f0 and descr only
    python3.6 descr_fits.py -159 0 V1_orig/ -1 0 1 1 0 0 2 $BOOT_REPS 0
  fi
  wait
  if [[ $DESCR_FIT -eq 1 ]]; then
    # then, just SF tuning (again, vec corr. for F1, not phase adjustment);
    python3.6 descr_fits.py -159 0 V1_orig/ -1 0 0 1 1 0 2 $BOOT_REPS 0 # flex. gauss
    python3.6 descr_fits.py -159 0 V1_orig/ -1 0 0 1 1 0 4 $BOOT_REPS 0  # flex. gauss, sach loss
    python3.6 descr_fits.py -159 0 V1_orig/ -1 0 0 1 1 2 2 $BOOT_REPS 0 # Tony DoG
    #python3.6 descr_fits.py -159 0 V1_orig/ -1 0 0 1 1 1 2 $BOOT_REPS 0 # sach DoG
  fi
fi

if [ "$EXP_DIR" = "altExp/" ]; then
  if [[ $RVC_FIT -eq 1 ]]; then
    # altExp/ -- rvc_f0 and descr only
    python3.6 descr_fits.py -108 0 altExp/ -1 0 1 1 0 0 2 $BOOT_REPS 0
  fi
  wait
  if [[ $DESCR_FIT -eq 1 ]]; then
    # then, just SF tuning (again, vec corr. for F1, not phase adjustment);
    python3.6 descr_fits.py -108 0 altExp/ -1 0 0 1 1 0 2 $BOOT_REPS 0 # flex. gauss
    python3.6 descr_fits.py -108 0 altExp/ -1 0 0 1 1 0 4 $BOOT_REPS 0 # flex. gauss, sach loss
    python3.6 descr_fits.py -108 0 altExp/ -1 0 0 1 1 2 2 $BOOT_REPS 0 # Tony DoG
    #python3.6 descr_fits.py -108 0 altExp/ -1 0 0 1 1 1 2 $BOOT_REPS 0 # sach DoG

  fi
fi

if [ "$EXP_DIR" = "LGN/" ]; then
  ## LGN - phase adjustment (will be done iff LGN/ 1; not if LGN/ 0 ) and F1 rvc
  if [[ $RVC_FIT -eq 1 ]]; then
    # phase adj
    python3.6 descr_fits.py -181 0 LGN/ 1 0 0 0 0 0 3 $BOOT_REPS 0
    # RVC (movshon)
    python3.6 descr_fits.py -181 0 LGN/ 0 1 0 0 0 0 3 $BOOT_REPS 0
    python3.6 descr_fits.py -181 1 LGN/ 0 1 0 0 0 0 3 $BOOT_REPS 0
    python3.6 descr_fits.py -181 2 LGN/ 0 1 0 0 0 0 3 $BOOT_REPS 0
    python3.6 descr_fits.py -181 3 LGN/ 0 1 0 0 0 0 3 $BOOT_REPS 0
    # RVC (Naka-Rushton)
    python3.6 descr_fits.py -181 0 LGN/ 0 1 0 1 0 0 3 $BOOT_REPS 0
    python3.6 descr_fits.py -181 1 LGN/ 0 1 0 1 0 0 3 $BOOT_REPS 0
    python3.6 descr_fits.py -181 2 LGN/ 0 1 0 1 0 0 3 $BOOT_REPS 0
    python3.6 descr_fits.py -181 3 LGN/ 0 1 0 1 0 0 3 $BOOT_REPS 0
  fi
  wait
  if [[ $DESCR_FIT -eq 1 ]]; then
    # Descr fits (based on Movshon RVCs)
    #python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 0 4 $BOOT_REPS 0 1 # flex gauss, not joint; sach loss
    #python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 0 2 $BOOT_REPS 0 1 # flex gauss, not joint
    #python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 # sach DoG, not joint (sach loss)
    #python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 # sach DoG, not joint (sqrt)
    #python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 2 2 $BOOT_REPS 0 1 # Tony DoG, not joint (sqrt)
      
    if [[ $BOOT_REPS -eq 0 ]]; then
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 # sach DoG, not joint (sqrt)
    else
      # cross-val - 
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0 # sach DoG, not joint (sqrt)
      # cross-val - 
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0.01 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0.01 # sach DoG, not joint (sqrt)
      # cross-val - 
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0.02 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0.02 # sach DoG, not joint (sqrt)
      # cross-val - 
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0.04 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0.04 # sach DoG, not joint (sqrt)
      # cross-val - 
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0.05 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0.05 # sach DoG, not joint (sqrt)
      # cross-val
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0.1 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0.1 # sach DoG, not joint (sqrt)
      # cross-val
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0.4 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0.4 # sach DoG, not joint (sqrt)
      # cross-val
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0.2 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0.2 # sach DoG, not joint (sqrt)
      # cross-val
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0.5 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0.5 # sach DoG, not joint (sqrt)
      # cross-val
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0.15 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0.15 # sach DoG, not joint (sqrt)
      # cross-val
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 4 $BOOT_REPS 0 1 1 0.30 # sach DoG, not joint (sach loss)
      python3.6 descr_fits.py -181 0 LGN/ 0 0 0 0 1 1 2 $BOOT_REPS 0 1 1 0.30 # sach DoG, not joint (sqrt)
    fi
    wait
  fi
fi
