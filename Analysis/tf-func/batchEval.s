#!/bin/bash
#SBATCH --time=8:00:00
#SBATCH --mem=8GB

#SBATCH --job-name=evalModFlat

#SBATCH --mail-user=pl1465@nyu.edu
#SBATCH --mail-type=ALL

#SBATCH --output=tfHf_%A_%a.out
#SBATCH --error=tfHf_%A_%a.err

module purge
source /home/pl1465/SF_diversity/Analysis/tf2.7/python2.7.12/bin/activate

# params are: cellNum, stopThresh, learning rate, lossType, fitType, subset_frac, initFromCurr, collapseSF
#   lossType:
#     1 - sqrt
#     2 - poisson
#     3 - modPoiss
#   fitType:
#     1 - flat normalization
#     2 - gaussian weighting of norm responses
#     3 - (flexible) gaussian c50 filter
#   subset_frac = 0 means take all data (no subsampling)
#   collapseSF - if 1, then only holding out 10 "conditions" (group all SFS for given conXdisp together)
python evalModel.py $SLURM_ARRAY_TASK_ID 1e-4 0.1 3 1 1 0 1
 
# leave a blank line at the end
