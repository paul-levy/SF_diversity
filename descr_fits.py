import numpy as np
import sys
import helper_fcns as hf
import scipy.optimize as opt
import os
from time import sleep
from scipy.stats import sem, poisson
import warnings
import pdb

basePath = os.getcwd() + '/';
data_suff = 'structures/';

expName = hf.get_datalist(sys.argv[3]); # sys.argv[3] is experiment dir
#expName = 'dataList_glx_mr.npy'
df_f0 = 'descrFits_190503_sqrt_flex.npy';
#df_f0 = 'descrFits_190503_sach_flex.npy';
dogName =  'descrFits_190503';
phAdvName = 'phaseAdvanceFits_190905'
rvcName_f0   = 'rvcFits_f0'
rvcName_f1   = 'rvcFits_190905'
## model recovery???
modelRecov = 0;
if modelRecov == 1:
  normType = 1; # use if modelRecov == 1 :: 1 - flat; 2 - wght; ...
  dogName =  'mr%s_descrFits_190503' % hf.fitType_suffix(normType);
  rvcName = 'mr%s_rvcFits_f0.npy' % hf.fitType_suffix(normType);
else:
  normType = 0;

##########
### TODO:
##########
# - Fix rvc_adjusted_fit to still fit F1 without phase_advance_fit (i.e. for altExp)
# - Redo all of (1) for more general use!

##########
### Table of contents
##########

## phase_advance_fit
## rvc_adjusted_fit  - fit RVC for each SF/disp condition, choosing F0 or F1 given simple/complex determination
## fit_RVC_f0        - forces f0 spikes for RVC

## invalid
## DoG_loss
## fit_descr_DoG

### 1: Recreate Movshon, Kiorpes, Hawken, Cavanaugh '05 figure 6 analyses
''' These plots show response versus contrast data (with model fit) AND
    phase/amplitude plots with a model fit for response phase as a function of response amplitude
   
    First, given the FFT-derived response amplitude and phase, determine the response phase relative
    to the stimulus by taking into account the stimulus phase. 
    Then, make a simple linear model fit (line + constant offset) of the response phase as a function
    of response amplitude.

    The key non-intuitive step in the analysis is as follows: Rather than simply fitting an RVC curve
    with the FFT-derived response amplitudes, we determine the "true"/expected response phase given
    the measured response amplitude. Then, we project the observed vector onto a line which represents
    the "true"/expected response vector (i.e. the response vector with the expected phase, given the amplitude).
    Thus, the "fixed" response amplitude is = measuredAmp * cos(phiM - phiE)
    (phiM/E are the measured and expected response phases, respectively)

    This value will always be <= measuredAmp, which is what we want - if the response phase deviated
    from what it should be, then there was noise, and that noise shouldn't contribute to our response.
  
    Then, with these set of response amplitudes, fit an RVC (same model as in the '05 paper)

    For mixture stimuli, we will do the following (per conversations with JAM and EPS): Get the mean amplitude/phase
    of each component for a given condition (as done for single gratings) -- using the phase/amplitude relationship established
    for that component when presented in isolation, perform the same projection.
    To fit the RVC curve, then, simply fit the model to the sum of the adjusted individual component responses.
    The Sach DoG curves should also be fit to this sum.
'''

def phase_advance_fit(cell_num, data_loc, expInd, phAdvName=phAdvName, to_save=1, disp=0, dir=1, expName=expName):
  ''' Given the FFT-derived response amplitude and phase, determine the response phase relative
      to the stimulus by taking into account the stimulus phase. 
      Then, make a simple linear model fit (line + constant offset) of the response phase as a function
      of response amplitude.
      vSAVES loss/optimized parameters/and phase advance (if default "to_save" value is kept)
      RETURNS phAdv_model, all_opts

      Do ONLY for single gratings
  '''

  assert disp==0, "In phase_advance_fit; we only fit ph-amp relationship for single gratings."
  assert expInd>2, "In phase_advance_fit; we can only fit ph-amp relationship for experiments with \
                    careful component TF; expInd 1, 2 do not meet this requirement."

  dataList = hf.np_smart_load(data_loc + expName);
  cellStruct = hf.np_smart_load(data_loc + dataList['unitName'][cell_num-1] + '_sfm.npy');
  data = cellStruct['sfm']['exp']['trial'];
  phAdvName = hf.phase_fit_name(phAdvName, dir);

  # first, get the set of stimulus values:
  _, stimVals, valConByDisp, _, _ = hf.tabulate_responses(data, expInd);
  allCons = stimVals[1];
  allSfs = stimVals[2];

  # for all con/sf values for this dispersion, compute the mean amplitude/phase per condition
  allAmp, allPhi, allTf, _, _ = hf.get_all_fft(data, disp, expInd, dir=dir, all_trials=0); # all_trials=1 for debugging (0 is default)
  #pdb.set_trace();
     
  # now, compute the phase advance
  conInds = valConByDisp[disp];
  conVals = allCons[conInds];
  nConds = len(allAmp); # this is how many conditions are present for this dispersion
  # recall that nConds = nCons * nSfs
  allCons = [conVals] * nConds; # repeats list and nests
  phAdv_model, all_opts, all_phAdv, all_loss = hf.phase_advance(allAmp, allPhi, allCons, allTf);

  if os.path.isfile(data_loc + phAdvName):
      phFits = hf.np_smart_load(data_loc + phAdvName);
  else:
      phFits = dict();

  # update stuff - load again in case some other run has saved/made changes
  if os.path.isfile(data_loc + phAdvName):
      print('reloading phAdvFits...');
      phFits = hf.np_smart_load(data_loc + phAdvName);
  if cell_num-1 not in phFits:
    phFits[cell_num-1] = dict();
  phFits[cell_num-1]['loss'] = all_loss;
  phFits[cell_num-1]['params'] = all_opts;
  phFits[cell_num-1]['phAdv'] = all_phAdv;

  if to_save:
    np.save(data_loc + phAdvName, phFits);
    print('saving phase advance fit for cell ' + str(cell_num));

  return phAdv_model, all_opts;

def rvc_adjusted_fit(cell_num, data_loc, expInd, descrFitName_f0, rvcName=rvcName_f1, descrFitName_f1=None, to_save=1, disp=0, dir=-1, expName=expName, force_f1=False):
  ''' Piggy-backing off of phase_advance_fit above, get prepared to project the responses onto the proper phase to get the correct amplitude
      Then, with the corrected response amplitudes, fit the RVC model
  '''
  dataList = hf.np_smart_load(data_loc + expName);
  cellName = dataList['unitName'][cell_num-1];
  cellStruct = hf.np_smart_load(data_loc + cellName + '_sfm.npy');
  data = cellStruct['sfm']['exp']['trial'];
  rvcNameFinal = hf.phase_fit_name(rvcName, dir);
  expInd = hf.get_exp_ind(data_loc, cellName)[0];

  # before anything, let's get f1/f0 ratio
  f1f0 = hf.compute_f1f0(data, cell_num, expInd, data_loc, descrFitName_f0, descrFitName_f1)[0];

  # first, get the set of stimulus values:
  _, stimVals, valConByDisp, _, _ = hf.tabulate_responses(data, expInd);
  allCons = stimVals[1];
  allSfs = stimVals[2];
  try:
    valCons = allCons[valConByDisp[disp]];
  except:
    warnings.warn('This experiment does not have dispersion level %d; returning empty arrays' % disp);
    return [], [], [], [];
  #######
  ### Now, we fit the RVC
  #######
  if f1f0 > 1 or force_f1 is True: # i.e. simple cell
    # calling phase_advance fit, use the phAdv_model and optimized paramters to compute the true response amplitude
    # given the measured/observed amplitude and phase of the response
    # NOTE: We always call phase_advance_fit with disp=0 (default), since we don't make a fit
    # for the mixtrue stimuli - instead, we use the fits made on single gratings to project the
    # individual-component-in-mixture responses
    phAdv_model, all_opts = phase_advance_fit(cell_num, data_loc=data_loc, expInd=expInd, dir=dir, to_save = 0); # don't save
    allAmp, allPhi, _, allCompCon, allCompSf = hf.get_all_fft(data, disp, expInd, dir=dir, all_trials=1);
    # get just the mean amp/phi and put into convenient lists
    allAmpMeans = [[x[0] for x in sf] for sf in allAmp]; # mean is in the first element; do that for each [mean, std] pair in each list (split by sf)
    allAmpTrials = [[x[2] for x in sf] for sf in allAmp]; # trial-by-trial is third element 

    allPhiMeans = [[x[0] for x in sf] for sf in allPhi]; # mean is in the first element; do that for each [mean, var] pair in each list (split by sf)
    allPhiTrials = [[x[2] for x in sf] for sf in allPhi]; # trial-by-trial is third element 

    adjMeans   = hf.project_resp(allAmpMeans, allPhiMeans, phAdv_model, all_opts, disp, allCompSf, allSfs);
    adjByTrial = hf.project_resp(allAmpTrials, allPhiTrials, phAdv_model, all_opts, disp, allCompSf, allSfs);
    consRepeat = [valCons] * len(adjMeans);

    if disp > 0: # then we need to sum component responses and get overall std measure (we'll fit to sum, not indiv. comp responses!)
      adjSumResp  = [np.sum(x, 1) if x else [] for x in adjMeans];
      adjSemTr    = [[sem(np.sum(hf.switch_inner_outer(x), 1)) for x in y] for y in adjByTrial]
      adjSemCompTr  = [[sem(hf.switch_inner_outer(x)) for x in y] for y in adjByTrial];
      rvc_model, all_opts, all_conGains, all_loss = hf.rvc_fit(adjSumResp, consRepeat, adjSemTr);
    elif disp == 0:
      adjSemTr   = [[sem(x) for x in y] for y in adjByTrial];
      adjSemCompTr = adjSemTr; # for single gratings, there is only one component!
      rvc_model, all_opts, all_conGains, all_loss = hf.rvc_fit(adjMeans, consRepeat, adjSemTr);
  else: ### FIT RVC TO baseline-subtracted F0
    spikerate = hf.get_adjusted_spikerate(data, cell_num, expInd, data_loc, rvcName=None, descrFitName_f0=descrFitName_f0, descrFitName_f1=descrFitName_f1);
    # recall: rvc_fit wants adjMeans/consRepeat/adjSemTr organized as nSfs lists of nCons elements each (nested)
    respsOrg = hf.organize_resp(spikerate, data, expInd, respsAsRate=True)[3];
    #  -- so now, we organize
    adjMeans = []; adjSemTr = [];
    curr_cons = valConByDisp[disp];
    for sf_i, sf_val in enumerate(allSfs):
      # each list we add here should be of length nCons
      mnCurr = []; semCurr = [];
      for con_i in curr_cons:
        curr_resps = hf.nan_rm(respsOrg[disp, sf_i, con_i, :]);
        if np.array_equal(np.nan, curr_resps):
          mnCurr.append([]); semCurr.append([]);
        else:
          mnCurr.append(np.mean(curr_resps)); semCurr.append(sem(curr_resps));
      adjMeans.append(mnCurr); adjSemTr.append(semCurr);
    consRepeat = [allCons[curr_cons]] * len(adjMeans);
    rvc_model, all_opts, all_conGains, all_loss = hf.rvc_fit(adjMeans, consRepeat, adjSemTr);
    adjByTrial = spikerate;
    adjSemCompTr = []; # we're getting f0 - therefore cannot get individual component responses!

  if os.path.isfile(data_loc + rvcNameFinal):
      rvcFits = hf.np_smart_load(data_loc + rvcNameFinal);
  else:
      rvcFits = dict();

  # update stuff - load again in case some other run has saved/made changes
  if os.path.isfile(data_loc + rvcNameFinal):
    print('reloading rvcFits...');
    rvcFits = hf.np_smart_load(data_loc + rvcNameFinal);
  if cell_num-1 not in rvcFits:
    rvcFits[cell_num-1] = dict();
    rvcFits[cell_num-1][disp] = dict();
  else: # cell_num-1 is a key in rvcFits
    if disp not in rvcFits[cell_num-1]:
      rvcFits[cell_num-1][disp] = dict();

  rvcFits[cell_num-1][disp]['loss'] = all_loss;
  rvcFits[cell_num-1][disp]['params'] = all_opts;
  rvcFits[cell_num-1][disp]['conGain'] = all_conGains;
  rvcFits[cell_num-1][disp]['adjMeans'] = adjMeans;
  rvcFits[cell_num-1][disp]['adjByTr'] = adjByTrial
  rvcFits[cell_num-1][disp]['adjSem'] = adjSemTr;
  rvcFits[cell_num-1][disp]['adjSemComp'] = adjSemCompTr;

  if to_save:
    np.save(data_loc + rvcNameFinal, rvcFits);
    print('saving rvc fit for cell ' + str(cell_num));

  return rvc_model, all_opts, all_conGains, adjMeans;

### 1.1 RVC fits without adjusted responses (organized like SF tuning)

def fit_RVC_f0(cell_num, data_loc, n_repeats=500, fLname = rvcName_f0, dLname=expName, modelRecov=modelRecov, normType=normType):
  # NOTE: n_repeats not used (19.05.06)
  # normType used iff modelRecv == 1

  nParam = 3; # RVC model is 3 parameters only

  # load cell information
  dataList = hf.np_smart_load(data_loc + dLname);
  assert dataList!=[], "data file not found!"
  cellStruct = hf.np_smart_load(data_loc + dataList['unitName'][cell_num-1] + '_sfm.npy');
  data = cellStruct['sfm']['exp']['trial'];
  # get expInd, load rvcFits [if existing]
  expInd, expName = hf.get_exp_ind(data_loc, dataList['unitName'][cell_num-1]);
  print('Making RVC (F0) fits for cell %d in %s [%s]\n' % (cell_num,data_loc,expName));

  rvcName = fLname + '.npy';
  if os.path.isfile(data_loc + fLname):
      rvcFits = hf.np_smart_load(data_loc + fLname);
  else:
      rvcFits = dict();

  # now, get the spikes (recovery, if specified) and organize for fitting
  if modelRecov == 1:
    recovSpikes = hf.get_recovInfo(cellStruct, normType)[1];
  else:
    recovSpikes = None;
  spks = hf.get_spikes(data, rvcFits=None, expInd=expInd, overwriteSpikes=recovSpikes); # we say None for rvc (F1) fits
  _, _, resps_mean, resps_all = hf.organize_resp(spks, cellStruct, expInd);
  resps_sem = sem(resps_all, axis=-1, nan_policy='omit');
  
  print('Doing the work, now');

  # first, get the set of stimulus values:
  _, stimVals, valConByDisp, _, _ = hf.tabulate_responses(data, expInd);
  all_disps = stimVals[0];
  all_cons = stimVals[1];
  all_sfs = stimVals[2];
  
  nDisps = len(all_disps);
  nSfs = len(all_sfs);

  # Get existing fits
  if cell_num-1 in rvcFits:
    bestLoss = rvcFits[cell_num-1]['loss'];
    currParams = rvcFits[cell_num-1]['params'];
    conGains = rvcFits[cell_num-1]['conGain'];
  else: # set values to NaN...
    bestLoss = np.ones((nDisps, nSfs)) * np.nan;
    currParams = np.ones((nDisps, nSfs, nParam)) * np.nan;
    conGains = np.ones((nDisps, nSfs)) * np.nan;

  for d in range(nDisps): # works for all disps
    val_sfs = hf.get_valid_sfs(data, d, valConByDisp[d][0], expInd); # any valCon will have same sfs
    for sf in val_sfs:
      curr_conInd = valConByDisp[d];
      curr_conVals = all_cons[curr_conInd];
      curr_resps, curr_sem = resps_mean[d, sf, curr_conInd], resps_sem[d, sf, curr_conInd];
      # wrap in arrays, since rvc_fit is written for multiple rvc fits at once (i.e. vectorized)
      _, params, conGain, loss = hf.rvc_fit([curr_resps], [curr_conVals], [curr_sem], n_repeats=n_repeats);

      if (np.isnan(bestLoss[d, sf]) or loss < bestLoss[d, sf]) and params[0] != []: # i.e. params is not empty
        bestLoss[d, sf] = loss[0];
        currParams[d, sf, :] = params[0][:]; # "unpack" the array
        conGains[d, sf] = conGain[0];

  # update stuff - load again in case some other run has saved/made changes
  if os.path.isfile(data_loc + fLname):
    print('reloading RVC (F0) fits...');
    rvcFits = hf.np_smart_load(data_loc + fLname);
  if cell_num-1 not in rvcFits:
    rvcFits[cell_num-1] = dict();
  rvcFits[cell_num-1]['loss'] = bestLoss;
  rvcFits[cell_num-1]['params'] = currParams;
  rvcFits[cell_num-1]['conGain'] = conGains;

  np.save(data_loc + fLname, rvcFits);

#####################################

### 2: Descriptive tuning fit to (adjusted, if needed) responses
# previously, only difference of gaussian models; now (May 2019), we've also added the original flexible (i.e. two-halved) Gaussian model
# this is meant to be general for all experiments, so responses can be F0 or F1, and the responses will be the adjusted ones if needed

def invalid(params, bounds):
# given parameters and bounds, are the parameters valid?
  for p in range(len(params)):
    if params[p] < bounds[p][0] or params[p] > bounds[p][1]:
      return True;
  return False;

def DoG_loss(params, resps, sfs, loss_type = 3, DoGmodel=1, dir=-1, resps_std=None, gain_reg = 0):
  '''Given the model params (i.e. sach or tony formulation)), the responses, sf values
  return the loss
  loss_type: 1 - lsq
             2 - sqrt
             3 - poiss
             4 - Sach sum{[(exp-obs)^2]/[k+sigma^2]} where
                 k := 0.01*max(obs); sigma := measured variance of the response
  DoGmodel: 0 - flexGauss (not DoG...)
            1 - sach
            2 - tony
  '''
  # NOTE: See version in LGN/sach/ for how to fit trial-by-trial responses (rather than avg. resp)
  pred_spikes = hf.get_descrResp(params, sfs, DoGmodel);

  loss = 0;
  if loss_type == 1: # lsq
    loss = np.square(resps - pred_spikes);
    loss = loss + loss;
  elif loss_type == 2: # sqrt
    loss = np.sum(np.square(np.sqrt(resps) - np.sqrt(pred_spikes)));
    loss = loss + loss;
  elif loss_type == 3: # poisson model of spiking
    poiss = poisson.pmf(np.round(resps), pred_spikes); # round since the values are nearly but not quite integer values (Sach artifact?)...
    ps = np.sum(poiss == 0);
    if ps > 0:
      poiss = np.maximum(poiss, 1e-6); # anything, just so we avoid log(0)
    loss = loss + sum(-np.log(poiss));
  elif loss_type == 4: # sach's loss function
    k = 0.01*np.max(resps);
    if resps_std is None:
      sigma = np.ones_like(resps);
    else:
      sigma = resps_std;
    sq_err = np.square(resps-pred_spikes);
    loss = loss + np.sum((sq_err/(k+np.square(sigma)))) + gain_reg*(params[0] + params[2]); # regularize - want gains as low as possible
  return loss;

def fit_descr_DoG(cell_num, data_loc, n_repeats=1000, loss_type=3, DoGmodel=1, is_f0=0, get_rvc=1, dir=+1, gain_reg=0, fLname = dogName, dLname=expName, modelRecov=modelRecov, normType=normType):
  ''' This function is used to fit a descriptive tuning function to the spatial frequency responses of individual neurons
    
  '''

  if DoGmodel == 0:
    nParam = 5;
  else:
    nParam = 4;

  # load cell information
  dataList = hf.np_smart_load(data_loc + dLname);
  assert dataList!=[], "data file not found!"
  cellStruct = hf.np_smart_load(data_loc + dataList['unitName'][cell_num-1] + '_sfm.npy');
  data = cellStruct['sfm']['exp']['trial'];
  # get expInd, load rvcFits [if existing, and specified]
  expInd, expName = hf.get_exp_ind(data_loc, dataList['unitName'][cell_num-1]);
  print('Making descriptive SF fits for cell %d in %s [%s]\n' % (cell_num,data_loc,expName));
  if is_f0 == 0 and get_rvc == 1:
    rvcFits = hf.get_rvc_fits(data_loc, expInd, cell_num); # see default arguments in helper_fcns.py
  else:
    rvcFits = None;

  modStr  = hf.descrMod_name(DoGmodel)
  fLname  = hf.descrFit_name(loss_type, descrBase=fLname, modelName=modStr);
  if os.path.isfile(data_loc + fLname):
      descrFits = hf.np_smart_load(data_loc + fLname);
  else:
      descrFits = dict();

  # now, get the spikes (adjusted, if needed) and organize for fitting
  # TODO: Add recovery spikes...
  if modelRecov == 1:
    recovSpikes = hf.get_recovInfo(cellStruct, normType)[1];
  else:
    recovSpikes = None;
  spks = hf.get_spikes(data, rvcFits, expInd, overwriteSpikes=recovSpikes);
  _, _, resps_mean, resps_all = hf.organize_resp(spks, cellStruct, expInd);
  resps_sem = sem(resps_all, axis=-1, nan_policy='omit');
  
  print('Doing the work, now');

  # first, get the set of stimulus values:
  _, stimVals, valConByDisp, validByStimVal, _ = hf.tabulate_responses(data, expInd);
  all_disps = stimVals[0];
  all_cons = stimVals[1];
  all_sfs = stimVals[2];

  nDisps = len(all_disps);
  nCons = len(all_cons);

  if cell_num-1 in descrFits:
    bestNLL = descrFits[cell_num-1]['NLL'];
    currParams = descrFits[cell_num-1]['params'];
    varExpl = descrFits[cell_num-1]['varExpl'];
    prefSf = descrFits[cell_num-1]['prefSf'];
    charFreq = descrFits[cell_num-1]['charFreq'];
  else: # set values to NaN...
    bestNLL = np.ones((nDisps, nCons)) * np.nan;
    currParams = np.ones((nDisps, nCons, nParam)) * np.nan;
    varExpl = np.ones((nDisps, nCons)) * np.nan;
    prefSf = np.ones((nDisps, nCons)) * np.nan;
    charFreq = np.ones((nDisps, nCons)) * np.nan;

  # next, let's compute some measures abougt the responses
  max_resp = np.nanmax(resps_all);
  base_rate = hf.blankResp(cellStruct, expInd)[0];

  # set bounds
  if DoGmodel == 0: # flexible gaussian (i.e. two halves)
    min_bw = 1/4; max_bw = 10; # ranges in octave bandwidth
    bound_baseline = (0, max_resp);
    bound_range = (0, 1.5*max_resp);
    bound_mu = (0.01, 10);
    bound_sig = (np.maximum(0.1, min_bw/(2*np.sqrt(2*np.log(2)))), max_bw/(2*np.sqrt(2*np.log(2)))); # Gaussian at half-height
    allBounds = (bound_baseline, bound_range, bound_mu, bound_sig, bound_sig);
  elif DoGmodel == 1: # SACH
    bound_gainCent = (1e-3, None);
    bound_radiusCent= (1e-3, None);
    bound_gainSurr = (1e-3, None);
    bound_radiusSurr= (1e-3, None);
    allBounds = (bound_gainCent, bound_radiusCent, bound_gainSurr, bound_radiusSurr);
  elif DoGmodel == 2: # TONY
    bound_gainCent = (1e-3, None);
    bound_gainFracSurr = (1e-2, 1);
    bound_freqCent = (1e-3, None);
    bound_freqFracSurr = (1e-2, 1);
    allBounds = (bound_gainCent, bound_freqCent, bound_gainFracSurr, bound_freqFracSurr);

  for d in range(nDisps): # works for all disps
    for con in range(nCons):
      if con not in valConByDisp[d]:
        continue;

      valSfInds = hf.get_valid_sfs(data, d, con, expInd, stimVals, validByStimVal);
      valSfVals = all_sfs[valSfInds];

      print('.');
      respConInd = np.where(np.asarray(valConByDisp[d]) == con)[0];
      resps_curr = resps_mean[d, valSfInds, con];
      sem_curr   = resps_sem[d, valSfInds, con];
      maxResp       = np.max(resps_curr);
      freqAtMaxResp = all_sfs[np.argmax(resps_curr)];

      for n_try in range(n_repeats):

        ###########
        ### pick initial params
        ###########
        ## FLEX (not difference of gaussian)
        if DoGmodel == 0:
          # set initial parameters - a range from which we will pick!
          if base_rate <= 3:
              range_baseline = (0, 3);
          else:
              range_baseline = (0.5 * base_rate, 1.5 * base_rate);
          range_amp = (0.5 * max_resp, 1.25 * max_resp);

          max_sf_index = np.argmax(resps_curr); # what sf index gives peak response?
          mu_init = valSfVals[max_sf_index];

          if max_sf_index == 0: # i.e. smallest SF center gives max response...
              range_mu = (mu_init/2, valSfVals[max_sf_index + 3]);
          elif max_sf_index+1 == len(valSfVals): # i.e. highest SF center is max
              range_mu = (valSfVals[max_sf_index-3], mu_init);
          else:
              range_mu = (valSfVals[max_sf_index-1], valSfVals[max_sf_index+1]); # go +-1 indices from center

          log_bw_lo = 0.75; # 0.75 octave bandwidth...
          log_bw_hi = 2; # 2 octave bandwidth...
          denom_lo = hf.bw_log_to_lin(log_bw_lo, mu_init)[0]; # get linear bandwidth
          denom_hi = hf.bw_log_to_lin(log_bw_hi, mu_init)[0]; # get lin. bw (cpd)
          range_denom = (denom_lo, denom_hi); # don't want 0 in sigma 

          init_base = hf.random_in_range(range_baseline);
          init_amp = hf.random_in_range(range_amp);
          init_mu = hf.random_in_range(range_mu);
          init_sig_left = hf.random_in_range(range_denom);
          init_sig_right = hf.random_in_range(range_denom);
          init_params = [init_base, init_amp, init_mu, init_sig_left, init_sig_right];
        ## SACH
        elif DoGmodel == 1:
          init_gainCent = hf.random_in_range((maxResp, 5*maxResp))[0];
          init_radiusCent = hf.random_in_range((0.05, 2))[0];
          init_gainSurr = init_gainCent * hf.random_in_range((0.1, 0.95))[0];
          init_radiusSurr = init_radiusCent * hf.random_in_range((1.25, 8))[0];
          init_params = [init_gainCent, init_radiusCent, init_gainSurr, init_radiusSurr];
        ## TONY
        elif DoGmodel == 2:
          init_gainCent = maxResp * hf.random_in_range((0.9, 1.2))[0];
          init_freqCent = np.maximum(all_sfs[2], freqAtMaxResp * hf.random_in_range((1.2, 1.5))[0]); # don't pick all_sfs[0] -- that's zero (we're avoiding that)
          init_gainFracSurr = hf.random_in_range((0.7, 1))[0];
          init_freqFracSurr = hf.random_in_range((.25, .35))[0];
          init_params = [init_gainCent, init_freqCent, init_gainFracSurr, init_freqFracSurr];

        # choose optimization method
        if np.mod(n_try, 2) == 0:
            methodStr = 'L-BFGS-B';
        else:
            methodStr = 'TNC';
        obj = lambda params: DoG_loss(params, resps_curr, valSfVals, resps_std=sem_curr, loss_type=loss_type, DoGmodel=DoGmodel, dir=dir, gain_reg=gain_reg);
        wax = opt.minimize(obj, init_params, method=methodStr, bounds=allBounds);

        # compare
        NLL = wax['fun'];
        params = wax['x'];

        if np.isnan(bestNLL[d, con]) or NLL < bestNLL[d, con]:
          bestNLL[d, con] = NLL;
          currParams[d, con, :] = params;
          varExpl[d, con] = hf.var_explained(resps_curr, params, valSfVals, DoGmodel);
          prefSf[d, con] = hf.dog_prefSf(params, dog_model=DoGmodel, all_sfs=valSfVals);
          charFreq[d, con] = hf.dog_charFreq(params, DoGmodel=DoGmodel);

    # update stuff - load again in case some other run has saved/made changes
    if os.path.isfile(data_loc + fLname):
      print('reloading descrFits...');
      descrFits = hf.np_smart_load(data_loc + fLname);
    if cell_num-1 not in descrFits:
      descrFits[cell_num-1] = dict();
    descrFits[cell_num-1]['NLL'] = bestNLL;
    descrFits[cell_num-1]['params'] = currParams;
    descrFits[cell_num-1]['varExpl'] = varExpl;
    descrFits[cell_num-1]['prefSf'] = prefSf;
    descrFits[cell_num-1]['charFreq'] = charFreq;
    descrFits[cell_num-1]['gainRegFactor'] = gain_reg;

    np.save(data_loc + fLname, descrFits);
    print('saving for cell ' + str(cell_num));

### Fin: Run the stuff!

if __name__ == '__main__':

    if len(sys.argv) < 2:
      print('uhoh...you need at least one argument(s) here');
      exit();

    cell_num   = int(sys.argv[1]);
    disp       = int(sys.argv[2]);
    data_dir   = sys.argv[3];
    ph_fits    = int(sys.argv[4]);
    rvc_fits   = int(sys.argv[5]);
    rvcF0_fits   = int(sys.argv[6]);
    descr_fits = int(sys.argv[7]);
    dog_model  = int(sys.argv[8]);
    loss_type  = int(sys.argv[9]);
    if len(sys.argv) > 10:
      dir = float(sys.argv[10]);
    else:
      dir = None;
    if len(sys.argv) > 11:
      gainReg = float(sys.argv[11]);
    else:
      gainReg = 0;
    print('Running cell %d in %s' % (cell_num, expName));

    # get the full data directory
    dataPath = basePath + data_dir + data_suff;
    # get the expInd
    dL = hf.np_smart_load(dataPath + expName);
    unitName = dL['unitName'][cell_num-1];
    expInd = hf.get_exp_ind(dataPath, unitName)[0];

    # then, put what to run here...
    if dir == None:
      if ph_fits == 1:
        phase_advance_fit(cell_num, data_loc=dataPath, expInd=expInd, disp=disp);
      if rvc_fits == 1:
        rvc_adjusted_fit(cell_num, data_loc=dataPath, expInd=expInd, descrFitName_f0=df_f0, disp=disp);
      if descr_fits == 1:
        fit_descr_DoG(cell_num, data_loc=dataPath, gain_reg=gainReg, DoGmodel=dog_model, loss_type=loss_type);
    else:
      if ph_fits == 1:
        phase_advance_fit(cell_num, data_loc=dataPath, expInd=expInd, disp=disp, dir=dir);
      if rvc_fits == 1:
        rvc_adjusted_fit(cell_num, data_loc=dataPath, expInd=expInd, descrFitName_f0=df_f0, disp=disp, dir=dir);
      if descr_fits == 1:
        fit_descr_DoG(cell_num, data_loc=dataPath, gain_reg=gainReg, dir=dir, DoGmodel=dog_model, loss_type=loss_type);

    if rvcF0_fits == 1:
      fit_RVC_f0(cell_num, data_loc=dataPath);
