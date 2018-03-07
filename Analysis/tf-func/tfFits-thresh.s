#!/bin/bash

#SBATCH --time=15:00:00
#SBATCH --mem=4GB

#SBATCH --job-name=princeTF

#SBATCH --mail-user=pl1465@nyu.edu
#SBATCH --mail-type=ALL

#SBATCH --output=tf_%A_%a.out
#SBATCH --error=tf_%A_%a.err

module purge
source /home/pl1465/SF_diversity/Analysis/tf2.7/python2.7.12/bin/activate

# params are: cellNum, stopThresh, learning rate, fitType, subset_frac, initFromCurr
#   fitType:
#     1 - sqrt
#     2 - poisson
#     3 - modPoiss
#   subset_frac = 0 means take all data (no subsampling)
python mod_resp_trackNLL.py $SLURM_ARRAY_TASK_ID 1e-8 0.1 1 0.10 0
 
# leave a blank line at the end

