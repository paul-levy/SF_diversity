import numpy as np
import model_responses as mod_resp
import helper_fcns as hfunc
import scipy.optimize as opt
from scipy.stats import norm, mode, lognorm, nbinom, poisson
from numpy.matlib import repmat
import os.path
import sys

import pdb

def invalid(params, bounds):
# given parameters and bounds, are the parameters valid?
  for p in range(len(params)):
    if params[p] < bounds[p][0] or params[p] > bounds[p][1]:
      return True;
  return False;
    

def flexible_Gauss(params, stim_sf):
    # The descriptive model used to fit cell tuning curves - in this way, we
    # can read off preferred SF, octave bandwidth, and response amplitude

    respFloor       = params[0];
    respRelFloor    = params[1];
    sfPref          = params[2];
    sigmaLow        = params[3];
    sigmaHigh       = params[4];
 
    # Tuning function
    sf0   = stim_sf / sfPref;

    # set the sigma - left half (i.e. sf0<1) is sigmaLow; right half (sf0>1) is sigmaHigh
    sigma = sigmaLow * np.ones(len(stim_sf));
    sigma[sf0 > 1] = sigmaHigh;

    shape = np.exp(-np.square(np.log(sf0)) / (2*np.square(sigma)));
                
    return np.maximum(0.1, respFloor + respRelFloor*shape);

def descr_loss(params, data, family, contrast, loss_type = 1):
    
    # set constants
    epsilon = 1e-4;
    trial = data['sfm']['exp']['trial'];

    # find NaN trials...
    mask = np.isnan(trial['ori'][0]); # sum over all stim components...if there are any nans in that trial, we know
    fixedOr = trial['ori'][0][~mask];
    fixedCon = trial['con'][0][~mask];
    fixedSf = trial['sf'][0][~mask];
    fixedSpikes = trial['spikeCount'][~mask];
    fixedDur = trial['duration'][~mask];

    # get indices for trials we want to look at
    center_con = hfunc.get_center_con(family+1, contrast+1);
    ori_pref = mode(fixedOr).mode;

    con_check = abs(fixedCon - center_con) < epsilon;
    ori_check = abs(fixedOr - ori_pref) < epsilon;

    sf_check = np.zeros_like(con_check);

    # get all the possible sf centers (at high contrast...but same at low, anyway)
    sf_centers = data['sfm']['exp']['sf'][0][0];

    for sf_i in sf_centers:
        sf_check[fixedSf == sf_i] = 1;

    indices = np.where(con_check & ori_check & sf_check); 
    
    obs_count = fixedSpikes[indices];

    pred_rate = flexible_Gauss(params, fixedSf[indices]);
    stim_dur = fixedDur[indices];

    if loss_type == 1: # lsq
      curr_loss = np.square(pred_rate * stim_dur - obs_count);
      NLL = sum(curr_loss);
    elif loss_type == 2: # sqrt
      curr_loss = np.square(np.sqrt(pred_rate * stim_dur) - np.sqrt(obs_count));
      NLL = sum(curr_loss);
    elif loss_type == 3: # poiss
      # poisson model of spiking
      poiss = poisson.pmf(obs_count, pred_rate * stim_dur);
      ps = np.sum(poiss == 0);
      if ps > 0:
        poiss = np.maximum(poiss, 1e-6); # anything, just so we avoid log(0)
      NLL = sum(-np.log(poiss));
    
    return NLL;

def fit_descr(cell_num, data_loc, n_repeats = 4, fromModelSim = 0, fitLossType=1, baseStr=None, normType=None, lossType=None):
    
    nFam = 5;
    nCon = 2;
    nParam = 5;

    # get base descrFit name (including loss str)
    if fitLossType == 1:
      floss_str = '_lsq';    
    elif fitLossType == 2:
      floss_str = '_sqrt';    
    elif fitLossType == 3:
      floss_str = '_poiss';
    descrFitBase = 'descrFits%s' % floss_str;
    
    # load cell information
    dataList = hfunc.np_smart_load(data_loc + 'dataList.npy');
    if fromModelSim:
      # get model fit name
      fL_name = baseStr;

      # normType
      if normType == 1:
        fL_suffix1 = '_flat';
      elif normType == 2:
        fL_suffix1 = '_wght';
      elif normType == 3:
        fL_suffix1 = '_c50';
      # lossType
      if lossType == 1:
        fL_suffix2 = '_sqrt.npy';
      elif lossType == 2:
        fL_suffix2 = '_poiss.npy';
      elif lossType == 3:
        fL_suffix2 = '_modPoiss.npy';
      elif lossType == 4:
        fL_suffix2 = '_chiSq.npy';
      fitListName = str(fL_name + fL_suffix1 + fL_suffix2);

      dfModelName = '%s_%s' % (descrFitBase, fitListName);

      if os.path.isfile(data_loc + dfModelName):
          descrFits = hfunc.np_smart_load(data_loc + dfModelName);
      else:
          descrFits = dict();
    else:
      dfModelName = '%s.npy' % descrFitBase;
      if os.path.isfile(data_loc + dfModelName):
          descrFits = hfunc.np_smart_load(data_loc + dfModelName);
      else:
          descrFits = dict();
    data = hfunc.np_smart_load(data_loc + dataList['unitName'][cell_num-1] + '_sfm.npy');
    
    if fromModelSim: # then we'll 'sneak' in the model responses in the place of the real data
        modFits = hfunc.np_smart_load(data_loc + fitListName);
        modFit = modFits[cell_num-1]['params'];
        a, modResp = mod_resp.SFMGiveBof(modFit, data, normType=normType, lossType=lossType);
        # spike count must be integers! Simply round
        data['sfm']['exp']['trial']['spikeCount'] = np.round(modResp * data['sfm']['exp']['trial']['duration']); 

    if cell_num-1 in descrFits:
        bestNLL = descrFits[cell_num-1]['NLL'];
        currParams = descrFits[cell_num-1]['params'];
    else: # set values to NaN...
        bestNLL = np.ones((nFam, nCon)) * np.nan;
        currParams = np.ones((nFam, nCon, nParam)) * np.nan;
    
    print('Doing the work, now');
    for family in range(nFam):
        for con in range(nCon):    

            print('.');           
            # set initial parameters - a range from which we will pick!
            base_rate = data['sfm']['exp']['sponRateMean']
            if base_rate <= 3:
                range_baseline = (0, 3);
            else:
                range_baseline = (0.5 * base_rate, 1.5 * base_rate);

            max_resp = np.amax(data['sfm']['exp']['sfRateMean'][family][con]);
            range_amp = (0.5 * max_resp, 1.5);
            
            theSfCents = data['sfm']['exp']['sf'][family][con];
            
            max_sf_index = np.argmax(data['sfm']['exp']['sfRateMean'][family][con]); # what sf index gives peak response?
            mu_init = theSfCents[max_sf_index];
            
            if max_sf_index == 0: # i.e. smallest SF center gives max response...
                range_mu = (mu_init/2,theSfCents[max_sf_index + 3]);
            elif max_sf_index+1 == len(theSfCents): # i.e. highest SF center is max
                range_mu = (theSfCents[max_sf_index-3], mu_init);
            else:
                range_mu = (theSfCents[max_sf_index-1], theSfCents[max_sf_index+1]); # go +-1 indices from center
                
            log_bw_lo = 0.75; # 0.75 octave bandwidth...
            log_bw_hi = 2; # 2 octave bandwidth...
            denom_lo = hfunc.bw_log_to_lin(log_bw_lo, mu_init)[0]; # get linear bandwidth
            denom_hi = hfunc.bw_log_to_lin(log_bw_hi, mu_init)[0]; # get lin. bw (cpd)
            range_denom = (denom_lo, denom_hi); # don't want 0 in sigma 
                
            # set bounds for parameters
            min_bw = 1/4; max_bw = 10; # ranges in octave bandwidth

            bound_baseline = (0, max_resp);
            bound_range = (0, 1.5*max_resp);
            bound_mu = (0.01, 10);
            bound_sig = (np.maximum(0.1, min_bw/(2*np.sqrt(2*np.log(2)))), max_bw/(2*np.sqrt(2*np.log(2)))); # Gaussian at half-height
            
            all_bounds = (bound_baseline, bound_range, bound_mu, bound_sig, bound_sig);

            for n_try in range(n_repeats):
                
                # pick initial params
                init_base = hfunc.random_in_range(range_baseline);
                init_amp = hfunc.random_in_range(range_amp);
                init_mu = hfunc.random_in_range(range_mu);
                init_sig_left = hfunc.random_in_range(range_denom);
                init_sig_right = hfunc.random_in_range(range_denom);
                         
                init_params = [init_base, init_amp, init_mu, init_sig_left, init_sig_right];
                         
                # choose optimization method
                if np.mod(n_try, 2) == 0:
                    methodStr = 'L-BFGS-B';
                else:
                    methodStr = 'TNC';
                
                obj = lambda params: descr_loss(params, data, family, con);
                wax = opt.minimize(obj, init_params, method=methodStr, bounds=all_bounds);
                
                # compare
                NLL = wax['fun'];
                params = wax['x'];

                if np.isnan(bestNLL[family, con]) or NLL < bestNLL[family, con] or invalid(currParams[family, con, :], all_bounds):
                    bestNLL[family, con] = NLL;
                    currParams[family, con, :] = params;

    # update stuff - load again in case some other run has saved/made changes
    if os.path.isfile(data_loc + dfModelName):
      print('reloading descrFitsModel...');
      descrFits = hfunc.np_smart_load(data_loc + dfModelName)
    if cell_num-1 not in descrFits:
      descrFits[cell_num-1] = dict();
    descrFits[cell_num-1]['NLL'] = bestNLL;
    descrFits[cell_num-1]['params'] = currParams;

    np.save(data_loc + dfModelName, descrFits);
    print('saving for cell ' + str(cell_num));
                
if __name__ == '__main__':

    #data_loc = '/home/pl1465/SF_diversity/Analysis/Structures/'; # prince
    data_loc = '/arc/2.2/p1/plevy/SF_diversity/sfDiv-OriModel/sfDiv-python/Analysis/Structures/'; # CNS

    if len(sys.argv) < 3:
      print('uhoh...you need at least two arguments here'); # and one is the script itself...
      print('First should be cell number, second is number of fit iterations');
      exit();

    print('Running cell ' + sys.argv[1] + '...');

    if len(sys.argv) > 5:
      print(' for ' + sys.argv[2] + ' iterations on model data? ' + sys.argv[3]);
      # args: cellNum dataLoc, #reps, fromModelSim, baseStr, normType, lossType
      fit_descr(int(sys.argv[1]), data_loc, int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], int(sys.argv[6]), int(sys.argv[7]));
    elif len(sys.argv) > 4:
      print(' for ' + sys.argv[2] + ' iterations on model data? ' + sys.argv[3]);
      fit_descr(int(sys.argv[1]), data_loc, int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]));
    elif len(sys.argv) > 3:
      print(' for ' + sys.argv[2] + ' iterations on model data? ' + sys.argv[3]);
      fit_descr(int(sys.argv[1]), data_loc, int(sys.argv[2]), int(sys.argv[3]));
    elif len(sys.argv) > 2: # specify number of fit iterations
      print(' for ' + sys.argv[2] + ' iterations');
      fit_descr(int(sys.argv[1]), data_loc, int(sys.argv[2]));
    else: # all trials in each iteration
      fit_descr(int(sys.argv[1]), data_loc);

