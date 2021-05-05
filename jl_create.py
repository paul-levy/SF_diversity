import numpy as np
import os
import helper_fcns as hf
import scipy.stats as ss
from scipy.stats.mstats import gmean
from scipy.stats import ks_2samp, kstest, linregress
import itertools

#'''
########################
#### V1
########################
# expDirs (and expNames must always be of the right length, i.e. specify for each expt dir 
## V1 version
expDirs = ['V1_orig/', 'altExp/', 'V1/']
expNames = ['dataList.npy', 'dataList.npy', 'dataList_glx.npy']

nExpts = len(expDirs);

# these are usually same for all expts...we'll "tile" below
pytorch_mod = 1; #
excType, lossType = 2, 1
vecCorrected = 1
useHPCfit = 1;
normA, normB = 5, 1; # for weighted, 5 is wghtGain (2 is "old" weighted model)
lgnA, lgnB = 1, 1; # (1) means have an LGN, original filters
conA, conB = 1, 1; # (1) separate M&P; (2) is equal M+P; (4) is all parvo
loc_str = 'HPC' if useHPCfit else '';
fitBase = 'fitList%s_pyt_210331' % loc_str
fitNamesWght = [hf.fitList_name(fitBase, normA, lossType, lgnA, conA, vecCorrected, fixRespExp=None)]
fitNamesFlat = [hf.fitList_name(fitBase, normB, lossType, lgnB, conB, vecCorrected, fixRespExp=None)]
####
# descrFits - loss type determined by comparison (choose best; see modCompare.ipynb::Descriptive Fits)
####
dogMod = 2; # 1 (sach) or 2 (Tony)
dogNames = ['descrFits_210503_sqrt_tony.npy', 'descrFits_210503_sqrt_tony.npy', 'descrFits_210503_sqrt_tony.npy'];
#dogNames = ['descrFits_210304_sqrt_sach.npy', 'descrFits_210304_sqrt_sach.npy', 'descrFits_210304_sqrt_sach.npy'];
descrMod = 0; # which model for the diff. of gauss fits (0/1/2: flex/sach/tony)
descrNames = ['descrFits_210304_sqrt_flex.npy', 'descrFits_210304_sqrt_flex.npy', 'descrFits_210304_sqrt_flex.npy'];
#descrNames = ['descrFits_190503_sqrt_flex.npy', 'descrFits_190503_sqrt_flex.npy', 'descrFits_191023_sqrt_flex.npy'];

rvcNames = ['rvcFits_210304_f0_NR.npy', 'rvcFits_210304_f0_NR.npy', 'rvcFits_210304_vecF1_NR.npy'];
#rvcNames = ['rvcFits_191023_f0_NR.npy', 'rvcFits_191023_f0_NR.npy', 'rvcFits_191023_NR_pos.npy'];
rvcMods = [1,1,1]; # 0-mov; 1-Nakarushton; 2-Peirce
# rvcNames   = ['rvcFits_f0.npy'];
# pack to easily tile
expt = [expDirs, expNames, fitNamesWght, fitNamesFlat, descrNames, dogNames, rvcNames, rvcMods];
for exp_i in range(len(expt)):
    if len(expt[exp_i]) == 1:
        expt[exp_i] = expt[exp_i] * nExpts;
# now unpack for use
expDirs, expNames, fitNamesWght, fitNamesFlat, descrNames, dogNames, rvcNames, rvcMods = expt;

base_dir = os.getcwd() + '/';


###
# what do we want to track for each cell?
jointList = []; # we'll pack dictionaries in a list...

#### these are now defaults in hf.jl_create - but here, nonetheless, for reference!

# any parameters we need for analysis below?
varExplThresh = 70; # i.e. only include if the fit explains >X (e.g. 75)% variance
dog_varExplThresh = 70; # i.e. only include if the fit explains >X (e.g. 75)% variance

sf_range = [0.1, 10]; # allowed values of 'mu' for fits - see descr_fit.py for details

conDig = 1; # i.e. round to nearest tenth (1 decimal place)
rawInd = 0; # for accessing ratios/differences that we pass into diffsAtThirdCon

muLoc = 2; # prefSF is in location '2' of parameter arrays

# NOTE: the real code for creating the jointList has been moved to helper_fcns!
# WARNING: This takes [~/<]10 minutes (as of 20.04.14)
# jointList_V1full = hf.jl_create(base_dir, [expDirs[-1]], [expNames[-1]], [fitNamesWght[-1]], [fitNamesFlat[-1]], [descrNames[-1]], [dogNames[-1]], [rvcNames[-1]], [rvcMods[-1]])

jointList = hf.jl_create(base_dir, expDirs, expNames, fitNamesWght, fitNamesFlat, descrNames, dogNames, rvcNames, rvcMods, varExplThresh=varExplThresh, dog_varExplThresh=dog_varExplThresh, descrMod=descrMod, dogMod=dogMod)

from datetime import datetime
suffix = datetime.today().strftime('%y%m%d')
#suffix = '210504'

np.save(base_dir + 'jointList_V1_wMods_%s_vT%d_dvT%d' % (suffix, varExplThresh, dog_varExplThresh), jointList)

########################
#### END V1
########################
#'''
'''

########################
#### LGN
########################

# expDirs (and expNames must always be of the right length, i.e. specify for each expt dir 
### LGN version
#expDirs = ['LGN/']
#expNames = ['dataList.npy']
expDirs = ['LGN/', 'LGN/sach/'];
expNames = ['dataList.npy', 'sachData.npy']
#expDirs = ['LGN/sach/'];
#expNames = ['sachData.npy']

nExpts = len(expDirs);

# these are usually same for all expts...we'll "tile" below
# fitBase = 'fitList_190502cA';
fitBase = 'fitList_191023c';
#fitBase = 'fitList_210304';
fitNamesWght = ['%s_wght_chiSq.npy' % fitBase];
fitNamesFlat = ['%s_flat_chiSq.npy' % fitBase];
####
# descrFits - loss type determined by comparison (choose best; see modCompare.ipynb::Descriptive Fits)
####
#dogNames = ['descrFits_s210304_sach_sach.npy'];
#descrNames = ['descrFits_s210304_sqrt_flex.npy'];
dogNames = ['descrFits_210503_sqrt_tony.npy', 'descrFits_s210304_sqrt_tony.npy'];
#dogNames = ['descrFits_210304_sach_sach.npy', 'descrFits_s210304_sach_sach.npy'];
descrNames = ['descrFits_210304_sqrt_flex.npy', 'descrFits_s210304_sqrt_flex.npy'];
#dogNames = ['descrFits_191023_sach_sach.npy'];
#descrNames = ['descrFits_200507_sqrt_flex.npy'];

#rvcNames = ['rvcFits_191023_pos.npy']; 
#rvcMods = [0]; # 0-mov (blank); 1-Nakarushton (NR); 2-Peirce (peirce)
rvcNames = ['rvcFits_210304_pos.npy', 'rvcFits_210304.npy']; 
rvcMods = [0,0]; # 0-mov (blank); 1-Nakarushton (NR); 2-Peirce (peirce)
#rvcNames = ['rvcFits_210304.npy']; 
#rvcMods = [0]; # 0-mov (blank); 1-Nakarushton (NR); 2-Peirce (peirce)

# pack to easily tile
expt = [expDirs, expNames, fitNamesWght, fitNamesFlat, descrNames, dogNames, rvcNames];
for exp_i in range(len(expt)):
    if len(expt[exp_i]) == 1:
        expt[exp_i] = expt[exp_i] * nExpts;
# now unpack for use
expDirs, expNames, fitNamesWght, fitNamesFlat, descrNames, dogNames, rvcNames = expt;

base_dir = os.getcwd() + '/';

#####
# what do we want to track for each cell?
jointList = []; # we'll pack dictionaries in a list...

#### these are now defaults in hf.jl_create - but here, nonetheless, for reference!

# any parameters we need for analysis below?
varExplThresh = 70; # i.e. only include if the fit explains >X (e.g. 75)% variance
dog_varExplThresh = 70; # i.e. only include if the fit explains >X (e.g. 75)% variance

sf_range = [0.01, 10]; # allowed values of 'mu' for fits - see descr_fit.py for details

# NOTE: the real code for creating the jointList has been moved to helper_fcns!
# WARNING: This takes ~10 minutes (as of 09.06.19)
jointList = hf.jl_create(base_dir, expDirs, expNames, fitNamesWght, fitNamesFlat, descrNames, dogNames, rvcNames, rvcMods, dog_varExplThresh=dog_varExplThresh)

from datetime import datetime
suffix = datetime.today().strftime('%y%m%d')

np.save(base_dir + 'jointList_LGN_%s_vT%d_dvT%d' % (suffix, varExplThresh, dog_varExplThresh), jointList)

'''
