# coding: utf-8

import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg') # to avoid GUI/cluster issues...
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf as pltSave
import seaborn as sns
sns.set(style='ticks')
from scipy.stats import poisson, nbinom
from scipy.stats.mstats import gmean

import helper_fcns as hf
import model_responses as mod_resp
import helper_fcns_sfBB as hf_sf
import model_responses_pytorch as mrpt

import warnings
warnings.filterwarnings('once');

import pdb

# using fits where the filter sigma is sigmoid?
_sigmoidRespExp = None; # 3 or None, as of 21.03.14
_sigmoidSigma = 5; # put a value (5, as of 21.03.10) or None (see model_responses_pytorch.py for details)
_sigmoidGainNorm = 5;
_applyLGNtoNorm = 1;
#_applyLGNtoNorm = 0;
recenter_norm = 0;
#recenter_norm = 3;
#singleGratsOnly = True;
singleGratsOnly = False;

save_varExpl = False; # save varExpl to the model fit?

f1_expCutoff = 2; # if 1, then all but V1_orig/ are allowed to have F1; if 2, then altExp/ is also excluded

force_full = 1;

plt.style.use('https://raw.githubusercontent.com/paul-levy/SF_diversity/master/paul_plt_style.mplstyle');
from matplotlib import rcParams
# TODO: migrate this to actual .mplstyle sheet
rcParams['font.size'] = 20;
rcParams['pdf.fonttype'] = 42 # should be 42, but there are kerning issues
rcParams['ps.fonttype'] = 42 # should be 42, but there are kerning issues
rcParams['lines.linewidth'] = 2.5;
rcParams['lines.markeredgewidth'] = 0; # remove edge??
rcParams['axes.linewidth'] = 1.5;
rcParams['lines.markersize'] = 12; # 8 is the default
rcParams['font.style'] = 'oblique';

rcParams['xtick.major.size'] = 25
rcParams['xtick.minor.size'] = 12
rcParams['ytick.major.size'] = 25
rcParams['ytick.minor.size'] = 0; # i.e. don't have minor ticks on y...

rcParams['xtick.major.width'] = 2
rcParams['xtick.minor.width'] = 2
rcParams['ytick.major.width'] = 2
rcParams['ytick.minor.width'] = 0

minorWid, minorLen = 2, 12;
majorWid, majorLen = 5, 25;

clip_on = True

cellNum  = int(sys.argv[1]);
excType  = int(sys.argv[2]);
lossType = int(sys.argv[3]);
expDir   = sys.argv[4]; 
normTypesIn = int(sys.argv[5]); # two-digit number, extracting 1st for modA, 2nd for modB
conTypesIn = int(sys.argv[6]); # two-digit number, extracting 1st for modA, 2nd for modB
lgnFrontEnd = int(sys.argv[7]); # two-digit number, extracting 1st for modA, 2nd for modB
rvcAdj   = int(sys.argv[8]); # if 1, then let's load rvcFits to adjust responses to F1; 0 means no rvcFits; -1 means vector F1 math
rvcMod   = int(sys.argv[9]); # 0/1/2 (see hf.rvc_fit_name)
diffPlot = int(sys.argv[10]);
intpMod  = int(sys.argv[11]);
kMult  = float(sys.argv[12]); # only applies for lossType=4

if len(sys.argv) > 13:
  fixRespExp = float(sys.argv[13]);
  if fixRespExp <= 0: # this is the code to not fix the respExp
    fixRespExp = None;
else:
  fixRespExp = None; # default (see modCompare.ipynb for details)

if len(sys.argv) > 14:
  respVar = int(sys.argv[14]);
else:
  respVar = 1;

if len(sys.argv) > 15:
  pytorch_mod = int(sys.argv[15]);
  newMethod = 1; # we are now using the newer method of computing the response in mrpt
  respMeasure = None; # allow it to be done based on F1:F0 ratio for now...
  # - we'll only need newMethod if pytorch_mod is 1
else:
  pytorch_mod = 0; # default, we don't use the pytorch model
  newMethod = None;

if len(sys.argv) > 16:
  useHPCfit = int(sys.argv[16]);
else:
  useHPCfit = 0;

if len(sys.argv) > 17:
  whichKfold = int(sys.argv[17]);
  if whichKfold<0:
    whichKfold = None
else:
  whichKfold = None;

if len(sys.argv) > 18: # norm weights determined with deriv. Gauss or log Gauss?
  dgNormFuncIn=int(sys.argv[18]);
else:
  dgNormFuncIn=0

isCV = False if whichKfold is None else True;

## used for interpolation plot
sfSteps  = 45; # i.e. how many steps between bounds of interest
conSteps = -1;
#nRpts    = 100; # how many repeats for stimuli in interpolation plot?
nRpts    = 5; # how many repeats for stimuli in interpolation plot?
#nRpts    = 3000; # how many repeats for stimuli in interpolation plot? USE FOR PUBLICATION/PRESENTATION QUALITY, but SLOW
nRptsSingle = 5; # when disp = 1 (which is most cases), we do not need so many interpolated points

loc_base = os.getcwd() + '/';
data_loc = loc_base + expDir + 'structures/';
save_loc = loc_base + expDir + 'figures/';

if 'pl1465' in loc_base or useHPCfit:
  loc_str = 'HPC';
else:
  loc_str = '';

if _sigmoidRespExp is not None:
  rExpStr = 're';
else:
  rExpStr = '';

### DATALIST
expName = hf.get_datalist(expDir, force_full=force_full, new_v1=True);
### FITLIST
# -- some params are sigmoid, we'll use this to unpack the true parameter
_sigmoidScale = 10
_sigmoidDord = 5;

fitBase = 'fitList%s_pyt_nr230118a_noRE_noSched%s' % (loc_str, '_sg' if singleGratsOnly else '')
#fitBase = 'fitList%s_pyt_nr230210qn_noRE_noSched%s' % (loc_str, '_sg' if singleGratsOnly else '')

rvcDir = 1;
vecF1 = 0;

if pytorch_mod == 1 and rvcAdj == -1:
  vecCorrected = 1;
else:
  vecCorrected = 0;

### RVCFITS
rvcBase = 'rvcFits%s_220928' % loc_str; # direc flag & '.npy' are added

### Model types
# 0th: Unpack the norm types, con types, lgnTypes, and (as of 23.01.18) whether we use deriv. Gauss norm weighting or log Gauss (default)
normA, normB = int(np.floor(normTypesIn/10)), np.mod(normTypesIn, 10)
conA, conB = int(np.floor(conTypesIn/10)), np.mod(conTypesIn, 10)
lgnA, lgnB = int(np.floor(lgnFrontEnd/10)), np.mod(lgnFrontEnd, 10)
dgnfA, dgnfB = int(np.floor(dgNormFuncIn/10)), np.mod(dgNormFuncIn, 10)
fitNameA = hf.fitList_name(fitBase, normA, lossType, lgnA, conA, vecCorrected, fixRespExp=fixRespExp, kMult=kMult, excType=excType, CV=isCV, lgnForNorm=_applyLGNtoNorm, dgNormFunc=dgnfA)
fitNameB = hf.fitList_name(fitBase, normB, lossType, lgnB, conB, vecCorrected, fixRespExp=fixRespExp, kMult=kMult, excType=excType, CV=isCV, lgnForNorm=_applyLGNtoNorm, dgNormFunc=dgnfB)
# what's the shorthand we use to refer to these models...
aWtStr = '%s%s' % ('wt' if normA>1 else 'asym', '' if normA<=2 else 'Gn' if normA==5 else 'Yk' if normA==6 else 'Mt');
bWtStr = '%s%s' % ('wt' if normB>1 else 'asym', '' if normB<=2 else 'Gn' if normB==5 else 'Yk' if normB==6 else 'Mt');
aWtStr = '%s%s' % ('DG' if dgnfA==1 else '', aWtStr);
bWtStr = '%s%s' % ('DG' if dgnfB==1 else '', bWtStr);
lgnStrA = hf.lgnType_suffix(lgnA, conA);
lgnStrB = hf.lgnType_suffix(lgnB, conB);
modA_str = '%s%s' % ('fl' if normA==1 else aWtStr, lgnStrA if lgnA>0 else 'V1');
modB_str = '%s%s' % ('fl' if normB==1 else bWtStr, lgnStrB if lgnB>0 else 'V1');

# set the save directory to save_loc, then create the save directory if needed
lossSuf = hf.lossType_suffix(lossType).replace('.npy', ''); # get the loss suffix, remove the file type ending
excType_str = hf.excType_suffix(excType);
if diffPlot == 1:
  compDir  = str(fitBase + '_diag%s_%s_%s' % (excType_str, modA_str, modB_str) + lossSuf + '/diff');
else:
  compDir  = str(fitBase + '_diag%s_%s_%s' % (excType_str, modA_str, modB_str) + lossSuf);
if intpMod == 1:
  compDir = str(compDir + '/intp');
subDir   = compDir.replace('fitList', 'fits').replace('.npy', '');
save_loc = str(save_loc + subDir + '%s/' % ('' if _applyLGNtoNorm else '_nn'));

conDig = 3; # round contrast to the 3rd digit

try: # keeping for backwards compatability
  dataList = np.load(str(data_loc + expName), encoding='latin1').item();
except:
  dataList = hf.np_smart_load(str(data_loc + expName))
fitListA = hf.np_smart_load(data_loc + fitNameA);
fitListB = hf.np_smart_load(data_loc + fitNameB);

print('modA: %s\nmodB: %s\n' % (fitNameA, fitNameB))

cellName = dataList['unitName'][cellNum-1];
try:
  cellType = dataList['unitType'][cellNum-1];
except: 
  # TODO: note, this is dangerous; though thus far, only V1 cells don't have 'unitType' field in dataList, so we can safely do this
  cellType = 'V1'; 

try: # keeping for backwards compatability
  expData  = np.load(str(data_loc + cellName + '_sfm.npy'), encoding='latin1').item();
except:
  expData  = hf.np_smart_load(str(data_loc + cellName + '_sfm.npy'));
expInd   = hf.exp_name_to_ind(dataList['expType'][cellNum-1]);
  
# #### Load model fits
# - pre-define the loss trajectory to be None
loss_traj_A  = None;
loss_traj_B = None;

if pytorch_mod == 1:
  if respMeasure is None and expInd > f1_expCutoff:
    f1f0_rat = hf.compute_f1f0(expData['sfm']['exp']['trial'], cellNum, expInd, loc_data=None)[0];
    respMeasure = int(f1f0_rat > 1);
  else:
    respMeasure = 0; # default to DC (since this might be an expt where we can only analyze DC)
  respStr = hf_sf.get_resp_str(respMeasure);
  modFit_A = fitListA[cellNum-1][respStr]['params'];
  modFit_B = fitListB[cellNum-1][respStr]['params'];
  loss_A = fitListA[cellNum-1][respStr]['NLL%s' % ('_train' if isCV else '')]
  loss_B = fitListB[cellNum-1][respStr]['NLL%s' % ('_train' if isCV else '')]
  if isCV:
    modFit_A = modFit_A[whichKfold]
    modFit_B = modFit_B[whichKfold]
    loss_A = np.mean(loss_A[whichKfold])
    loss_B = np.mean(loss_B[whichKfold])
    kstr = '_k%d' % whichKfold
  else:
    kstr = '';
  # load details, too, if possible
  try:
    try:
      fitDetailsA = hf.np_smart_load(data_loc + fitNameA.replace('.npy', '_details.npy'))
      loss_traj_A = fitDetailsA[cellNum-1][respStr]['loss'];
      loss_traj_A = np.array([np.mean(x) for x in loss_traj_A]); # why mean? in case batch_size < # trials
    except:
      pass; # it's ok, we've already pre-defined None
    try:
      fitDetailsB = hf.np_smart_load(data_loc + fitNameB.replace('.npy', '_details.npy'))
      loss_traj_B = fitDetailsB[cellNum-1][respStr]['loss'];
      loss_traj_B = np.array([np.mean(x) for x in loss_traj_B]); # why mean? in case batch_size < # trials
    except:
      pass
  except:
    pass
else:
  modFit_A = fitListA[cellNum-1]['params']; # 
  modFit_B = fitListB[cellNum-1]['params']; # 
  loss_A = fitListA[cellNum-1]['NLL']
  loss_B = fitListB[cellNum-1]['NLL']
modFits = [modFit_A, modFit_B];
normTypes = [normA, normB]; # weighted, then flat (typically, but NOT always)
lgnTypes = [lgnA, lgnB];
conTypes = [conA, conB];
dgnfTypes = [dgnfA, dgnfB];

# ### Organize data & model responses
# ---- first, if m
if pytorch_mod == 1:
  # get the correct, adjusted F1 response
  trialInf = expData['sfm']['exp']['trial'];
  if expInd > f1_expCutoff and respMeasure == 1:
    respOverwrite = hf.adjust_f1_byTrial(trialInf, expInd);
  else:
    respOverwrite = None;
# ---- DATA - organize data responses, first
_, stimVals, val_con_by_disp, validByStimVal, _ = hf.tabulate_responses(expData, expInd);
if rvcAdj >= 0:
  if rvcAdj == 1:
    rvcFlag = '';
    rvcFits = hf.get_rvc_fits(data_loc, expInd, cellNum, rvcName=rvcBase, rvcMod=rvcMod, direc=rvcDir, vecF1=vecF1);
    asRates = False; #True;
    force_dc = False
  elif rvcAdj == 0:
    rvcFlag = '_f0';
    rvcFits = hf.get_rvc_fits(data_loc, expInd, cellNum, rvcName='None');
    asRates = False;
    force_dc = True
  # rvcMod=-1 tells the function call to treat rvcName as the fits, already (we loaded above!)
  spikes_rate, meas = hf.get_adjusted_spikerate(expData['sfm']['exp']['trial'], cellNum, expInd, data_loc, rvcName=rvcFits, rvcMod=-1, descrFitName_f0=None, baseline_sub=False, return_measure=True, force_dc=force_dc);
elif rvcAdj == -1: # i.e. ignore the phase adjustment stuff...
  if respMeasure == 1 and expInd > f1_expCutoff:
    spikes_byComp = respOverwrite;
    # then, sum up the valid components per stimulus component
    allCons = np.vstack(expData['sfm']['exp']['trial']['con']).transpose();
    blanks = np.where(allCons==0);
    spikes_byComp[blanks] = 0; # just set it to 0 if that component was blank during the trial
    spikes_rate = np.sum(spikes_byComp, axis=1);
    asRates = False; # TODO: Figure out if really as rates or not...
    rvcFlag = '_f1';
  else:
    spikes_rate = hf.get_adjusted_spikerate(expData['sfm']['exp']['trial'], cellNum, expInd, data_loc, rvcName=None, force_dc=True, baseline_sub=False); 
    rvcFlag = '_f0';
    asRates = True;

print('got correct spike rates');

# #### determine contrasts, center spatial frequency, dispersions
# -- first, load varGain, since we'll need it just below if pytorch_mod==1, or later on otherwise (if lossType=3)
if lossType == 3: # i.e. modPoiss
  varGains  = [x[7] for x in modFits];
  if pytorch_mod: # then the real varGain value is sigmoid(varGain), i.e. 1/(1+exp(-varGain))
    varGains = [1/(1+np.exp(-x)) for x in varGains];
else:
  varGains = [-99, -99]; # just dummy values; won't be used unless losstype=3

if pytorch_mod == 1:
  ### now, set-up the two models
  model_A, model_B = [mrpt.sfNormMod(prms, expInd=expInd, excType=excType, normType=normType, lossType=lossType, newMethod=newMethod, lgnFrontEnd=lgnType, lgnConType=lgnCon, applyLGNtoNorm=_applyLGNtoNorm, toFit=False, normFiltersToOne=False, dgNormFunc=dgnfType) for prms,normType,lgnType,lgnCon,dgnfType in zip(modFits, normTypes, lgnTypes, conTypes, dgnfTypes)]
  # these values will be the same for all models
  minPrefSf, maxPrefSf = model_A.minPrefSf.detach().numpy(), model_A.maxPrefSf.detach().numpy()
  # -- package the model objects directly
  modelsAsObj = [model_A, model_B]
  # vvv respOverwrite defined above (None if DC or if expInd=-1)
  #dw = mrpt.dataWrapper(trialInf, respMeasure=respMeasure, expInd=expInd, respOverwrite=respOverwrite, shuffleTf=True)#, shufflePh=False);
  dw = mrpt.dataWrapper(trialInf, respMeasure=respMeasure, expInd=expInd, respOverwrite=respOverwrite);
  modResps = [mod.forward(dw.trInf, respMeasure=respMeasure, sigmoidSigma=_sigmoidSigma, recenter_norm=recenter_norm).detach().numpy() for mod in [model_A, model_B]];

  if respMeasure == 1: # make sure the blank components have a zero response (we'll do the same with the measured responses)
    blanks = np.where(dw.trInf['con']==0);
    modResps[0][blanks] = 0;
    modResps[1][blanks] = 0;
    # next, sum up across components
    modResps = [np.sum(mr, axis=1) for mr in modResps];
  # finally, make sure this fills out a vector of all responses (just have nan for non-modelled trials)
  nTrialsFull = len(trialInf['num']);
  mr_A = np.nan * np.zeros((nTrialsFull, ));
  mr_A[dw.trInf['num']] = modResps[0];
  mr_B = np.nan * np.zeros((nTrialsFull, ));
  mr_B[dw.trInf['num']] = modResps[1];
  modResps = [mr_A, mr_B];

  # organize responses so that we can package them for evaluating varExpl...
  _, _, expByCond, _ = hf.organize_resp(spikes_rate, trialInf, expInd);
  #_, _, expByCond, _ = hf.organize_resp(spikes_rate, trialInf, expInd, respsAsRate=asRates);
  stimDur = hf.get_exp_params(expInd).stimDur;
  # TODO: This is a work around for which measures are in rates vs. counts (DC vs F1, model vs data...)
  # --- but check V1/1 -- why is varExpl still bad????
  divFactor = stimDur if respMeasure == 0 else 1;
  _, _, modByCondA, _ = hf.organize_resp(np.divide(mr_A, divFactor), trialInf, expInd); # divFactor was previously stimDur
  _, _, modByCondB, _ = hf.organize_resp(np.divide(mr_B, divFactor), trialInf, expInd);

  # - and now compute varExpl - first for SF tuning curves, then for RVCs...
  nDisp, nSf, nCon = expByCond.shape;
  varExplSF_A = np.nan * np.zeros((nDisp, nCon));
  varExplSF_B = np.nan * np.zeros((nDisp, nCon));
  varExplCon_A = np.nan * np.zeros((nDisp, nSf));
  varExplCon_B = np.nan * np.zeros((nDisp, nSf));
  for dI in np.arange(nDisp):
    for sI in np.arange(nSf):
      varExplCon_A[dI, sI] = hf.var_explained(hf.nan_rm(expByCond[dI, sI, :]), hf.nan_rm(modByCondA[dI, sI, :]), None);
      varExplCon_B[dI, sI] = hf.var_explained(hf.nan_rm(expByCond[dI, sI, :]), hf.nan_rm(modByCondB[dI, sI, :]), None);
    for cI in np.arange(nCon):
      varExplSF_A[dI, cI] = hf.var_explained(hf.nan_rm(expByCond[dI, :, cI]), hf.nan_rm(modByCondA[dI, :, cI]), None);
      varExplSF_B[dI, cI] = hf.var_explained(hf.nan_rm(expByCond[dI, :, cI]), hf.nan_rm(modByCondB[dI, :, cI]), None);

  # save the varExpl in the fitList
  if save_varExpl:
    fitListA[cellNum-1][respStr]['varExpl_con'] = varExplCon_A
    fitListB[cellNum-1][respStr]['varExpl_con'] = varExplCon_B
    fitListA[cellNum-1][respStr]['varExpl_SF'] = varExplSF_A
    fitListB[cellNum-1][respStr]['varExpl_SF'] = varExplSF_B

  # and also get the blank resp
  modBlank_A = np.maximum(0, model_A.noiseLate.detach().numpy()/divFactor); # baseline 
  modBlank_B = np.maximum(0, model_B.noiseLate.detach().numpy()/divFactor); # baseline

  lossByCond_A = mrpt.loss_sfNormMod(mrpt._cast_as_tensor(mr_A), mrpt._cast_as_tensor(spikes_rate), lossType=lossType, varGain=mrpt._cast_as_tensor(varGains[0]), debug=1)[1].detach().numpy();
  lossByCond_B = mrpt.loss_sfNormMod(mrpt._cast_as_tensor(mr_B), mrpt._cast_as_tensor(spikes_rate), lossType=lossType, varGain=mrpt._cast_as_tensor(varGains[1]), debug=1)[1].detach().numpy();

elif pytorch_mod == 0:
  # SFMGiveBof returns spike counts per trial, NOT rates -- we will correct in hf.organize_resp call below
  # - to properly evaluate the loss, load rvcFits, mask the trials
  rvcCurr = hf.get_rvc_fits(data_loc, expInd, cellNum, rvcName=rvcBase, rvcMod=rvcMod);
  stimOr = np.vstack(expData['sfm']['exp']['trial']['ori']);
  mask = np.isnan(np.sum(stimOr, 0)); # sum over all stim components...if there are any nans in that trial, we know
  # - now compute SFMGiveBof!
  modResps = [mod_resp.SFMGiveBof(fit, expData, normType=norm, lossType=lossType, expInd=expInd, cellNum=cellNum, rvcFits=rvcCurr, excType=excType, maskIn=~mask, compute_varExpl=1, lgnFrontEnd=lgn) for fit, norm,lgn in zip(modFits, normTypes, lgnTypes)];
                                  
  # unpack the model fits!
  varExplSF_A = modResps[0][3];
  varExplSF_B = modResps[1][3];
  varExplCon_A = modResps[0][4];
  varExplCon_B = modResps[1][4];
  lossByCond_A = modResps[0][2];
  lossByCond_B = modResps[1][2]; # We only care about weighted...
  modResps = [x[1] for x in modResps]; # 1st return output (x[0]) is NLL (don't care about that here)

# Now, continue with organizing things
if normA > 1:
  gs_mean_A = model_A.transform_sigmoid_param('gs_mean')
  gs_std_A = model_A.transform_sigmoid_param('gs_std')
  #gs_mean_A = model_A.gs_mean.detach().numpy();
  #gs_std_A = model_A.gs_std.detach().numpy();
else:
  gs_mean_A, gs_std_A = None, None
if normB > 1 and normB != 4:
  gs_mean_B = model_B.transform_sigmoid_param('gs_mean')
  gs_std_B = model_B.transform_sigmoid_param('gs_std')
  #gs_mean_B = model_B.gs_mean.detach().numpy();
  #gs_std_B = model_B.gs_std.detach().numpy();
else:
  gs_mean_B, gs_std_B = None, None

# now organize the responses
orgs = [hf.organize_resp(np.divide(mr, divFactor), expData, expInd) for mr in modResps];
#orgs = [hf.organize_resp(mr, expData, expInd, respsAsRate=True) for mr in modResps];
#orgs = [hf.organize_resp(mr, expData, expInd, respsAsRate=False) for mr in modResps];
oriModResps = [org[0] for org in orgs]; # only non-empty if expInd = 1
conModResps = [org[1] for org in orgs]; # only non-empty if expInd = 1
sfmixModResps = [org[2] for org in orgs];
allSfMixs = [org[3] for org in orgs];

modLows = [np.nanmin(resp, axis=3) for resp in allSfMixs];
modHighs = [np.nanmax(resp, axis=3) for resp in allSfMixs];
modAvgs = [np.nanmean(resp, axis=3) for resp in allSfMixs];
modSponRates = [fit[6] for fit in modFits];

# DATA: more tabulation - stim vals, organize measured responses
_, _, respOrg, respAll = hf.organize_resp(spikes_rate, expData, expInd, respsAsRate=asRates);

respMean = respOrg;
respStd = np.nanstd(respAll, -1); # take std of all responses for a given condition
# compute SEM, too
findNaN = np.isnan(respAll);
nonNaN  = np.sum(findNaN == False, axis=-1);
respSem = np.nanstd(respAll, -1) / np.sqrt(nonNaN);
# pick which measure of response variance
if respVar == 1:
  respVar = respSem;
else:
  respVar = respStd;

if diffPlot: # otherwise, nothing to do
  ### Now, recenter data relative to flat normalization model
  allAvgs = [respMean, modAvgs[1], modAvgs[0]]; # why? weighted is 1, flat is 0
  respsRecenter = [x - allAvgs[2] for x in allAvgs]; # recentered

  respMean = respsRecenter[0];
  modAvgs  = [respsRecenter[2], respsRecenter[1]];

blankMean, blankStd, _ = hf.blankResp(expData, expInd);

if respMeasure == 1: # i.e. f1, then all 0
  to_sub = [0, 0, 0];
else: # dc
  to_sub = [modBlank_A, blankMean, modBlank_B];

# #### determine contrasts, center spatial frequency, dispersions
all_disps = stimVals[0];
all_cons = stimVals[1];
all_sfs = stimVals[2];

nCons = len(all_cons);
nSfs = len(all_sfs);
nDisps = len(all_disps);

# ### Plots

# set up model plot info
# i.e. flat model is red, weighted model is green
modColors = ['g', 'r']
modLabels = ['A: %s' % modA_str, 'B: %s' % modB_str]

# #### Plots by dispersion

fDisp = []; dispAx = [];

sfs_plot = np.logspace(np.log10(all_sfs[0]), np.log10(all_sfs[-1]), 100);    

for d in range(nDisps):

    v_cons = val_con_by_disp[d];
    n_v_cons = len(v_cons);

    fCurr, dispCurr = plt.subplots(n_v_cons, 2, figsize=(nDisps*8, n_v_cons*12), sharey=False);
    fDisp.append(fCurr)
    dispAx.append(dispCurr);

    minResp = np.min(np.min(respMean[d, ~np.isnan(respMean[d, :, :])]));
    maxResp = np.max(np.max(respMean[d, ~np.isnan(respMean[d, :, :])]));

    for c in reversed(range(n_v_cons)):
        c_plt_ind = len(v_cons) - c - 1;
        v_sfs = ~np.isnan(respMean[d, :, v_cons[c]]);        

        # NOW...let's compute the sum loss across all SF values for this disp X con condition
        if lossType == 1 or lossType == 2 or lossType == 3:
          # lossByCond is [nDisp x nSf x nCon], but flattened - so we use np.ravel_multi_index to access
          sfs_to_check = np.where(v_sfs)[0];
          all_trials = [hf.get_valid_trials(expData, d, v_cons[c], sf_i, expInd, stimVals, validByStimVal)[0] for sf_i in sfs_to_check];
          # first modA
          all_loss_all = np.array([lossByCond_A[x] for x in all_trials]);
          try:
            all_loss = np.mean(all_loss_all, axis=1); # for error per SF condition
            curr_loss = np.sum(all_loss_all)
          except: # in case all_loss_all has unequal length arrays (and is therefeore dtype=Object, not just a np.array)
            all_loss = np.array([np.mean(x) for x in all_loss_all]);
            curr_loss = np.sum([np.sum(x) for x in all_loss_all]);
          # then modB
          all_loss_all_B = np.array([lossByCond_B[x] for x in all_trials]);
          try:
            all_loss_B = np.mean(all_loss_all_B, axis=1); # for error per SF condition
            curr_loss_B = np.sum(all_loss_all_B);
          except: # in case all_loss_all_B has unequal length arrays (and is therefeore dtype=Object, not just a np.array)
            all_loss_B = np.array([np.mean(x) for x in all_loss_all_B]);
            curr_loss_B = np.sum([np.sum(x) for x in all_loss_all_B]);
        elif lossType == 4: # must add for lossType == 1||2 (handled the same way)...
          # lossByCond is [nDisp x nSf x nCon], but flattened - so we use np.ravel_multi_index to access
          sfs_to_check = np.where(v_sfs)[0];
          all_conds = [np.ravel_multi_index([d, sf, v_cons[c]], [nDisps, nSfs, nCons]) for sf in sfs_to_check];
          all_loss = np.array([lossByCond_A[x] for x in all_conds]);
          curr_loss = np.sum(all_loss)
          # then modB
          all_loss_B = np.array([lossByCond_B[x] for x in all_conds]);
          curr_loss_B = np.sum(all_loss_B);
        else:
          curr_loss = np.nan; curr_loss_B = np.nan;
          all_loss = np.nan; all_loss_B = np.nan;

        for i in range(2): # i = 0 (lin-y); i = 1 (log-y)

          ### make things nice
          dispAx[d][c_plt_ind, i].set_xlim((min(all_sfs), max(all_sfs)));

          dispAx[d][c_plt_ind, i].set_xscale('log');
          dispAx[d][c_plt_ind, i].set_title('D%02d: contrast: %.3f (l_w %.1f, l_f %.1f)' % (d, all_cons[v_cons[c]], curr_loss, curr_loss_B));
          dispAx[d][c_plt_ind, i].set_xlabel('Spatial frequency (c/deg)'); 
          dispAx[d][c_plt_ind, i].set_ylabel('Response (spikes/s)');

          # Set ticks out, remove top/right axis, put ticks only on bottom/left
          dispAx[d][c_plt_ind, i].tick_params(labelsize=15, width=majorWid, length=majorLen, direction='out');
          dispAx[d][c_plt_ind, i].tick_params(which='minor', direction='out', width=minorWid, length=minorLen); # minor ticks, too...
          sns.despine(ax=dispAx[d][c_plt_ind, i], offset=10, trim=False); 
   
          ### plot data
          dispAx[d][c_plt_ind, i].errorbar(all_sfs[v_sfs], respMean[d, v_sfs, v_cons[c]], 
                                           respVar[d, v_sfs, v_cons[c]], fmt='o', color='k', clip_on=False); # always show the full data

          ### plot model fits
          if intpMod == 1:
            plt_sfs = np.geomspace(all_sfs[v_sfs][0], all_sfs[v_sfs][-1], sfSteps);
            interpModBoth = []; # well, flat is first, so we will subtract that off...
            if d == 0:
              nRptsCurr = nRptsSingle;
            else:
              nRptsCurr = nRpts;
            for pm, typ in zip(modFits, normTypes):
              simWrap = lambda x: mod_resp.SFMsimulateNew(pm, expData, d, v_cons[c], x, normType=typ, expInd=expInd, nRepeats=nRptsCurr, excType=excType)[0];
              interpMod = [np.mean(simWrap(np.array([sfCurr]))) for sfCurr in plt_sfs];
              interpModBoth.append(np.array(interpMod));
            # TODO plot, but recenter if diffPlot == 1...
            if diffPlot == 1:
              relTo = interpModBoth[0];
            else:
              relTo = np.zeros_like(interpModBoth[0]);
            for rsp, cc, s in zip(interpModBoth, modColors, modLabels):
              dispAx[d][c_plt_ind, i].plot(plt_sfs, rsp-relTo, color=cc, label=s);
          else: # plot model evaluated only at data point
            [dispAx[d][c_plt_ind, i].plot(all_sfs[v_sfs], modAvg[d, v_sfs, v_cons[c]], color=cc, alpha=0.7, clip_on=clip_on, label=s) for modAvg, cc, s in zip(modAvgs, modColors, modLabels)];
          '''
          sponRate = dispAx[d][c_plt_ind, 0].axhline(blankMean, color='b', linestyle='dashed', label='data spon. rate');
          [dispAx[d][c_plt_ind, 0].axhline(sponRate, color=cc, linestyle='dashed') for sponRate,cc in zip(modSponRates, modColors)];
          '''

          ### plot model fits
          if diffPlot == 1:
            if i == 0:
              dispAx[d][c_plt_ind, i].set_ylim((-1.5*np.abs(minResp), 1.5*maxResp));
            else:
              dispAx[d][c_plt_ind, i].set_yscale('symlog');
              dispAx[d][c_plt_ind, i].set_ylim((-1.5*np.abs(minResp), 1.5*maxResp));
          else:
            if i == 0:
              dispAx[d][c_plt_ind, i].set_ylim((0, 1.5*maxResp));
              if np.array_equal(all_loss, np.nan):
                dispAx[d][c_plt_ind, i].text(min(all_sfs), 1.2*maxResp, ', '.join(['%.1f' % x for x in all_loss]), ha='left', wrap=True, fontsize=25);
              dispAx[d][c_plt_ind, i].text(min(all_sfs), 1.2*maxResp, '%.2f, %.2f' % (varExplSF_A[d, v_cons[c]], varExplSF_B[d, v_cons[c]]), ha='left', wrap=True, fontsize=25);
            else:
              dispAx[d][c_plt_ind, i].set_yscale('symlog');
              dispAx[d][c_plt_ind, i].set_ylim((1.1*minResp, 1.5*maxResp));

          dispAx[d][c_plt_ind, i].legend();

    fCurr.suptitle('%s #%d, loss %.2f|%.2f [%s]' % (cellType, cellNum, loss_A, loss_B, respStr));


if not os.path.exists(save_loc):
  os.makedirs(save_loc);

saveName = "/cell_%03d%s.pdf" % (cellNum, kstr)
full_save = os.path.dirname(str(save_loc + 'byDisp%s/' % rvcFlag));
if not os.path.exists(full_save):
  os.makedirs(full_save);
pdfSv = pltSave.PdfPages(full_save + saveName);
for f in fDisp:
    pdfSv.savefig(f)
    plt.close(f)
pdfSv.close();

# #### All SF tuning on one graph, split by dispersion

if diffPlot != 1:
  fDisp = []; dispAx = [];

  sfs_plot = np.logspace(np.log10(all_sfs[0]), np.log10(all_sfs[-1]), 100);    

  for d in range(nDisps):

      v_cons = val_con_by_disp[d];
      n_v_cons = len(v_cons);

      fCurr, dispCurr = plt.subplots(1, 3, figsize=(35, 30), sharex=True, sharey=True); # left side for flat; middle for data; right side for weighted modelb
      fDisp.append(fCurr)
      dispAx.append(dispCurr);

      fCurr.suptitle('%s #%d [%s]' % (cellType, cellNum, respStr));

      resps_curr = [modAvgs[0], respMean, modAvgs[1]];
      labels     = [modLabels[0], 'data', modLabels[1]];

      for i in range(3):

        # Set ticks out, remove top/right axis, put ticks only on bottom/left
        dispAx[d][i].tick_params(labelsize=15, width=majorWid, length=majorLen, direction='out');
        dispAx[d][i].tick_params(which='minor', direction='out'); # minor ticks, too...
        sns.despine(ax=dispAx[d][i], offset=10, trim=False); 

        curr_resps = resps_curr[i];
        maxResp = np.max(np.max(np.max(curr_resps[~np.isnan(curr_resps)])));  

        for c in reversed(range(n_v_cons)):
            v_sfs = ~np.isnan(curr_resps[d, :, v_cons[c]]);        

            # plot data
            col = [c/float(n_v_cons), c/float(n_v_cons), c/float(n_v_cons)];
            plot_resp = curr_resps[d, v_sfs, v_cons[c]] - to_sub[i];

            dispAx[d][i].plot(all_sfs[v_sfs][plot_resp>1e-1], plot_resp[plot_resp>1e-1], '-o', clip_on=False, \
                                           color=col, label=str(np.round(all_cons[v_cons[c]], 2)));

        #dispAx[d][i].set_aspect('equal', 'box'); 
        dispAx[d][i].set_xlim((0.5*min(all_sfs), 1.2*max(all_sfs)));
        #dispAx[d][i].set_ylim((5e-2, 1.5*maxResp));

        dispAx[d][i].set_xscale('log');
        dispAx[d][i].set_yscale('log');
        dispAx[d][i].axis('scaled');
        dispAx[d][i].set_xlabel('sf (c/deg)'); 

        dispAx[d][i].set_ylabel('resp above baseline (imp/s)');
        dispAx[d][i].set_title('D%02d - sf tuning %s' % (d, labels[i]));
        dispAx[d][i].legend(); 

  saveName = "/allCons_cell_%03d%s.pdf" % (cellNum, kstr)
  full_save = os.path.dirname(str(save_loc + 'byDisp%s/' % rvcFlag));
  if not os.path.exists(full_save):
    os.makedirs(full_save);
  pdfSv = pltSave.PdfPages(full_save + saveName);
  for f in fDisp:
      pdfSv.savefig(f)
      plt.close(f)
  pdfSv.close()

# #### Plot just sfMix contrasts

mixCons = hf.get_exp_params(expInd).nCons;
minResp = np.min(np.min(np.min(respMean[~np.isnan(respMean)])));
maxResp = np.max(np.max(np.max(respMean[~np.isnan(respMean)])));

f, sfMixAx = plt.subplots(mixCons, nDisps, figsize=(30, 35));

sfs_plot = np.logspace(np.log10(all_sfs[0]), np.log10(all_sfs[-1]), 100);

for d in range(nDisps):
    v_cons = np.array(val_con_by_disp[d]);
    n_v_cons = len(v_cons);
    v_cons = v_cons[np.arange(np.maximum(0, n_v_cons -mixCons), n_v_cons)]; # max(1, .) for when there are fewer contrasts than 4
    n_v_cons = len(v_cons);
    
    for c in reversed(range(n_v_cons)):

	# Set ticks out, remove top/right axis, put ticks only on bottom/left
        sfMixAx[c_plt_ind, d].tick_params(labelsize=15, width=majorWid, length=majorLen, direction='out');
        sfMixAx[c_plt_ind, d].tick_params(which='minor', direction='out'); # minor ticks, too...
        sns.despine(ax=sfMixAx[c_plt_ind, d], offset=10, trim=False);

        c_plt_ind = n_v_cons - c - 1;
        v_sfs = ~np.isnan(respMean[d, :, v_cons[c]]);
        
        # put sum loss for all conditions present
        # NOW...let's compute the sum loss across all SF values for this disp X con condition
        if lossType == 1 or lossType == 2 or lossType == 3:
          sfs_to_check = np.where(v_sfs)[0];
          all_trials = [hf.get_valid_trials(expData, d, v_cons[c], sf_i, expInd, stimVals, validByStimVal)[0] for sf_i in sfs_to_check];
          # first, wghtd
          all_loss_all = np.array([lossByCond_A[x] for x in all_trials]);
          try:
            all_loss = np.mean(all_loss_all, axis=1); # for error per SF condition
            curr_loss = np.sum(all_loss_all)
          except:
            all_loss = np.array([np.mean(x) for x in all_loss_all]);
            curr_loss = np.sum([np.sum(x) for x in all_loss_all]);
          # then flat/lgn
          all_loss_all_B = np.array([lossByCond_B[x] for x in all_trials]);
          try:
            all_loss_B = np.mean(all_loss_all_B, axis=1); # for error per SF condition
            curr_loss_B = np.sum(all_loss_all_B);
          except:
            all_loss_B = np.array([np.mean(x) for x in all_loss_all_B]);
            curr_loss_B = np.sum([np.sum(x) for x in all_loss_all_B]);
        elif lossType == 4: # must add for lossType == 1||2 (handled the same way)...
          # NOTE: I think below is outdated - now lossByCond is just per trial!
          # lossByCond is [nDisp x nSf x nCon], but flattened - so we use np.ravel_multi_index to access
          sfs_to_check = np.where(v_sfs)[0];
          all_conds = [np.ravel_multi_index([d, sf, v_cons[c]], [nDisps, nSfs, nCons]) for sf in sfs_to_check];
          all_loss = np.array([lossByCond_A[x] for x in all_conds]);
          curr_loss = np.sum(all_loss);
          # then flat
          all_loss_B = np.array([lossByCond_B[x] for x in all_conds]);
          curr_loss_B = np.sum(all_loss_B);
        else:
          curr_loss = np.nan; curr_loss_B = np.nan;
          all_loss = np.nan; all_loss_B = np.nan;

        sfMixAx[c_plt_ind, d].set_title('con: %s (l_A %.1f, l_B %.1f)' % (str(np.round(all_cons[v_cons[c]], 2)), curr_loss, curr_loss_B));
        # plot data
        sfMixAx[c_plt_ind, d].errorbar(all_sfs[v_sfs], respMean[d, v_sfs, v_cons[c]], 
                                       respVar[d, v_sfs, v_cons[c]], fmt='o', color='k', clip_on=False);

	# plot model fits
        if intpMod == 1:
          plt_sfs = np.geomspace(all_sfs[v_sfs][0], all_sfs[v_sfs][-1], sfSteps);
          interpModBoth = []; # well, flat is first, so we will subtract that off...
          if d == 0:
            nRptsCurr = nRptsSingle;
          else:
            nRptsCurr = nRpts;
          for pm, typ in zip(modFits, normTypes):
            simWrap = lambda x: mod_resp.SFMsimulateNew(pm, expData, d, v_cons[c], x, normType=typ, expInd=expInd, nRepeats=nRptsCurr, excType=excType)[0];
            interpMod = [np.mean(simWrap(np.array([sfCurr]))) for sfCurr in plt_sfs];
            interpModBoth.append(np.array(interpMod));
          # TODO plot, but recenter if diffPlot == 1...
          if diffPlot == 1:
            relTo = interpModBoth[0];
          else:
            relTo = np.zeros_like(interpModBoth[0]);
          for rsp, cc, s in zip(interpModBoth, modColors, modLabels):
            if d == 0 and c == 0:
              sfMixAx[c_plt_ind, d].plot(plt_sfs, rsp-relTo, color=cc, label=s, clip_on=clip_on);
            else:
              sfMixAx[c_plt_ind, d].plot(plt_sfs, rsp-relTo, color=cc, clip_on=clip_on);
        else: # plot model evaluated only at data point
          if d == 0 and c == 0:
            [sfMixAx[c_plt_ind, d].plot(all_sfs[v_sfs], modAvg[d, v_sfs, v_cons[c]], color=cc, alpha=0.7, clip_on=clip_on, label=s) for modAvg, cc, s in zip(modAvgs, modColors, modLabels)];
          else:
            [sfMixAx[c_plt_ind, d].plot(all_sfs[v_sfs], modAvg[d, v_sfs, v_cons[c]], color=cc, alpha=0.7, clip_on=clip_on) for modAvg, cc in zip(modAvgs, modColors)];

        sfMixAx[c_plt_ind, d].set_xlim((np.min(all_sfs), np.max(all_sfs)));
        if diffPlot == 1:
          sfMixAx[c_plt_ind, d].set_ylim((-1.5*np.abs(minResp), 1.5*maxResp));
        else:
          sfMixAx[c_plt_ind, d].set_ylim((0, 1.5*maxResp));

        if np.array_equal(all_loss, np.nan):
          sfMixAx[c_plt_ind, d].text(min(all_sfs), 1.2*maxResp, ', '.join(['%.1f' % x for x in all_loss]), ha='left', wrap=True, fontsize=10);
        sfMixAx[c_plt_ind, d].text(min(all_sfs), 0.8*maxResp, '%.2f, %.2f' % (varExplSF_A[d, v_cons[c]], varExplSF_B[d, v_cons[c]]), ha='left', wrap=True, fontsize=25);

        sfMixAx[c_plt_ind, d].set_xscale('log');
        if c_plt_ind == (n_v_cons-1):
          sfMixAx[c_plt_ind, d].set_xlabel('sf (c/deg)');
        if d == 0:
          sfMixAx[c_plt_ind, d].set_ylabel('resp (imp/s)');

if lgnA > 0:
  mWt_A = modFit_A[-1] if pytorch_mod == 0 else 1/(1+np.exp(-modFit_A[-1])); # why? in pytorch_mod, it's a sigmoid
else:
  mWt_A = -99;
if lgnB > 0:
  mWt_B = modFit_B[-1] if pytorch_mod == 0 else 1/(1+np.exp(-modFit_B[-1])); # why? in pytorch_mod, it's a sigmoid
else:
  mWt_B = -99;
lgnStr = ' mWt=%.2f|%.2f' % (mWt_A, mWt_B);

f.legend(fontsize='large');
varExpl_A = hf.var_explained(hf.nan_rm(respMean), hf.nan_rm(modAvgs[0]), None);
varExpl_B = hf.var_explained(hf.nan_rm(respMean), hf.nan_rm(modAvgs[1]), None);
###
if pytorch_mod == 1 and save_varExpl:
  fitListA[cellNum-1][respStr]['varExpl'] = varExpl_A;
  fitListB[cellNum-1][respStr]['varExpl'] = varExpl_B;
  # save the var explained!
  print('saving varExplained in: %s' % (data_loc+fitNameA));
  np.save(data_loc + fitNameA, fitListA);
  np.save(data_loc + fitNameB, fitListB);
f.suptitle('%s #%d (%s; %s), loss %.2f|%.2f%s [varExpl=%.2f|%.2f]' % (cellType, cellNum, cellName, respStr, loss_A, loss_B, lgnStr, varExpl_A, varExpl_B));
	        
#########
# Plot secondary things - filter, normalization, nonlinearity, etc
#########

fDetails = plt.figure();
fDetails.set_size_inches(w=25,h=15)

detailSize = (3, 5);
if ~np.any([i is None for i in oriModResps]): # then we're using an experiment with ori curves
  curr_ax = plt.subplot2grid(detailSize, (0, 2));
  # Remove top/right axis, put ticks only on bottom/left
  sns.despine(ax=curr_ax, offset = 5);

  # plot ori tuning
  [plt.plot(expData['sfm']['exp']['ori'], oriResp, '%so' % c, clip_on=False, label=s) for oriResp, c, s in zip(oriModResps, modColors, modLabels)]; # Model responses
  expPlt = plt.plot(expData['sfm']['exp']['ori'], expData['sfm']['exp']['oriRateMean'], 'o-', clip_on=clip_on); # Exp responses
  plt.xlabel('Ori (deg)', fontsize=12);
  plt.ylabel('Response (ips)', fontsize=12);

if ~np.any([i is None for i in conModResps]): # then we're using an experiment with RVC curves
  # CRF - with values from TF simulation and the broken down (i.e. numerator, denominator separately) values from resimulated conditions
  curr_ax = plt.subplot2grid(detailSize, (0, 1)); # default size is 1x1
  consUse = expData['sfm']['exp']['con'];
  plt.semilogx(consUse, expData['sfm']['exp']['conRateMean'], 'o-', clip_on=False); # Measured responses
  [plt.plot(consUse, conResp, '%so' % c, clip_on=clip_on, label=s) for conResp, c, s in zip(conModResps, modColors, modLabels)]; # Model responses
  plt.xlabel('Con (%)', fontsize=20);

''' DEPRECATING POISSON PLOT --> WILL NEED TO MOVE OTHERS, IF SO
# poisson test - mean/var for each condition (i.e. sfXdispXcon)
curr_ax = plt.subplot2grid(detailSize, (0, 0)); # set the current subplot location/size[default is 1x1]
sns.despine(ax=curr_ax, offset=5, trim=False);
val_conds = ~np.isnan(respMean);
gt0 = np.logical_and(respMean[val_conds]>0, respVar[val_conds]>0);
plt.loglog([0.01, 1000], [0.01, 1000], 'k--');
plt.loglog(respMean[val_conds][gt0], np.square(respVar[val_conds][gt0]), 'o');
# skeleton for plotting modulated poisson prediction
if lossType == 3: # i.e. modPoiss
  mean_vals = np.logspace(-1, 2, 50);
  [plt.loglog(mean_vals, mean_vals + varGain*np.square(mean_vals), label='vG: %.2f' % varGain) for varGain in varGains];
  plt.legend();
plt.xlabel('Mean (imp/s)');
plt.ylabel('Variance (imp/s^2)');
plt.title('Super-poisson?');
plt.axis('equal');
'''

#  RVC - pick center SF
curr_ax = plt.subplot2grid(detailSize, (0, 0)); # default size is 1x1
sns.despine(ax=curr_ax, offset = 5);
disp_rvc = 0;
val_cons = np.array(val_con_by_disp[disp_rvc]);
v_sfs = ~np.isnan(respMean[disp_rvc, :, val_cons[0]]); # remember, for single gratings, all cons have same #/index of sfs
sfToUse = np.int(np.floor(len(v_sfs)/2));
plt.semilogx(all_cons[val_cons], respMean[disp_rvc, sfToUse, val_cons], 'o', clip_on=False); # Measured responses
[plt.plot(all_cons[val_cons], modAvg[disp_rvc, sfToUse, val_cons], marker=None, color=c, clip_on=clip_on, label=s) for modAvg, c, s in zip(modAvgs, modColors, modLabels)]; # Model responses
plt.xlabel('Con (%)', fontsize=20);
plt.ylim([np.minimum(-5, np.nanmin(respMean[disp_rvc, sfToUse, val_cons])), 1.1*np.nanmax(respMean[disp_rvc, sfToUse, val_cons])]);

# plot model details - exc/suppressive components
omega = np.logspace(-1.5, 1.5, 1000);
#omega = np.logspace(-2, 2, 1000);
sfExc = [];
sfExcRaw = [];
for (pltNum, modPrm),modObj,lgnType,lgnConType,mWt in zip(enumerate(modFits), modelsAsObj, lgnTypes, conTypes, [mWt_A, mWt_B]):
  #prefSf = modPrm[0];
  prefSf = minPrefSf + maxPrefSf*hf.sigmoid(modPrm[0])

  if excType == 1:
    ### deriv. gauss
    dOrder = _sigmoidDord*1/(1+np.exp(-modPrm[1]));
    sfRel = omega/prefSf;
    s     = np.power(omega, dOrder) * np.exp(-dOrder/2 * np.square(sfRel));
    sMax  = np.power(prefSf, dOrder) * np.exp(-dOrder/2);
    sfExcV1 = s/sMax;
    sfExcLGN = s/sMax; # will be used IF there isn't an LGN front-end...
  if excType == 2:
    ### flex. gauss
    sigLow = modPrm[1] if _sigmoidSigma is None else _sigmoidSigma/(1+np.exp(-modPrm[1]));
    sigHigh = modPrm[-1-np.sign(lgnType)] if _sigmoidSigma is None else _sigmoidSigma/(1+np.exp(-modPrm[-1-np.sign(lgnType)]))
    sfRel = np.divide(omega, prefSf);
    # - set the sigma appropriately, depending on what the stimulus SF is
    sigma = np.multiply(sigLow, [1]*len(sfRel));
    sigma[[x for x in range(len(sfRel)) if sfRel[x] > 1]] = sigHigh;
    # - now, compute the responses (automatically normalized, since max gaussian value is 1...)
    s     = [np.exp(-np.divide(np.square(np.log(x)), 2*np.square(y))) for x,y in zip(sfRel, sigma)];
    sfExcV1 = s;
    sfExcLGN = s; # will be used IF there isn't an LGN front-end...
  # BUT. if this is an LGN model, we'll apply the filtering, eval. at 100% contrast
  if lgnType == 1 or lgnType == 2 or lgnType == 3 or lgnType == 4:
    params_m = modObj.rvc_m.detach().numpy(); # one tensor array, so just detach
    params_p = modObj.rvc_p.detach().numpy();
    DoGmodel = modObj.LGNmodel; # what DoG parameterization?
    dog_m = np.array([x.item() for x in modObj.dog_m]) # a list of tensors, so do list comp. to undo into a normal/numpy array
    dog_p = np.array([x.item() for x in modObj.dog_p])
    # now compute with these parameters
    glbl_min = 1e-6; # as in mrpt as of late 2022 and beyond --> doesn't matter for dogSach/DiffOfGauss, anyway, though...
    resps_m = hf.get_descrResp(dog_m, omega, DoGmodel, minThresh=glbl_min)
    resps_p = hf.get_descrResp(dog_p, omega, DoGmodel, minThresh=glbl_min)
    # -- make sure we normalize by the true max response:
    sfTest = np.geomspace(0.1, 10, 1000);
    max_m = np.max(hf.get_descrResp(dog_m, sfTest, DoGmodel, minThresh=glbl_min));
    max_p = np.max(hf.get_descrResp(dog_p, sfTest, DoGmodel, minThresh=glbl_min));
    # -- then here's our selectivity per component for the current stimulus
    selSf_m = np.divide(resps_m, max_m);
    selSf_p = np.divide(resps_p, max_p);
    # - then RVC response: # rvcMod 0 (Movshon)
    stimCo = np.linspace(0,1,100);
    '''
    rvc_mod = hf.get_rvc_model();
    selCon_m = rvc_mod(*params_m, stimCo)
    selCon_p = rvc_mod(*params_p, stimCo)
    '''
    selCon_m = mrpt.get_rvc_model(modObj.rvc_m, mrpt._cast_as_tensor(stimCo), modObj.rvcMod).detach().numpy();
    selCon_p = mrpt.get_rvc_model(modObj.rvc_p, mrpt._cast_as_tensor(stimCo), modObj.rvcMod).detach().numpy();

    if lgnConType == 1: # DEFAULT
      # -- then here's our final responses per component for the current stimulus
      # ---- NOTE: The real mWeight will be sigmoid(mWeight), such that it's bounded between 0 and 1
      lgnSel = mWt*selSf_m*selCon_m[-1] + (1-mWt)*selSf_p*selCon_p[-1];
    elif lgnConType == 2 or lgnConType == 3 or lgnConType == 4:
      # -- Unlike the above (default) case, we don't allow for a separate M & P RVC - instead we just take the average of the two
      selCon_avg = mWt*selCon_m + (1-mWt)*selCon_p;
      lgnSel = mWt*selSf_m*selCon_avg[-1] + (1-mWt)*selSf_p*selCon_avg[-1];
    elif lgnConType == 5: # TEMP
      # -- then here's our final responses per component for the current stimulus
      # ---- NOTE: The real mWeight will be sigmoid(mWeight), such that it's bounded between 0 and 1
      lgnSel = mWt*selSf_m*selCon_m[-1] + (1-mWt)*selSf_p*selCon_p[-1];
    withLGN = s*lgnSel;
    sfExcLGN = withLGN/np.max(withLGN);

    # plot LGN front-end, if we're here
    curr_ax = plt.subplot2grid(detailSize, (1+pltNum, 0));
    plt.semilogx(omega, selSf_m, label='magno [%.1f]' % dog_m[1], color='r', linestyle='--');
    plt.semilogx(omega, selSf_p, label='parvo [%.1f]' % dog_p[1], color='b', linestyle='--');
    max_joint = np.max(lgnSel);
    plt.semilogx(omega, np.divide(lgnSel, max_joint), label='joint - 100% contrast', color='k');
    conMatch = 0.20
    conValInd = np.argmin(np.square(stimCo-conMatch));
    if lgnConType == 1:
      jointAtLowCon = mWt*selSf_m*selCon_m[conValInd] + (1-mWt)*selSf_p*selCon_p[conValInd];
    elif lgnConType == 2 or lgnConType == 3 or lgnConType == 4:
      jointAtLowCon = mWt*selSf_m*selCon_avg[conValInd] + (1-mWt)*selSf_p*selCon_avg[conValInd];
    elif lgnConType == 5:
      jointAtLowCon = mWt*selSf_m*selCon_m[conValInd] + (1-mWt)*selSf_p*selCon_p[conValInd];
    plt.semilogx(omega, np.divide(jointAtLowCon, max_joint), label='joint - %d%% contrast' % (100*conMatch), color='k', alpha=0.3);
    plt.title('lgn %s' % modLabels[pltNum]);
    plt.legend();
    plt.xlim([1e-1, 1e1]);

  sfExcRaw.append(sfExcV1);
  sfExc.append(sfExcLGN);

# Compute the reference, untuned gain control (apply as necessary)
inhAsym = 0;
inhWeight = [];
try:
  inhChan = expData['sfm']['mod']['normalization']['pref']['sf'];
except: # if that didn't work, then we need to create the norm_resp
  norm_resp = mod_resp.GetNormResp(cellNum, data_loc, expDir='', dataListName=expName); # in GetNormResp, expDir added to data_loc; already included here
  inhChan = norm_resp['pref']['sf']
  expData  = hf.np_smart_load(str(data_loc + cellName + '_sfm.npy')); # then we have to reload expData...
inhSfTuning = hf.getSuppressiveSFtuning();
for iP in range(len(inhChan)):
    inhWeight = np.append(inhWeight, 1 + inhAsym * (np.log(inhChan[iP]) - np.mean(np.log(inhChan[iP]))));
sfNorm_flat = np.sum(-.5*(inhWeight*np.square(inhSfTuning)), 1);
sfNorm_flat = sfNorm_flat/np.amax(np.abs(sfNorm_flat));

### Compute weights for suppressive signals
unwt_weights = np.sqrt(hf.genNormWeightsSimple(omega, None, None));
sfNormSim = unwt_weights/np.amax(np.abs(unwt_weights));
# - tuned
if gs_mean_A is not None:
  wt_weights_A = np.sqrt(hf.genNormWeightsSimple(omega, gs_mean_A, gs_std_A, normType=normA, dgNormFunc=dgnfA));
  sfNormTuneSim_A = wt_weights_A/np.amax(np.abs(wt_weights_A));
  sfNormSim_A = sfNormTuneSim_A;
else:
  sfNormSim_A = sfNormSim;
if gs_mean_B is not None:
  wt_weights_B = np.sqrt(hf.genNormWeightsSimple(omega, gs_mean_B, gs_std_B, normType=normB, dgNormFunc=dgnfB));
  sfNormTuneSim_B = wt_weights_B/np.amax(np.abs(wt_weights_B));
  sfNormSim_B = sfNormTuneSim_B;
else:
  sfNormSim_B = sfNormSim;
sfNormsSimple = [sfNormSim_A, sfNormSim_B]

# Plot the filters - for LGN, this is WITH the lgn filters "acting" (assuming high contrast)
curr_ax = plt.subplot2grid(detailSize, (1, 1));
# Remove top/right axis, put ticks only on bottom/left
sns.despine(ax=curr_ax, offset=5);
# just setting up lines
plt.semilogx([omega[0], omega[-1]], [0, 0], 'k--')
plt.semilogx([.01, .01], [-1.5, 1], 'k--')
plt.semilogx([.1, .1], [-1.5, 1], 'k--')
plt.semilogx([1, 1], [-1.5, 1], 'k--')
plt.semilogx([10, 10], [-1.5, 1], 'k--')
plt.semilogx([100, 100], [-1.5, 1], 'k--')
# now the real stuff
[plt.semilogx(omega, exc, '%s' % cc, label=s) for exc, cc, s in zip(sfExc, modColors, modLabels)]
[plt.semilogx(omega, norm, '%s--' % cc, label=s) for norm, cc, s in zip(sfNormsSimple, modColors, modLabels)]
# -- this is the OLD version (note sfNorms as opposed to sfNormsSimple) with the subunits included
#[plt.semilogx(omega, -norm, '%s--' % cc, label=s) for norm, cc, s in zip(sfNorms, modColors, modLabels)]
plt.xlim([omega[0], omega[-1]]);
plt.ylim([-0.1, 1.1]);
plt.xlabel('spatial frequency (c/deg)', fontsize=12);
plt.ylabel('Normalized response (a.u.)', fontsize=12);

### now the raw weights/filters (i.e. with LGN filter applied for excitation, if needed)
curr_ax = plt.subplot2grid(detailSize, (2, 1));
# Remove top/right axis, put ticks only on bottom/left
sns.despine(ax=curr_ax, offset=5);
plt.semilogx([omega[0], omega[-1]], [0, 0], 'k--')
plt.semilogx([.01, .01], [-1.5, 1], 'k--')
plt.semilogx([.1, .1], [-1.5, 1], 'k--')
plt.semilogx([1, 1], [-1.5, 1], 'k--')
plt.semilogx([10, 10], [-1.5, 1], 'k--')
plt.semilogx([100, 100], [-1.5, 1], 'k--')
[plt.semilogx(omega, exc, '%s' % cc, label=s) for exc, cc, s in zip(sfExcRaw, modColors, modLabels)]
#[plt.semilogx(omega, norm, '%s--' % cc, label=s) for norm, cc, s in zip(sfNormsSimple, modColors, modLabels)]
plt.xlim([omega[0], omega[-1]]);
plt.ylim([-0.1, 1.1]);
plt.title('v-- raw weights/filters --v');
plt.xlabel('spatial frequency (c/deg)', fontsize=12);
plt.ylabel('Normalized response (a.u.)', fontsize=12);

# Now, plot the full denominator (including the constant term) at a few contrasts
# --- use the debug flag to get the tuned component of the gain control as computed in the full model
for disp_i in range(np.minimum(3, nDisps)):
  exc_ax = plt.subplot2grid(detailSize, (0, 2+disp_i));
  norm_ax = plt.subplot2grid(detailSize, (1, 2+disp_i));

  modRespsDebug = [mod.forward(dw.trInf, respMeasure=respMeasure, debug=1, sigmoidSigma=_sigmoidSigma, recenter_norm=recenter_norm, normOverwrite=True) for mod in [model_A, model_B]];
  modA_exc, modA_norm, modA_sigma = [modRespsDebug[0][x].detach().numpy() for x in [0, 1,2]]; # returns are exc, inh, sigmaFilt (c50)
  modB_exc, modB_norm, modB_sigma = [modRespsDebug[1][x].detach().numpy() for x in [0, 1,2]]; # returns are exc, inh, sigmaFilt (c50)
  # --- then, simply mirror the calculation as done in the full model
  full_denoms = [sigmaFilt+norm for sigmaFilt, norm in zip([modA_sigma, modB_sigma], [modA_norm, modB_norm])];
  #full_denoms = [np.power(sigmaFilt + np.power(norm, 2), 0.5) for sigmaFilt, norm in zip([modA_sigma, modB_sigma], [modA_norm, modB_norm])];
  # --- use hf.get_valid_trials to get high/low con, single gratings
  v_cons = np.array(val_con_by_disp[disp_i]);
  if disp_i == 0: # single gratings
    conVals = [0.10, 0.33, 0.5, 1]; # try to get the normResp at these contrast values; MUST BE ASCENDING
  elif disp_i == 1: # e.x. mixture
    conVals = [0.33, 0.69, 1]; # try to get the normResp at these contrast values; MUST BE ASCENDING
  elif disp_i == 2: # e.x. mixture
    conVals = [0.47, 0.69, 1]; # try to get the normResp at these contrast values; MUST BE ASCENDING
  modTrials = dw.trInf['num']; # these are the trials eval. by the model
  # then, let's go through for the above contrasts and get the in-model response
  # as of 23.01.08, we normalize the normalization response to the high-contrast value
  line_styles = ['-', '--'] # solid for exc, dashed for norm.
  for cI, conVal in enumerate(reversed(conVals)):
    closest_ind = np.argmin(np.abs(conVal - all_cons[v_cons]));
    close_enough = np.abs(all_cons[v_cons[closest_ind]] - conVal) < 0.03 # must be within 3% contrast
    if close_enough:
      valSfInds = hf.get_valid_sfs(None, disp_i, v_cons[closest_ind], expInd, stimVals, validByStimVal);
      # highest contrast, first
      all_trials = [hf.get_valid_trials(expData, disp_i, v_cons[closest_ind], sf_i, expInd, stimVals, validByStimVal)[0] for sf_i in valSfInds];
      # then, find which corresponding index into model-eval-only trials this is
      all_trials_modInd = [np.intersect1d(modTrials, trs, return_indices=True)[1] for trs in all_trials];
      sf_vals = all_sfs[valSfInds];
      for respInd, whichResp in enumerate([[modA_exc, modB_exc], full_denoms]):
        whichAx = exc_ax if respInd==0 else norm_ax;
        if model_A.useFullNormResp or respInd==0: # i.e. we only do this if norm. and fullNormResp
          modA_resps = [np.mean(whichResp[0][:, trs]) for trs in all_trials_modInd];
          modB_resps = [np.mean(whichResp[1][:, trs]) for trs in all_trials_modInd];
          #print('respInd %d, con %.2f:\t' % (respInd, conVal))
          #print(modA_resps);
        else:
          modA_resps = [np.mean(whichResp[0][trs]) for trs in all_trials_modInd];
          modB_resps = [np.mean(whichResp[1][trs]) for trs in all_trials_modInd];
        # as of 23.01.08, normalize the denominator!
        if conVal==np.nanmax(conVals):
          if respInd == 0:
            to_norm_num  = [np.nanmax(denom) for denom in [modA_resps, modB_resps]];
          elif respInd == 1:
            to_norm_denom = [np.nanmax(denom) for denom in [modA_resps, modB_resps]];
        to_norm = to_norm_num if respInd==0 else to_norm_denom;
        [whichAx.semilogx(sf_vals, np.divide(denom, norm), alpha=conVal, color=clr, linestyle=line_styles[respInd]) for clr,denom,norm in zip(modColors, [modA_resps, modB_resps], to_norm)]
        if respInd == 0: # exc
          whichAx.set_title('Model exc. [d=%d]' % disp_i);
          if conVal==np.nanmax(conVals):
            # let's also replot the high contrast responses (faintly) on the norm. plot!
            [norm_ax.semilogx(sf_vals, np.divide(denom, norm), alpha=0.3, linestyle=line_styles[respInd], color=clr) for clr,denom,norm in zip(modColors, [modA_resps, modB_resps], to_norm)]
        elif respInd == 1: # inh
          whichAx.set_title('Model norm. [d=%d]' % disp_i);
          # also plot just the constant term (i.e. if there is NO g.c. pooled response)
          sf_vals = all_sfs[valSfInds];
          onlySigma = [sigmaFilt for sigmaFilt in [modA_sigma, modB_sigma]];
          [whichAx.plot(xCoord*sf_vals[0], sig/norm, color=clr, marker='>') for xCoord,sig,clr,norm in zip([0.95, 0.85], onlySigma, modColors, to_norm)]
        whichAx.set_xlim([omega[0], omega[-1]]);
        #plt.xlim([1e-1, 1e1]);

# last but not least...and not last... response nonlinearity
if _sigmoidRespExp is None:
  modExps = [x[3] for x in modFits]; # respExp is in location [3]
else:
  modExps = [1 + _sigmoidRespExp/(1+np.exp(-x[3])) for x in modFits]; # respExp is in location [3]
curr_ax = plt.subplot2grid(detailSize, (0, 1));
# Remove top/right axis, put ticks only on bottom/left
sns.despine(ax=curr_ax, offset=5);
plt.plot([-1, 1], [0, 0], 'k--')
plt.plot([0, 0], [-.1, 1], 'k--')
[plt.plot(np.linspace(-1,1,100), np.power(np.maximum(0, np.linspace(-1,1,100)), modExp), '%s-' % cc, label=s, linewidth=2) for modExp,cc,s in zip(modExps, modColors, modLabels)]
plt.plot(np.linspace(-1,1,100), np.maximum(0, np.linspace(-1,1,100)), 'k--', linewidth=1)
plt.xlim([-1, 1]);
plt.ylim([-.1, 1]);
plt.text(0.5, 1.1, 'respExp: %.2f, %.2f' % (modExps[0], modExps[1]), fontsize=12, horizontalalignment='center', verticalalignment='center');

# IF available, show the loss trajectory
if loss_traj_A is not None or loss_traj_B is not None:
  curr_ax = plt.subplot2grid(detailSize, (2, 4));
  if loss_traj_A is not None:
    plt.plot(loss_traj_A, label='modA', color=modColors[0])
  if loss_traj_B is not None:
    plt.plot(loss_traj_B, label='modB', color=modColors[1])
  #plt.xscale('log');
  plt.yscale('symlog');
  plt.legend();
  plt.title('Loss traj. on best fit');
  sns.despine(ax=curr_ax, offset=10);

# print, in text, model parameters:
curr_ax = plt.subplot2grid(detailSize, (2, 3)); # was (0, 4)
plt.text(0.5, 0.5, 'prefSf: %.3f, %.3f' % (modFits[0][0], modFits[1][0]), fontsize=12, horizontalalignment='center', verticalalignment='center');
if excType == 1:
  plt.text(0.5, 0.4, 'derivative order: %.3f, %.3f' % (modFits[0][1], modFits[1][1]), fontsize=12, horizontalalignment='center', verticalalignment='center');
elif excType == 2:
  plt.text(0.5, 0.4, 'sig: %.2f|%.2f, %.2f|%.2f' % (modFits[0][1], modFits[0][-1-np.sign(lgnTypes[0])], modFits[1][1], modFits[1][-1-np.sign(lgnTypes[1])]), fontsize=12, horizontalalignment='center', verticalalignment='center');
#respScalars = [_sigmoidScale/(1+np.exp(-x)) for x in [modFits[0][4], modFits[1][4]]];
respScalars = [modFits[0][4], modFits[1][4]]; # don't transform them, since we want to know the real value of the optimized parameter
plt.text(0.5, 0.3, 'response scalar: %.3f, %.3f' % (respScalars[0], respScalars[1]), fontsize=12, horizontalalignment='center', verticalalignment='center');
plt.text(0.5, 0.2, 'sigma: %.2e, %.2e | %.3f, %.3f' % (np.power(10, modFits[0][2]), np.power(10, modFits[1][2]), modFits[0][2], modFits[1][2]), fontsize=12, horizontalalignment='center', verticalalignment='center');
normGainA = _sigmoidGainNorm/(1+np.exp(-modFits[0][10])) if normTypes[0]==5 else np.nan;
normGainB = _sigmoidGainNorm/(1+np.exp(-modFits[1][10])) if normTypes[1]==5 else np.nan;
if normGainA is not None or normGainB is not None:
  plt.text(0.5, 0.1, 'normGain: %.2f, %.2f' % (normGainA, normGainB), fontsize=12, horizontalalignment='center', verticalalignment='center');
if normTypes[0]==0 or normTypes[1]==0:
  # assume it's inhAsym -->
  inhA = modFits[0][8] if normTypes[0] == 0 else np.nan;
  inhB = modFits[1][8] if normTypes[1] == 0 else np.nan;
  plt.text(0.5, 0, 'inhAsym: %.2f, %.2f' % (inhA, inhB), fontsize=12, horizontalalignment='center', verticalalignment='center');
plt.axis('off');

# Now, space out the subplots...
#f.tight_layout(pad=0.1)
fDetails.tight_layout(pad=0.1)

### now save all figures (sfMix contrasts, details, normalization stuff)
allFigs = [f, fDetails];
saveName = "/cell_%03d%s.pdf" % (cellNum, kstr)
full_save = os.path.dirname(str(save_loc + 'sfMixOnly%s/' % rvcFlag));
if not os.path.exists(full_save):
  os.makedirs(full_save);
pdfSv = pltSave.PdfPages(full_save + saveName);
for fig in range(len(allFigs)):
    pdfSv.savefig(allFigs[fig])
    plt.close(allFigs[fig])
pdfSv.close()

#### Response versus contrast

# #### Plot contrast response functions with (full) model predictions

rvcAx = []; fRVC = [];

if intpMod == 0 or (intpMod == 1 and conSteps > 0): # i.e. we've chosen to do this (we have this flag since sometimes we do not need to plot RVCs in interpolated way)

  for d in range(nDisps):
      # which sfs have at least one contrast presentation? within a dispersion, all cons have the same # of sfs
      v_sf_inds = hf.get_valid_sfs(expData, d, val_con_by_disp[d][0], expInd, stimVals, validByStimVal);
      n_v_sfs = len(v_sf_inds);
      n_rows = int(np.ceil(n_v_sfs/np.floor(np.sqrt(n_v_sfs)))); # make this close to a rectangle/square in arrangement (cycling through sfs)
      n_cols = int(np.ceil(n_v_sfs/n_rows));
      fCurr, rvcCurr = plt.subplots(n_rows, n_cols, figsize=(n_cols*10, n_rows*15), sharex = True, sharey = True);
      fRVC.append(fCurr);
      rvcAx.append(rvcCurr);

      fCurr.suptitle('%s #%d [%s]' % (cellType, cellNum, respStr));

      #print('%d rows, %d cols\n' % (n_rows, n_cols));
      all_rvc_loss_A = [];
      all_rvc_loss_B = [];
      for sf in range(n_v_sfs):

          row_ind = int(sf/n_cols);
          col_ind = np.mod(sf, n_cols);
          sf_ind = v_sf_inds[sf];
          plt_x = d; 
          if n_cols > 1:
            plt_y = (row_ind, col_ind);
          else: # pyplot makes it (n_rows, ) if n_cols == 1
            plt_y = (row_ind, );
          #print(plt_y);

          # Set ticks out, remove top/right axis, put ticks only on bottom/left
          sns.despine(ax = rvcAx[plt_x][plt_y], offset = 10, trim=False);
          rvcAx[plt_x][plt_y].tick_params(labelsize=25, width=majorWid, length=majorLen, direction='out');
          rvcAx[plt_x][plt_y].tick_params(which='minor', direction='out'); # minor ticks, too...

          v_cons = val_con_by_disp[d];
          n_cons = len(v_cons);
          plot_cons = np.linspace(np.min(all_cons[v_cons]), np.max(all_cons[v_cons]), 100); # 100 steps for plotting...

          # organize (measured) responses
          resp_curr = np.reshape([respMean[d, sf_ind, v_cons]], (n_cons, ));
          var_curr  = np.reshape([respVar[d, sf_ind, v_cons]], (n_cons, ));
          if diffPlot == 1: # don't set a baseline (i.e. response can be negative!)
            respPlt = rvcAx[plt_x][plt_y].errorbar(all_cons[v_cons], resp_curr, var_curr, fmt='o', color='k', clip_on=False, label='data');
          else:
            respPlt = rvcAx[plt_x][plt_y].errorbar(all_cons[v_cons], np.maximum(resp_curr, 0.1), var_curr, fmt='o', color='k', clip_on=clip_on, label='data');

          # RVC with full model fits (i.e. flat and weighted)
          if intpMod == 1:
            plt_cons = np.geomspace(all_cons[v_cons][0], all_cons[v_cons][-1], conSteps);
            interpModBoth = []; # flat comes first, and we'll subtract off if diffPlot
            if d == 0:
              nRptsCurr = nRptsSingle;
            else:
              nRptsCurr = nRpts;
            for pm, typ in zip(modFits, normTypes):
              simWrap = lambda x: mod_resp.SFMsimulateNew(pm, expData, d, x, sf_ind, normType=typ, expInd=expInd, nRepeats=nRptsCurr, excType=excType)[0];
              interpMod = np.array([np.mean(simWrap(np.array([conCurr]))) for conCurr in plt_cons]);
              interpModBoth.append(np.array(interpMod));
            if diffPlot == 1:
              relTo = interpModBoth[0];
            else:
              relTo = np.zeros_like(interpModBoth[0]);
            for rsp, cc, s in zip(interpModBoth, modColors, modLabels):
              rvcAx[plt_x][plt_y].plot(plt_cons, rsp-relTo, color=cc, label=s, clip_on=clip_on);
          else:
            [rvcAx[plt_x][plt_y].plot(all_cons[v_cons], np.maximum(modAvg[d, sf_ind, v_cons], 0.1), color=cc, \
              alpha=0.7, clip_on=clip_on, label=s) for modAvg,cc,s in zip(modAvgs, modColors, modLabels)];

          # summary plots
          '''
          curr_rvc = rvcAx[0][d, 0].plot(all_cons[v_cons], resps_curr, '-', clip_on=clip_on);
          rvc_plots.append(curr_rvc[0]);

          stdPts = np.hstack((0, np.reshape([respVar[d, sf_ind, v_cons]], (n_cons, ))));
          expPts = rvcAx[d+1][row_ind, col_ind].errorbar(np.hstack((0, all_cons[v_cons])), resps_w_blank, stdPts, fmt='o', clip_on=Fals
  e);

          sepPlt = rvcAx[d+1][row_ind, col_ind].plot(plot_cons, helper_fcns.naka_rushton(plot_cons, curr_fit_sep), linestyle='dashed');
          allPlt = rvcAx[d+1][row_ind, col_ind].plot(plot_cons, helper_fcns.naka_rushton(plot_cons, curr_fit_all), linestyle='dashed');
          # accompanying legend/comments
          rvcAx[d+1][row_ind, col_ind].legend((expPts[0], sepPlt[0], allPlt[0]), ('data', 'model fits'), fontsize='large', loc='center left')
          '''

          rvcAx[plt_x][plt_y].text(min(all_cons[v_cons]), 0.8*maxResp, '%.2f, %.2f' % (varExplCon_A[d, sf_ind], varExplCon_B[d, sf_ind]), ha='left', wrap=True, fontsize=25);
          # ALSO compute loss for these data:
          all_trials = [hf.get_valid_trials(expData, d, vc, sf, expInd, stimVals, validByStimVal)[0][0] for vc in v_cons];
          try:
            rvc_loss = [np.sum([lbc_curr[vt] for vt in all_trials]) for lbc_curr in [lossByCond_A, lossByCond_B]];
          except: # this isn't essential to have, so just give NaNs and move on...
            rvc_loss = [-999, -999];
          rvcAx[plt_x][plt_y].text(min(all_cons[v_cons]), 0.6*maxResp, '%.2f, %.2f' % (*rvc_loss, ), ha='left', wrap=True, fontsize=25);
          all_rvc_loss_A.append(rvc_loss[0]);
          all_rvc_loss_B.append(rvc_loss[1]);

          rvcAx[plt_x][plt_y].set_xscale('log', base=10); # was previously symlog, linthreshx=0.01
          if col_ind == 0:
            rvcAx[plt_x][plt_y].set_xlabel('contrast', fontsize='medium');
            rvcAx[plt_x][plt_y].set_ylabel('response (spikes/s)', fontsize='medium');
            rvcAx[plt_x][plt_y].legend();

          rvcAx[plt_x][plt_y].set_title('D%d: sf: %.3f [%d,%d]' % (d+1, all_sfs[sf_ind], np.sum(all_rvc_loss_A), np.sum(all_rvc_loss_B)), fontsize='large');


  saveName = "/cell_%03d%s.pdf" % (cellNum, kstr)
  full_save = os.path.dirname(str(save_loc + 'CRF%s/' % rvcFlag));
  if not os.path.exists(full_save):
    os.makedirs(full_save);
  pdfSv = pltSave.PdfPages(full_save + saveName);
  for f in fRVC:
      pdfSv.savefig(f)
      plt.close(f)
  pdfSv.close()

# #### Plot contrast response functions - all sfs on one axis (per dispersion)

if diffPlot != 1 or intpMod == 0:

  crfAx = []; fCRF = [];

  for d in range(nDisps):

      fCurr, crfCurr = plt.subplots(1, 3, figsize=(35, 30), sharex = True, sharey = True); # left side for flat; middle for data; right side for weighted model
      fCRF.append(fCurr)
      crfAx.append(crfCurr);

      fCurr.suptitle('%s #%d [%s]' % (cellType, cellNum, respStr));

      resps_curr = [modAvgs[0], respMean, modAvgs[1]];
      labels     = [modLabels[0], 'data', modLabels[1]];

      v_sf_inds = hf.get_valid_sfs(expData, d, val_con_by_disp[d][0], expInd, stimVals, validByStimVal);
      n_v_sfs = len(v_sf_inds);

      for i in range(3):
        curr_resps = resps_curr[i];
        maxResp = np.max(np.max(np.max(curr_resps[~np.isnan(curr_resps)])));

        # Set ticks out, remove top/right axis, put ticks only on bottom/left
        crfAx[d][i].tick_params(labelsize=15, width=majorWid, length=majorLen, direction='out');
        crfAx[d][i].tick_params(which='minor', direction='out'); # minor ticks, too...
        sns.despine(ax = crfAx[d][i], offset=10, trim=False);

        lines_log = [];
        for sf in range(n_v_sfs):
            sf_ind = v_sf_inds[sf];
            v_cons = ~np.isnan(curr_resps[d, sf_ind, :]);
            n_cons = sum(v_cons);

            col = [sf/float(n_v_sfs), sf/float(n_v_sfs), sf/float(n_v_sfs)];
            plot_resp = curr_resps[d, sf_ind, v_cons] - to_sub[i];

            line_curr, = crfAx[d][i].plot(all_cons[v_cons][plot_resp>1e-1], plot_resp[plot_resp>1e-1], '-o', color=col, \
                                          clip_on=False, label = str(np.round(all_sfs[sf_ind], 2)));
            lines_log.append(line_curr);

        crfAx[d][i].set_xlim([-0.1, 1]);
        crfAx[d][i].set_ylim([-0.1*maxResp, 1.1*maxResp]);
        #'''
        crfAx[d][i].set_xscale('log');
        crfAx[d][i].set_yscale('log');
        #crfAx[d][i].set_xlim([1e-2, 1]);
        #crfAx[d][i].set_ylim([1e-2, 1.5*maxResp]);
        crfAx[d][i].axis('scaled');
        #'''
        crfAx[d][i].set_xlabel('contrast');

        crfAx[d][i].set_ylabel('resp above baseline (imp/s)');
        crfAx[d][i].set_title('D%d: sf:all - log resp %s' % (d, labels[i]));
        crfAx[d][i].legend();

  saveName = "/allSfs_cell_%03d%s.pdf" % (cellNum, kstr)
  full_save = os.path.dirname(str(save_loc + 'CRF%s/' % rvcFlag));
  if not os.path.exists(full_save):
    os.makedirs(full_save);
  pdfSv = pltSave.PdfPages(full_save + saveName);
  for f in fCRF:
      pdfSv.savefig(f)
      plt.close(f)
  pdfSv.close()
