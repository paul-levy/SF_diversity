#!/bin/bash

### README
# have you set the dataList name?
# have you set the fitList base name?
# have you set the directory (below)
### see plot_simple.py for changes/details

# second param is loss_type:
	# 1 - square root
	# 2 - poisson
	# 3 - modulated poission
	# 4 - chi squared
# third param is expDir (e.g. V1/ or LGN/)
# fourth param is f0/f1 (i.e. load rvcFits?)
# fifth param is diffPlot (i.e. plot everything relative to flat model prediction)
# sixth param is std/sem as variance measure: (1 sem (default))

source activate lcv-python

for run in {1..17}
do
  python plot_compare.py $run 4 V1/ 0 0 1 &
done

# leave a blank line at the end
