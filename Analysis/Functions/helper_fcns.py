import math, numpy, random, os
from scipy.stats import norm, mode, poisson, nbinom
from scipy.stats.mstats import gmean as geomean
from numpy.matlib import repmat
from time import sleep
import scipy.optimize as opt
sqrt = math.sqrt
log = math.log
exp = math.exp
import pdb

# Functions:
# np_smart_load     - load a .npy file safely
# bw_lin_to_log
# bw_log_to_lin
# chiSq

# deriv_gauss       - evaluate a derivative of a gaussian, specifying the derivative order and peak
# compute_SF_BW     - returns the log bandwidth for height H given a fit with parameters and height H (e.g. half-height)
# fix_params        - Intended for parameters of flexible Gaussian, makes all parameters non-negative
# flexible_Gauss    - Descriptive function used to describe/fit SF tuning
# get_center_con    - given a family and contrast index, returns the contrast level
# tabulateResponses - Organizes measured and model responses for sfMixAlt experiment
# random_in_range    - random real-valued number between A and B
# nbinpdf_log        - was used with sfMix optimization to compute the negative binomial probability (likelihood) for a predicted rate given the measured spike count
# getSuppressiveSFtuning - returns the normalization pool response
# makeStimulus       - was used last for sfMix experiment to generate arbitrary stimuli for use with evaluating model
# getNormParams  - given the model params and fit type, return the relevant parameters for normalization
# genNormWeights     - used to generate the weighting matrix for weighting normalization pool responses
# setSigmaFilter     - create the filter we use for determining c50 with SF
# evalSigmaFilter    - evaluate an arbitrary filter at a set of spatial frequencies to determine c50 (semisaturation contrast)
# setNormTypeArr     - create the normTypeArr used in SFMGiveBof/Simulate to determine the type of normalization and corresponding parameters
# getConstraints     - get list of constraints for optimization

def np_smart_load(file_path, encoding_str='latin1'):

   if not os.path.isfile(file_path):
     return [];
   loaded = [];
   while(True):
     try:
         loaded = numpy.load(file_path, encoding=encoding_str).item();
         break;
     except IOError: # this happens, I believe, because of parallelization when running on the cluster; cannot properly open file, so let's wait and then try again
         sleep(10); # i.e. wait for 10 seconds
     except EOFError: # this happens, I believe, because of parallelization when running on the cluster; cannot properly open file, so let's wait and then try again
         sleep(10); # i.e. wait for 5 seconds

   return loaded;

def bw_lin_to_log( lin_low, lin_high ):
    # Given the low/high sf in cpd, returns number of octaves separating the
    # two values

    return numpy.log2(lin_high/lin_low);

def bw_log_to_lin(log_bw, pref_sf):
    # given the preferred SF and octave bandwidth, returns the corresponding
    # (linear) bounds in cpd

    less_half = numpy.power(2, numpy.log2(pref_sf) - log_bw/2);
    more_half = numpy.power(2, log_bw/2 + numpy.log2(pref_sf));

    sf_range = [less_half, more_half];
    lin_bw = more_half - less_half;
    
    return lin_bw, sf_range

def chiSq(data_resps, model_resps, stimDur=1):
  ''' given a set of measured and model responses, compute the chi-squared (see Cavanaugh et al '02a)
      assumes: resps are mean/variance for each stimulus condition (e.g. like a tuning curve)
        with each condition a tuple (or 2-array) with [mean, var]
  '''
  np = numpy;
  rats = np.divide(data_resps[1], data_resps[0]);
  nan_rm = lambda x: x[~np.isnan(x)]
  rho = geomean(nan_rm(rats));
  k   = 0.10 * rho * np.nanmax(data_resps[0]) # default kMult from Cavanaugh is 0.01

  chi = np.sum(np.divide(np.square(data_resps[0] - model_resps[0]), k + data_resps[0]*rho/stimDur));

  return chi;

######

def deriv_gauss(params, stimSf = numpy.logspace(numpy.log10(0.1), numpy.log10(10), 101)):

    prefSf = params[0];
    dOrdSp = params[1];

    sfRel = stimSf / prefSf;
    s     = pow(stimSf, dOrdSp) * numpy.exp(-dOrdSp/2 * pow(sfRel, 2));
    sMax  = pow(prefSf, dOrdSp) * numpy.exp(-dOrdSp/2);
    sNl   = s/sMax;
    selSf = sNl;

    return selSf, stimSf;


def compute_SF_BW(fit, height, sf_range):

    # 1/16/17 - This was corrected in the lead up to SfN (sometime 11/16). I had been computing
    # octaves not in log2 but rather in log10 - it is field convention to use
    # log2!

    # Height is defined RELATIVE to baseline
    # i.e. baseline = 10, peak = 50, then half height is NOT 25 but 30
    
    bw_log = numpy.nan;
    SF = numpy.empty((2, 1));
    SF[:] = numpy.nan;

    # left-half
    left_full_bw = 2 * (fit[3] * sqrt(2*log(1/height)));
    left_cpd = fit[2] * exp(-(fit[3] * sqrt(2*log(1/height))));

    # right-half
    right_full_bw = 2 * (fit[4] * sqrt(2*log(1/height)));
    right_cpd = fit[2] * math.exp((fit[4] * sqrt(2*math.log(1/height))));

    if left_cpd > sf_range[0] and right_cpd < sf_range[-1]:
        SF = [left_cpd, right_cpd];
        bw_log = log(right_cpd / left_cpd, 2);

    # otherwise we don't have defined BW!
    
    return SF, bw_log

def fix_params(params_in):

    # simply makes all input arguments positive
 
    # R(Sf) = R0 + K_e * EXP(-(SF-mu)^2 / 2*(sig_e)^2) - K_i * EXP(-(SF-mu)^2 / 2*(sig_i)^2)

    return [abs(x) for x in params_in] 

def flexible_Gauss(params, stim_sf, minThresh=0.1):
    # The descriptive model used to fit cell tuning curves - in this way, we
    # can read off preferred SF, octave bandwidth, and response amplitude

    respFloor       = params[0];
    respRelFloor    = params[1];
    sfPref          = params[2];
    sigmaLow        = params[3];
    sigmaHigh       = params[4];

    # Tuning function
    sf0   = [x/sfPref for x in stim_sf];

    sigma = numpy.multiply(sigmaLow, [1]*len(sf0));

    sigma[[x for x in range(len(sf0)) if sf0[x] > 1]] = sigmaHigh;

    # hashtag:uglyPython
    shape = [math.exp(-pow(math.log(x), 2) / (2*pow(y, 2))) for x, y in zip(sf0, sigma)];
                
    return [max(minThresh, respFloor + respRelFloor*x) for x in shape];

def get_center_con(family, contrast):

    # hardcoded - based on sfMix as run in 2015/2016 (m657, m658, m660); given
    # the stimulus family and contrast level, returns the expected contrast of
    # the center frequency.
    
    # contrast = 1 means high contrast...otherwise, low contrast

    con = numpy.nan
    
    if family == 1:
        if contrast == 1:
            con = 1.0000;
        else:
            con = 0.3300;
    elif family == 2:
        if contrast == 1:
            con = 0.6717;
        else:
            con = 0.2217;
    elif family == 3:
        if contrast == 1:
            con = 0.3785;
        else:
            con = 0.1249;
    elif family == 4:
        if contrast == 1:
            con = 0.2161;
        else:
            con = 0.0713;
    elif family == 5:
        if contrast == 1:
            con = 0.1451;
        else:
            con = 0.0479;

    return con

def organize_modResp(modResp, expStructure):
    # the blockIDs are fixed...
    nFam = 5;
    nCon = 2;
    nCond = 11; # 11 sfCenters for sfMix
    nReps = 20; # never more than 20 reps per stim. condition
    
    # Analyze the stimulus-driven responses for the orientation tuning curve
    oriBlockIDs = numpy.hstack((numpy.arange(131, 155+1, 2), numpy.arange(132, 136+1, 2))); # +1 to include endpoint like Matlab

    rateOr = numpy.empty((0,));
    for iB in oriBlockIDs:
        indCond = numpy.where(expStructure['blockID'] == iB);
        if len(indCond[0]) > 0:
            rateOr = numpy.append(rateOr, numpy.mean(modResp[indCond]));
        else:
            rateOr = numpy.append(rateOr, numpy.nan);

    #pdb.set_trace();

    # Analyze the stimulus-driven responses for the contrast response function
    conBlockIDs = numpy.arange(138, 156+1, 2);
    iC = 0;

    rateCo = numpy.empty((0,));
    for iB in conBlockIDs:
        indCond = numpy.where(expStructure['blockID'] == iB);   
        if len(indCond[0]) > 0:
            rateCo = numpy.append(rateCo, numpy.mean(modResp[indCond]));
        else:
            rateCo = numpy.append(rateCo, numpy.nan);

    # Analyze the stimulus-driven responses for the spatial frequency mixtures

    # Initialize Variables        
    rateSfMix = numpy.ones((nFam, nCon, nCond)) * numpy.nan;
    allSfMix = numpy.ones((nFam, nCon, nCond, nReps)) * numpy.nan;
    for iE in range(nCon):
        for iW in range(nFam):

            StimBlockIDs  = numpy.arange(((iW)*(13*2)+1)+(iE), 1+((iW+1)*(13*2)-5)+(iE), 2);
            nStimBlockIDs = len(StimBlockIDs);
            #print('nStimBlockIDs = ' + str(nStimBlockIDs));
        
            iC = 0;

            for iB in StimBlockIDs:
                indCond = numpy.where(expStructure['blockID'] == iB);   
                if len(indCond[0]) > 0:
                    #print('setting up ' + str((iE, iW, iC)) + ' with ' + str(len(indCond[0])) + 'trials');
                    rateSfMix[iW, iE, iC] = numpy.nanmean(modResp[indCond]);
                    allSfMix[iW, iE, iC, 0:len(indCond[0])] = modResp[indCond];
                    iC         = iC+1;
                 
    return rateOr, rateCo, rateSfMix, allSfMix;

def mod_poiss(mu, varGain):
    np = numpy;
    var = mu + (varGain * np.power(mu, 2));                        # The corresponding variance of the spike count
    r   = np.power(mu, 2) / (var - mu);                           # The parameters r and p of the negative binomial distribution
    p   = r/(r + mu)

    return r, p

def naka_rushton(con, params):
    np = numpy;
    base = params[0];
    gain = params[1];
    expon = params[2];
    c50 = params[3];

    return base + gain*np.divide(np.power(con, expon), np.power(con, expon) + np.power(c50, expon));

def fit_CRF(cons, resps, nr_c50, nr_expn, nr_gain, nr_base, v_varGain, fit_type):
	# fit_type (i.e. which loss function):
		# 1 - least squares
		# 2 - square root
		# 3 - poisson
		# 4 - modulated poisson
    np = numpy;

    n_sfs = len(resps);

    # Evaluate the model
    loss_by_sf = np.zeros((n_sfs, 1));
    for sf in range(n_sfs):
        all_params = (nr_c50, nr_expn, nr_gain, nr_base);
        param_ind = [0 if len(i) == 1 else sf for i in all_params];

        nr_args = [nr_base[param_ind[3]], nr_gain[param_ind[2]], nr_expn[param_ind[1]], nr_c50[param_ind[0]]]; 
	# evaluate the model
        pred = naka_rushton(cons[sf], nr_args); # ensure we don't have pred (lambda) = 0 --> log will "blow up"
        
        if fit_type == 4:
	  # Get predicted spike count distributions
          mu  = pred; # The predicted mean spike count; respModel[iR]
          var = mu + (v_varGain * np.power(mu, 2));                        # The corresponding variance of the spike count
          r   = np.power(mu, 2) / (var - mu);                           # The parameters r and p of the negative binomial distribution
          p   = r/(r + mu);
          # no elif/else

        if fit_type == 1 or fit_type == 2:
          # error calculation
          if fit_type == 1:
            loss = lambda resp, pred: np.sum(np.power(resp-pred, 2)); # least-squares, for now...
          if fit_type == 2:
            loss = lambda resp, pred: np.sum(np.square(np.sqrt(resp) - np.sqrt(pred)));

          curr_loss = loss(resps[sf], pred);
          loss_by_sf[sf] = np.sum(curr_loss);

        else:
	  # if likelihood calculation
          if fit_type == 3:
            loss = lambda resp, pred: poisson.logpmf(resp, pred);
            curr_loss = loss(resps[sf], pred); # already log
          if fit_type == 4:
            loss = lambda resp, r, p: np.log(nbinom.pmf(resp, r, p)); # Likelihood for each pass under doubly stochastic model
            curr_loss = loss(resps[sf], r, p); # already log
          loss_by_sf[sf] = -np.sum(curr_loss); # negate if LLH

    return np.sum(loss_by_sf);

def random_in_range(lims, size = 1):

    return [random.uniform(lims[0], lims[1]) for i in range(size)]

def nbinpdf_log(x, r, p):
    from scipy.special import loggamma as lgamma

    # We assume that r & p are tf placeholders/variables; x is a constant
    # Negative binomial is:
        # gamma(x+r) * (1-p)^x * p^r / (gamma(x+1) * gamma(r))
    
    # Here we return the log negBinomial:
    noGamma = x * numpy.log(1-p) + (r * numpy.log(p));
    withGamma = lgamma(x + r) - lgamma(x + 1) - lgamma(r);
    
    return numpy.real(noGamma + withGamma);

def getSuppressiveSFtuning(sfs = numpy.logspace(-2, 2, 1000)): # written when still new to python. Probably to matlab-y...
    # Not updated for sfMixAlt - 1/31/18
    # normPool details are fixed, ya?
    # plot model details - exc/suppressive components
    omega = sfs;

    # Compute suppressive SF tuning
    # The exponents of the filters used to approximately tile the spatial frequency domain
    n = numpy.array([.75, 1.5]);
    # The number of cells in the broad/narrow pool
    nUnits = numpy.array([12, 15]);
    # The gain of the linear filters in the broad/narrow pool
    gain = numpy.array([.57, .614]);

    normPool = {'n': n, 'nUnits': nUnits, 'gain': gain};
    # Get filter properties in spatial frequency domain
    gain = numpy.empty((len(normPool.get('n'))));
    for iB in range(len(normPool.get('n'))):
        prefSf_new = numpy.logspace(numpy.log10(.1), numpy.log10(30), normPool.get('nUnits')[iB]);
        if iB == 0:
            prefSf = prefSf_new;
        else:
            prefSf = [prefSf, prefSf_new];
        gain[iB]   = normPool.get('gain')[iB];

    for iB in range(len(normPool.get('n'))):
        sfRel = numpy.matlib.repmat(omega, len(prefSf[iB]), 1).transpose() / prefSf[iB]
        s     = numpy.power(numpy.matlib.repmat(omega, len(prefSf[iB]), 1).transpose(), normPool['n'][iB]) \
                    * numpy.exp(-normPool['n'][iB]/2 * numpy.square(sfRel));
        sMax  = numpy.power(prefSf[iB], normPool['n'][iB]) * numpy.exp(-normPool['n'][iB]/2);
        if iB == 0:
            selSf = gain[iB] * s / sMax;
        else:
            selSf = [selSf, gain[iB] * s/sMax];

    return numpy.hstack((selSf[0], selSf[1]));

def makeStimulus(stimFamily, conLevel, sf_c, template):

# returns [Or, Tf, Co, Ph, Sf, trial_used]

# 1/23/16 - This function is used to make arbitrary stimuli for use with
# the Robbe V1 model. Rather than fitting the model responses at the actual
# experimental stimuli, we instead can simulate from the model at any
# arbitrary spatial frequency in order to determine peak SF
# response/bandwidth/etc

# If argument 'template' is given, then orientation, phase, and tf_center will be
# taken from the template, which will be actual stimuli from that cell

    # Fixed parameters
    num_families = 5;
    num_gratings = 9;

    spreadVec = numpy.logspace(math.log10(.125), math.log10(1.25), num_families);
    octSeries  = numpy.linspace(1.5, -1.5, num_gratings);

    # set contrast and spatial frequency
    if conLevel == 1:
        total_contrast = 1;
    elif conLevel == 2:
        total_contrast = 1/3;
    elif conLevel>=0 and conLevel<1:
        total_contrast = conLevel;
    else:
        #warning('Contrast should be given as 1 [full] or 2 [low/one-third]; setting contrast to 1 (full)');
        total_contrast = 1; # default to that
        
    spread     = spreadVec[stimFamily-1];
    profTemp = norm.pdf(octSeries, 0, spread);
    profile    = profTemp/sum(profTemp);

    if stimFamily == 1: # do this for consistency with actual experiment - for stimFamily 1, only one grating is non-zero; round gives us this
        profile = numpy.round(profile);

    Sf = numpy.power(2, octSeries + numpy.log2(sf_c)); # final spatial frequency
    Co = numpy.dot(profile, total_contrast); # final contrast

    ## The others
    
    # get orientation - IN RADIANS
    trial = template.get('sfm').get('exp').get('trial');
    OriVal = mode(trial.get('ori')[0]).mode * numpy.pi/180; # pick arbitrary grating, mode for this is cell's pref Ori for experiment
    Or = numpy.matlib.repmat(OriVal, 1, num_gratings)[0]; # weird tuple [see below], just get the array we care about...
    
    if template.get('trial_used') is not None: #use specified trial
        trial_to_copy = template.get('trial_used');
    else: # get random trial for phase, TF
        # we'll draw from a random trial with the same stimulus family/contrast
        if conLevel!=1 or conLevel!=2: # basically, if we're doing a 'non-tradiational' contrast, then there isn't                  a corresponding blockID. So we'll just go with a high contrast blocKID; just used for Tf & Ph, anyway
            conLevel = 2; # just set it to 1...
        valid_blockIDs = numpy.arange((stimFamily-1)*(13*2)+1+(conLevel-1), ((stimFamily)*(13*2)-5)+(conLevel-1), 2)
                        # above from Robbe's plotSfMix
        num_blockIDs = len(valid_blockIDs);
        # for phase and TF
        valid_trials = trial.get('blockID') == valid_blockIDs[random.randint(0, num_blockIDs-1)] # pick a random block ID
        valid_trials = numpy.where(valid_trials)[0]; # 0 is to get array...weird "tuple" return type...
        trial_to_copy = valid_trials[random.randint(0, len(valid_trials)-1)]; # pick a random trial from within this

    trial_used = trial_to_copy;
    
    # grab Tf and Phase [IN RADIANS] from each grating for the given trial
    Tf = numpy.asarray([i[trial_to_copy] for i in trial.get('tf')]);
    Ph = numpy.asarray([i[trial_to_copy] * math.pi/180 for i in trial.get('ph')]);

    # now, sort by contrast (descending) with ties given to lower SF:
    inds_asc = numpy.argsort(Co); # this sorts ascending
    inds_des = inds_asc[::-1]; # reverse it
    Or = Or[inds_des];
    Tf = Tf[inds_des];
    Co = Co[inds_des];
    Ph = Ph[inds_des];
    Sf = Sf[inds_des];
    
    return {'Ori': Or, 'Tf' : Tf, 'Con': Co, 'Ph': Ph, 'Sf': Sf, 'trial_used': trial_used}

def getNormParams(params, normType):
  if normType == 1:
    if len(params) > 8:
      inhAsym = params[8];
    else:
      inhAsym = 0; 
    return inhAsym;
  elif normType == 2:
    gs_mean = params[8];
    gs_std  = params[9];
    return gs_mean, gs_std;
  elif normType == 3:
    # sigma calculation
    offset_sigma = params[8];  # c50 filter will range between [v_sigOffset, 1]
    stdLeft      = params[9];  # std of the gaussian to the left of the peak
    stdRight     = params[10]; # '' to the right '' 
    sfPeak       = params[11]; # where is the gaussian peak?
    return offset_sigma, stdLeft, stdRight, sfPeak;
  else:
    inhAsym = 0;
    return inhAsym;

def genNormWeights(cellStruct, nInhChan, gs_mean, gs_std, nTrials):
  np = numpy;
  # A: do the calculation here - more flexibility
  inhWeight = [];
  nFrames = 120;
  T = cellStruct['sfm'];
  nInhChan = T['mod']['normalization']['pref']['sf'];
        
  for iP in range(len(nInhChan)): # two channels: narrow and broad

    # if asym, put where '0' is
    curr_chan = len(T['mod']['normalization']['pref']['sf'][iP]);
    log_sfs = np.log(T['mod']['normalization']['pref']['sf'][iP]);
    new_weights = norm.pdf(log_sfs, gs_mean, gs_std);
    inhWeight = np.append(inhWeight, new_weights);
    #print('Weights: ' + str(new_weights));

  inhWeightT1 = np.reshape(inhWeight, (1, len(inhWeight)));
  inhWeightT2 = repmat(inhWeightT1, nTrials, 1);
  inhWeightT3 = np.reshape(inhWeightT2, (nTrials, len(inhWeight), 1));
  inhWeightMat  = np.tile(inhWeightT3, (1,1,nFrames));

  return inhWeightMat;

def setSigmaFilter(sfPref, stdLeft, stdRight, filtType = 1):
  '''
  For now, we are parameterizing the semisaturation contrast filter as a "fleixble" Gaussian
  That is, a gaussian parameterized with a mean, and a standard deviation to the left and right of that peak/mean
  We set the baseline of the filter to 0 and the overall amplitude to 1
  '''
  filter = dict();
  if filtType == 1:
    filter['type'] = 1; # flexible gaussian
    filter['params'] = [0, 1, sfPref, stdLeft, stdRight]; # 0 for baseline, 1 for respAmpAbvBaseline

  return filter;

def evalSigmaFilter(filter, scale, offset, evalSfs):
  '''
  filter is the type of filter to be evaluated (will be dictionary with necessary parameters)
  scale, offset are used to scale and offset the filter shape
  evalSfs - which sfs to evaluate at
  '''

  params = filter['params'];  
  if filter['type'] == 1: # flexibleGauss
    filterShape = numpy.array(flexible_Gauss(params, evalSfs, 0)); # 0 is baseline/minimum value of flexible_Gauss
  elif filter['type'] == 2:
    filterShape = deriv_gauss(params, evalSfs)[0]; # take the first output argument only

  evalC50 = scale*filterShape + offset - scale 
  # scale*filterShape will be between [scale, 0]; then, -scale makes it [0, -scale], where scale <0 ---> -scale>0
  # finally, +offset means evalC50 is [offset, -scale+offset], where -scale+offset will typically = 1
  return evalC50;

def setNormTypeArr(params, normTypeArr = []):
  '''
  Used to create the normTypeArr array which is called in model_responses by SFMGiveBof and SFMsimulate to set
  the parameters/values used to compute the normalization signal for the full model

  Requires the model parameters vector; optionally takes normTypeArr as input

  Returns the normTypeArr
  '''

  # constants
  c50_len = 12; # 12 parameters if we've optimized for the filter which sets c50 in a frequency-dependent way
  gauss_len = 10; # 10 parameters in the model if we've optimized for the gaussian which weights the normalization filters
  asym_len = 9; # 9 parameters in the model if we've used the old asymmetry calculation for norm weights

  inhAsym = 0; # set to 0 as default

  # now do the work
  if normTypeArr:
    norm_type = int(normTypeArr[0]); # typecast to int
    if norm_type == 3: # c50 style
      if len(params) == c50_len:
        filt_offset = params[8];
        std_l = params[9];
        std_r = params[10];
        filt_peak = params[11];
      else:
        if len(normTypeArr) > 1:
          filt_offset = normTypeArr[1];
        else: 
          filt_offset = random_in_range([0.05, 0.2])[0]; 
        if len(normTypeArr) > 2:
          std_l = normTypeArr[2];
        else:
          std_l = random_in_range([0.5, 5])[0]; 
        if len(normTypeArr) > 3:
          std_r = normTypeArr[3];
        else: 
          std_r = random_in_range([0.5, 5])[0]; 
        if len(normTypeArr) > 4:
          filt_peak = normTypeArr[4];
        else: 
          filt_peak = random_in_range([1, 6])[0]; 
      normTypeArr = [norm_type, filt_offset, std_l, std_r, filt_peak];

    elif norm_type == 2:
      if len(params) == gauss_len: # we've optimized for these parameters
        gs_mean = params[8];
        gs_std = params[9];
      else:
        if len(normTypeArr) > 1:
          gs_mean = normTypeArr[1];
        else:
          gs_mean = random_in_range([-1, 1])[0];
        if len(normTypeArr) > 2:
          gs_std = normTypeArr[2];
        else:
          gs_std = numpy.power(10, random_in_range([-2, 2])[0]); # i.e. 1e-2, 1e2
      normTypeArr = [norm_type, gs_mean, gs_std]; # save in case we drew mean/std randomly
    
    elif norm_type == 1:
      if len(params) == asym_len:
        inhAsym = params[8];
      else:
        inhAsym = 0;
      if len(normTypeArr) > 1: # then we've passed in inhAsym to override existing one, if there is one
        inhAsym = normTypeArr[1];
      normTypeArr = [norm_type, inhAsym]; # if neither "if" above is true, we've already set inhAsym to 0

  else:
    norm_type = 0; # i.e. just run old asymmetry computation
    if len(params) == asym_len:
      inhAsym = params[8];
    if len(normTypeArr) > 1: # then we've passed in inhAsym to override existing one, if there is one
      inhAsym = normTypeArr[1];
    normTypeArr = [norm_type, inhAsym];

  return normTypeArr;

def getConstraints(fitType):
        # 00 = preferred spatial frequency   (cycles per degree) || [>0.05]
        # 01 = derivative order in space || [>0.1]
        # 02 = normalization constant (log10 basis) || unconstrained
        # 03 = response exponent || >1
        # 04 = response scalar || >1e-3
        # 05 = early additive noise || [0, 1]; was [0.001, 1] - see commented out line below
        # 06 = late additive noise || >0.01
        # 07 = variance of response gain || >1e-3
        # if fitType == 2
        # 08 = mean of normalization weights gaussian || [>-2]
        # 09 = std of ... || >1e-3 or >5e-1
        # if fitType == 3
        # 08 = the offset of the c50 tuning curve which is bounded between [v_sigOffset, 1] || [0, 0.75]
        # 09 = standard deviation of the gaussian to the left of the peak || >0.1
        # 10 = "" to the right "" || >0.1
        # 11 = peak (i.e. sf location) of c50 tuning curve 

    zero = (0.05, None);
    one = (0.1, None);
    two = (None, None);
    three = (1, None);
    four = (1e-3, None);
    five = (0, 1); # why? if this is always positive, then we don't need to set awkward threshold (See ratio = in GiveBof)
    six = (0.01, None); # if always positive, then no hard thresholding to ensure rate (strictly) > 0
    seven = (1e-3, None);
    if fitType == 1:
      eight = (0, 0); # flat normalization (i.e. no tilt)
      return (zero,one,two,three,four,five,six,seven,eight);
    if fitType == 2:
      eight = (-2, None);
      nine = (5e-1, None);
      return (zero,one,two,three,four,five,six,seven,eight,nine);
    elif fitType == 3:
      eight = (0, 0.75);
      nine = (1e-1, None);
      ten = (1e-1, None);
      eleven = (0.05, None);
      return (zero,one,two,three,four,five,six,seven,eight,nine,ten,eleven);
    else: # mistake!
      return [];


