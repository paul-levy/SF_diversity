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

# cellNum errThresh learningRate subsampleRate paramsFromCurrFits
python mod_resp_trackNLL.py $SLURM_ARRAY_TASK_ID 1e-7 0.001 0.1 0
 
# leave a blank line at the end

