import math
import numpy
import os
from makeStimulus import makeStimulus 
from scipy.stats import norm, mode, lognorm, nbinom
from numpy.matlib import repmat
import time
import sys

import tensorflow as tf

import pdb

fft = numpy.fft
tf_pi = tf.constant(math.pi);

def ph_test(S, p):
    
    pdb.set_trace();
    
    z = S['sfm']['exp']['trial'];
    
    stimOr = numpy.empty((nGratings,));
    stimTf = numpy.empty((nGratings,));
    stimCo = numpy.empty((nGratings,));
    stimPh = numpy.empty((nGratings,));
    stimSf = numpy.empty((nGratings,));
               
    for iC in range(9):
        stimOr[iC] = z.get('ori')[iC][p] * math.pi/180; # in radians
        stimTf[iC] = z.get('tf')[iC][p];          # in cycles per second
        stimCo[iC] = z.get('con')[iC][p];         # in Michelson contrast
        stimPh[iC] = z.get('ph')[iC][p] * math.pi/180;  # in radians
        stimSf[iC] = z.get('sf')[iC][p];          # in cycles per degree
                
    return StimOr, stimTf, stimCo, stimPh, stimSf;

# orientation filter used in plotting (only, I think?)
def oriFilt(imSizeDeg, pixSizeDeg, prefSf, prefOri, dOrder, aRatio):
    
    # returns a spatial filter which is dth-order derivate of 2-D Gaussian


    # imSizeDeg  = image size in degrees
    # pixSizeDeg = pixel size in degrees
    # prefSf     = peak spatial frequency in cycles/deg
    # prefOri    = peak orientation in radians
    # dOrder     = derivative order (integer)
    # aRatio     = aspect ratio of the Gaussian 
    #
    # oriTuning = (cos(oris-prefOri).^2 .* exp((aRatio^2-1)*cos(oris-prefOri).^2)).^(dOrder/2);
    # sfTuning  = sfs.^dOrder .* exp(- sfs.^2 ./ (2*sx^2));


    pixPerDeg = 1/pixSizeDeg;
    npts2     = round(0.5*imSizeDeg*pixPerDeg);
    psfPixels = 2*npts2*prefSf/pixPerDeg;                                      # convert peak sf from cycles/degree to pixels
    sx        = psfPixels/max(math.sqrt(dOrder), 0.01);                             # MAGIC
    sy        = sx/aRatio;
    
    [X, Y] = numpy.mgrid[-npts2:npts2, -npts2:npts2];
    rX    = numpy.cos(prefOri) * X + numpy.sin(prefOri) * Y;
    rY    = -numpy.sin(prefOri) * X + numpy.cos(prefOri) * Y;

    ffilt = numpy.exp(-(pow(rX, 2) / (2 * pow(sx, 2)) + pow(rY, 2) / (2 * pow(sy, 2)))) * pow(-1j*rX, dOrder);
    
    filt = fft.fftshift(fft.ifft2(fft.ifftshift(ffilt)));
    return filt.real;

# SFMSimpleResp - Used in Robbe V1 model - excitatory, linear filter response
def SFMSimpleResp(ph_stimOr, ph_stimTf, ph_stimCo, ph_stimSf, ph_stimPh, mod_params):   
    # SFMSimpleResp       Computes response of simple cell for sfmix experiment

    # SFMSimpleResp(varargin) returns a simple cell response for the
    # mixture stimuli used in sfMix. The cell's receptive field is the n-th
    # derivative of a 2-D Gaussian that need not be circularly symmetric.

    # 00 = preferred spatial frequency   (cycles per degree)
    # 01 = derivative order in space
    # 02 = normalization constant        (log10 basis)
    # 03 = response exponent
    # 04 = response scalar
    # 05 = early additive noise
    # 06 = late additive noise
    # 07 = variance of response gain    

    # Get preferred stimulus values
    prefSf = mod_params[0];                           # in cycles per degree
    #nan_trials = tf.is_nan(ph_stimTf[0]);
    #masked_stimTf = tf.boolean_mask(ph_stimTf[0], ~nan_trials);
    #prefTf = tf.round(tf.reduce_mean(masked_stimTf));     # in cycles per second
    prefTf = tf.round(tf.reduce_mean(ph_stimTf[0]));
    
    # Get directional selectivity - removed 7/18/17

    # Get derivative order in space and time
    dOrdSp = mod_params[1];
    dOrdTi = 0.25; # fixed....

    # Get aspect ratio in space - removed 7/18/17

    # Get spatial coordinates
    xCo = 0;                                                              # in visual degrees, centered on stimulus center
    yCo = 0;                                                              # in visual degrees, centered on stimulus center

    # Store some results in M
    M = dict();
    pref = dict();
    dord = dict();
    pref.setdefault('sf', prefSf);
    pref.setdefault('tf', prefTf);
    pref.setdefault('xCo', xCo);
    pref.setdefault('yCo', yCo);
    dord.setdefault('sp', dOrdSp);
    dord.setdefault('ti', dOrdTi);
    
    M.setdefault('pref', pref);
    M.setdefault('dord', dord);
    
    # Pre-allocate memory
    nDims         = 3; # x, y, t
    nGratings     = 9;
    nFrames       = 120;
    
    to_rad = tf_pi/180;
                     
    # these will be nGratings x nTrials
    stimOr = ph_stimOr * to_rad;  # in radians
    stimTf = ph_stimTf;                       # in cycles per second
    stimCo = ph_stimCo;                       # in Michelson contrast
    stimPh = ph_stimPh * to_rad;  # in radians
    stimSf = ph_stimSf;                       # in cycles per degree
        
    # Compute simple cell response for all trials

    # I. Orientation, spatial frequency and temporal frequency
                
    # Compute spatial frequency tuning - will be 9 x nTrials
    sfRel = tf.divide(stimSf, prefSf);
    s     = tf.multiply(tf.pow(stimSf, dOrdSp), tf.exp(-dOrdSp/2 * tf.square(sfRel)));
    sMax  = tf.multiply(tf.pow(prefSf, dOrdSp), tf.exp(-dOrdSp/2));
    sNl   = tf.divide(s, sMax);
    selSf = sNl;

    # Compute temporal frequency tuning - will be 9 x nTrials
    tfRel = tf.divide(stimTf, prefTf);
    t     = tf.multiply(tf.pow(stimTf, dOrdTi), tf.exp(-dOrdTi/2 * tf.square(tfRel)));
    tMax  = tf.multiply(tf.pow(prefTf, dOrdTi), tf.exp(-dOrdTi/2));
    tNl   = tf.divide(t, tMax);
    selTf = tNl;

    # Compute orientation tuning 
    # removed ori selectivity 7/18/17 - just set to 1

    # ASSUMPTION: dOrdSp will never be zero...
    #  if dOrdSp == 0:
    #    selOr = tf.ones(selOr.shape);

    # II. Phase, space and time - will be 9 x nTrials
    omegaX = tf.multiply(stimSf, tf.cos(stimOr)); # the stimulus in frequency space
    omegaY = tf.multiply(stimSf, tf.sin(stimOr));
    omegaT = stimTf;

    # Play with dimensions! Make each 1 x 9 x nTrials
    omsX = tf.expand_dims(omegaX, axis=0);
    omsY = tf.expand_dims(omegaY, axis=0);
    omsT = tf.expand_dims(omegaT, axis=0);
    
    # Make 3 x 9 x nTrials
    omegaAll = tf.concat((omsX, omsY, omsT), axis=0);
    # Should be nTrials x 9 x 3
    omgAll = tf.transpose(omegaAll, perm=[2, 1, 0]); # put 2nd dim in 0th, 1st stays, 0th in 2nd   
    omAll = tf.expand_dims(omgAll, axis=-1); # should be nTrials x 9 x 3 x 1
    
    P_x = 2*tf_pi*xCo*tf.ones((nFrames, omAll.shape[0], nGratings));  
    # P is the matrix that contains the relative location of each filter in space-time (expressed in radians)
    P_y = 2*tf_pi*yCo*tf.ones((nFrames, omAll.shape[0], nGratings));

    # Make frameList 120 x 1 x 1
    frameList = tf.range(nFrames, dtype=tf.float32)/nFrames;
    frameExp = tf.expand_dims(frameList, axis=-1);
    frameExpand = tf.expand_dims(frameExp, axis=-1);
    
    phaseSpace = tf.divide(stimPh, (2*tf_pi*stimTf));
    phSp = tf.expand_dims(phaseSpace, axis=0);
    
    stimPos = frameExpand + phSp;    
    # ABOVE: 120 frames + appropriate phase-offset for each trial x grating combination
    # Therefore...size is 120 x 9 x nTrials
    Pt  = 2*tf_pi*stimPos; # P_t describes relative location of the filters in time.
    # Now...reshape to have same size as P_x, P_y
    P_t = tf.transpose(Pt, perm = [0, 2, 1]);

    Ps_temp = tf.stack((P_x, P_y, P_t), axis=-1); # now nTrials x nFrames x stimComp x 3
    Ps = tf.transpose(Ps_temp, perm=[1,2,0,3]); # want nTrials x stimComp x nFrames x 3
    
    # (nTrials x stimComp x nFrames x 3) * (nTrials x stimComp x 3 x 1) gives you
    # nTrials x stimComp x nFrames x 1 as result (intermediate)
    intrmd = tf.matmul(Ps, omAll); # why save intermediate? must convert in next step - cleaner    
    intermediate = tf.squeeze(intrmd, axis=-1); # now nTrials x stimComp x nFrames
    rCmplx_part = tf.exp(tf.multiply(1j, tf.cast(intermediate, tf.complex128)));
    rComplex_part = tf.transpose(rCmplx_part, perm=[0, 2, 1]);
        
    # selSi (& interAgain) will be stimComp x nTrials
    selSi =tf.multiply(selSf, selTf); # filter sensitivity for the sinusoid in the frequency domain
    intAgn = tf.multiply(selSi, stimCo);
    
    interAgn = tf.expand_dims(intAgn, axis=-1);
    interAgain = tf.transpose(interAgn, perm=[1,0,2]); # to make nTrials x stimComp x 1
    # important multiplication! (nTrials x nFrames x stimComp) * (nTrials x stimComp x 1) gives
    # nTrials x nFrames x 1
    rCmplx = tf.matmul(rComplex_part, tf.cast(interAgain, tf.complex128));
    rComplex = tf.squeeze(rCmplx, axis=-1);
    
    linR1 = tf.real(rComplex);
    linR2 = -1*tf.real(rComplex);
    linR3 = tf.imag(rComplex);
    linR4 = -1*tf.imag(rComplex);
                    
    # superposition and half-wave rectification,...
    # here, we return a nTrials x nFrames matrix - it will be averaged across frames in SFMGiveBof
    compZero = tf.zeros(linR1.shape, dtype=tf.float64);
    respSimple1 = tf.maximum(compZero, linR1); 
    respSimple2 = tf.maximum(compZero, linR2);
    respSimple3 = tf.maximum(compZero, linR3);
    respSimple4 = tf.maximum(compZero, linR4);

    # well, we just take simple response for now, unless we are modelling complex cells
    return respSimple1;
    #return {'AllAhDem': rComplex, 'selectivity': selSi, 'selWithCon': interAgain, 'expPart': rComplex_part, \
        #'P': Ps, 'omega': omegaAll};
        
def SFMGiveBof(ph_stimOr, ph_stimTf, ph_stimCo, ph_stimSf, ph_stimPh, ph_spikeCount, ph_stimDur, \
               ph_normResp, ph_normCenteredSf, v_prefSf, v_dOrdSp, v_normConst, \
                      v_respExp, v_respScalar, v_noiseEarly, v_noiseLate, v_varGain):
    
    # Computes the negative log likelihood for the LN-LN model

    params = applyConstraints(v_prefSf, v_dOrdSp, v_normConst, \
                      v_respExp, v_respScalar, v_noiseEarly, v_noiseLate, v_varGain);
    
    # 00 = preferred spatial frequency   (cycles per degree)
    # 01 = derivative order in space
    # 02 = normalization constant        (log10 basis)
    # 03 = response exponent
    # 04 = response scalar
    # 05 = early additive noise
    # 06 = late additive noise
    # 07 = variance of response gain    

    nFrames = 120; # hashtag always
    
    ### Get parameter values
    # Excitatory channel
    prefSf = params[0];
    dordSp = params[1]; dOrdTi = tf.constant(0.25); 
    # deriv order in temporal domain = 0.25 ensures broad tuning for temporal frequency

    # Inhibitory channel
    # no extra inh params in this formulation - 7/7/17

     # Other (nonlinear) model components
    sigma    = tf.pow(tf.constant(10, dtype=tf.float32), params[2]); # normalization constant
    # respExp  = 2; # response exponent
    respExp  = params[3]; # response exponent
    scale    = params[4]; # response scalar

    # Noise parameters
    noiseEarly = params[5];   # early additive noise
    noiseLate  = params[6];  # late additive noise
    varGain    = params[7];  # multiplicative noise

    ### Evaluate prior on response exponent -- corresponds loosely to the measurements in Priebe et al. (2004)
    #priorExp = lognorm.pdf(respExp, 0.3, 0, numpy.exp(1.15));
    NLLExp = 0; # should use priorExp and NLLExp lines commented out below, but not for now
    #NLLExp   = tf.constant(-numpy.log(priorExp) / ph_stimOr.shape[1]);
    # why divide by number of trials? because we take mean of NLLs, so this way it's fair to add them

    ### Compute weights for suppressive signals - will be 1-vector of length nFilt [27]
    inhWeight = 1 + tf.multiply(tf.constant(0, dtype=tf.float32), ph_normCenteredSf);

    # now we must exand inhWeight to match rank of ph_normResp - no need to match dimensions, since * will broadcast
    inhWeight = tf.expand_dims(inhWeight, axis=0);
    inhWeightMat = tf.expand_dims(inhWeight, axis=-1);

    # Get simple cell response for excitatory channel
    E = SFMSimpleResp(ph_stimOr, ph_stimTf, ph_stimCo, ph_stimSf, ph_stimPh, params); 

    # Extract simple cell response (half-rectified linear filtering)
    Lexc = E; #E['simpleResp'];

    # Get inhibitory response (pooled responses of complex cells tuned to wide range of spatial frequencies, square root to         bring everything in linear contrast scale again)
    temp = ph_normResp * inhWeightMat;
    temp = tf.reduce_sum(temp, axis=1); # sum over filters to make nTrials x nFrames
    Linh = tf.sqrt(temp);

    # Compute full model response (the normalization signal is the same as the subtractive suppressive signal)
    uno = tf.add(noiseEarly, tf.cast(Lexc, dtype=tf.float32));
    numerator     = uno;
    # taking the sqrt of the denominator (which is sum of squares) to bring in line with Carandini, Heeger, Movshon, '97
    denominator   = tf.sqrt(tf.square(sigma) + tf.square(Linh)); # squaring Linh - edit 7/17
    # ratio will be nTrials x nTrials
    ratio         = tf.pow(tf.maximum(tf.constant(0, dtype=tf.float32), tf.divide(numerator,denominator)), respExp);
    meanRate      = tf.reduce_mean(ratio, axis=1);
    respModel     = noiseLate + (scale * meanRate);

    # Get predicted spike count distributions
    mu  = tf.maximum(tf.constant(.01, dtype=tf.float32), tf.multiply(ph_stimDur, respModel)); 
    # The predicted mean spike count; respModel[iR]
    var = tf.add(mu, varGain*tf.square(mu)); # The corresponding variance of the spike count
    r   = tf.divide(tf.square(mu), tf.subtract(var, mu)); # The parameters r and p of the negative binomial distribution
    p   = tf.divide(r, tf.add(r, mu));

    log_lh = negBinom(ph_spikeCount, r, p);
     
    NLL = tf.reduce_mean(-1*log_lh);
    
    return NLL;

def applyConstraints(v_prefSf, v_dOrdSp, v_normConst, \
                      v_respExp, v_respScalar, v_noiseEarly, v_noiseLate, v_varGain):
        
        # 00 = preferred spatial frequency   (cycles per degree) || [>0.05]
        # 01 = derivative order in space || [>0.1]
        # 02 = normalization constant (log10 basis) || unconstrained
        # 03 = response exponent || >1
        # 04 = response scalar || >1e-3
        # 05 = early additive noise || [0,1]
        # 06 = late additive noise || >0
        # 07 = variance of response gain || >1e-3     

    zero = tf.add(tf.nn.softplus(v_prefSf), 0.05);
    one = tf.add(tf.nn.softplus(v_dOrdSp), 0.1);
    two = v_normConst;
    three = tf.constant(2, tf.float32);
    #three = tf.add(tf.nn.softplus(v_respExp), 1);
    four = tf.add(tf.nn.softplus(v_respScalar), 1e-3);
    five = tf.sigmoid(v_noiseEarly);
    six = tf.nn.softplus(v_noiseLate);
    seven = tf.add(tf.nn.softplus(v_varGain), 1e-3);
    return [zero,one,two,three,four,five,six,seven];

def negBinom(x, r, p):
    # We assume that r & p are tf placeholders/variables; x is a constant
    # Negative binomial is:
        # gamma(x+r) * (1-p)^x * p^r / (gamma(x+1) * gamma(r))
    
    # Here we return the log negBinomial:
    
    x = tf.to_float(x); # convert to float32just like r, p
    naGam = tf.multiply(x, tf.log(1-p)) + tf.multiply(r, tf.log(p));
    haanGam = tf.lgamma(tf.add(x, r)) - tf.lgamma(tf.add(x, 1)) - tf.lgamma(r);
    
    return tf.add(naGam, haanGam);
    
def setModel(cellNum, fitIter, lr, subset_frac = 0, initFromCurr = 1):
    # Given just a cell number, will fit the Robbe V1 model to the data
    # LR is learning rate
 
    ########
    # Load cell
    ########
    #loc_data = '/e/3.2/p1/plevy/SF_diversity/sfDiv-OriModel/sfDiv-python/Analysis/Structures/'; # CNS machine
    #loc_data = '/Users/paulgerald/work/sfDiversity/sfDiv-OriModel/sfDiv-python/Analysis/Structures/'; # personal machine
    loc_data = '/home/pl1465/SF_diversity/Analysis/Structures/'; # Prince cluster 

    fitListName = 'fitListCHMe2.npy';

    fitList = numpy.load(loc_data + fitListName); # no .item() needed...
    dataList = numpy.load(loc_data + 'dataList.npy').item();
    dataNames = dataList['unitName'];

    S = numpy.load(loc_data + dataNames[cellNum-1] + '_sfm.npy').item(); # why -1? 0 indexing...
    trial_inf = S['sfm']['exp']['trial'];
    prefOrEst = mode(trial_inf['ori'][1]).mode;
    trialsToCheck = trial_inf['con'][0] == 0.01;
    prefSfEst = mode(trial_inf['sf'][0][trialsToCheck==True]).mode;

    ########
    # Set up model parameters - i.e. trainable variables!
    ########
    
    # 00 = preferred spatial frequency   (cycles per degree)
    # 01 = derivative order in space
    # 02 = normalization constant        (log10 basis)
    # 03 = response exponent
    # 04 = response scalar
    # 05 = early additive noise
    # 06 = late additive noise
    # 07 = variance of response gain
    
    curr_params = fitList[cellNum-1]['params']; # load parameters from the fitList! this is what actually gets updated...
     
    pref_sf = float(prefSfEst) if initFromCurr==0 else curr_params[0];
    dOrdSp = numpy.random.uniform(1, 3) if initFromCurr==0 else curr_params[1];
    normConst = numpy.random.uniform(-1, 0) if initFromCurr==0 else curr_params[2];
    respExp = numpy.random.uniform(1, 3) if initFromCurr==0 else curr_params[3];
    respScal = numpy.random.uniform(10, 1000) if initFromCurr==0 else curr_params[4];
    noiseEarly = numpy.random.uniform(0.001, 0.1) if initFromCurr==0 else curr_params[5];
    noiseLate = numpy.random.uniform(0, 1) if initFromCurr==0 else curr_params[6];
    varGain = numpy.random.uniform(0, 1) if initFromCurr==0 else curr_params[7];
    
    v_prefSf = tf.Variable(pref_sf, dtype=tf.float32);
    v_dOrdSp = tf.Variable(dOrdSp, dtype=tf.float32);
    v_normConst = tf.Variable(normConst, dtype=tf.float32);
    v_respExp = tf.Variable(respExp, dtype=tf.float32);
    v_respScalar = tf.Variable(respScal, dtype=tf.float32);
    v_noiseEarly = tf.Variable(noiseEarly, dtype=tf.float32);
    v_noiseLate = tf.Variable(noiseLate, dtype=tf.float32);
    v_varGain = tf.Variable(varGain, dtype=tf.float32);
 
    #########
    # Now get all the data we need for tf_placeholders 
    #########    
    # stimulus information
    
    # vstack to turn into array (not array of arrays!)
    stimOr = numpy.vstack(trial_inf['ori']);
    stimTf = numpy.vstack(trial_inf['tf']);
    stimCo = numpy.vstack(trial_inf['con']);
    stimSf = numpy.vstack(trial_inf['sf']);
    stimPh = numpy.vstack(trial_inf['ph']);
    
    #purge of NaNs...
    mask = numpy.isnan(numpy.sum(stimOr, 0)); # sum over all stim components...if there are any nans in that trial, we know
    # and get rid of orientation tuning curve trials
    oriBlockIDs = numpy.hstack((numpy.arange(131, 155+1, 2), numpy.arange(132, 136+1, 2))); # +1 to include endpoint like Matlab

    oriInds = numpy.empty((0,));
    for iB in oriBlockIDs:
        indCond = numpy.where(trial_inf['blockID'] == iB);
        if len(indCond[0]) > 0:
            oriInds = numpy.append(oriInds, indCond);

    # get rid of CRF trials, too? Not yet...
    # conBlockIDs = numpy.arange(138, 156+1, 2);
    #rateCo = numpy.empty((0,));
    # for iB in conBlockIDs:
        # indCond = numpy.where(expStructure['blockID'] == iB);
        # if len(indCond[0]) > 0:
            # rateCo = numpy.append(rateCo, numpy.mean(modResp[indCond]));

    mask[oriInds.astype(numpy.int64)] = True; # as in, don't include those trials either!

    #pdb.set_trace();

    fixedOr = stimOr[:,~mask];
    fixedTf = stimTf[:,~mask];
    fixedCo = stimCo[:,~mask];
    fixedSf = stimSf[:,~mask];
    fixedPh = stimPh[:,~mask];
    
    # cell responses
    spikes = trial_inf['spikeCount'][~mask];
    stim_dur = trial_inf['duration'][~mask];
        
    #########
    # Now set up our normalization pool information (also placeholder)
    #########
    # Get the normalization response (nTrials x nFilters [27] x nFrames [120])
    normResp = S['sfm']['mod']['normalization']['normResp'][~mask,:,:];
    
    # Put all of the filter prefSf into one vector (should be length 12+15=27)
    muCenterPref = [];
    normPrefSf = S['sfm']['mod']['normalization']['pref']['sf'];
    for iP in range(len(normPrefSf)):
        muCenterPref = numpy.append(muCenterPref, numpy.log(normPrefSf[iP]) - numpy.mean(numpy.log(normPrefSf[iP])));
    
    normCentSf = muCenterPref;
    
    #########
    # Set up the network!
    #########
    subsetShape = [fixedTf.shape[0], round(fixedTf.shape[-1]*subset_frac)];
    
    ph_stimOr = tf.placeholder(tf.float32);
    if subset_frac > 0:
      ph_stimTf = tf.placeholder(tf.float32, shape=subsetShape);
    else:
      ph_stimTf = tf.placeholder(tf.float32, shape=fixedTf.shape);
    ph_stimCo = tf.placeholder(tf.float32);
    ph_stimSf = tf.placeholder(tf.float32);
    ph_stimPh = tf.placeholder(tf.float32);
    
    ph_spikeCount = tf.placeholder(tf.float32);
    ph_stimDur = tf.placeholder(tf.float32);
        
    ph_normResp = tf.placeholder(tf.float32);
    ph_normCentSf = tf.placeholder(tf.float32);

    print('Setting network');
     
    # Set up model here - we return the NLL
    okok = SFMGiveBof(ph_stimOr, ph_stimTf, ph_stimCo, ph_stimSf, ph_stimPh, ph_spikeCount, ph_stimDur, \
              ph_normResp, ph_normCentSf, v_prefSf, v_dOrdSp, v_normConst, \
                      v_respExp, v_respScalar, v_noiseEarly, v_noiseLate, v_varGain);

    if subset_frac > 0:  
      ph_stimTfFull = tf.placeholder(tf.float32, shape=fixedTf.shape);
      full = SFMGiveBof(ph_stimOr, ph_stimTfFull, ph_stimCo, ph_stimSf, ph_stimPh, ph_spikeCount, ph_stimDur, \
              ph_normResp, ph_normCentSf, v_prefSf, v_dOrdSp, v_normConst, \
                      v_respExp, v_respScalar, v_noiseEarly, v_noiseLate, v_varGain);
    
    
    print('Setting optimizer');
    optimizer = tf.train.AdamOptimizer(learning_rate=lr).minimize(okok);

    m = tf.Session();
    init = tf.global_variables_initializer();
    m.run(init);
    
    currNLL = fitList[cellNum-1]['NLL'];

    for i in range(fitIter):
        # resample data...
        if subset_frac > 0:
          trialsToPick = numpy.random.randint(0, fixedOr.shape[-1], subsetShape[-1]);
          subsetOr = fixedOr[:,trialsToPick];
          subsetTf = fixedTf[:,trialsToPick];
          subsetCo = fixedCo[:,trialsToPick];
          subsetSf = fixedSf[:,trialsToPick];
          subsetPh = fixedPh[:,trialsToPick];
          subsetSpikes = spikes[trialsToPick];
          subsetDur = stim_dur[trialsToPick];
          subsetNormResp = normResp[trialsToPick,:,:];

          opt, loss = m.run([optimizer, okok], feed_dict={ph_stimOr: subsetOr, ph_stimTf: subsetTf, ph_stimCo: subsetCo, \
                          ph_stimSf: subsetSf, ph_stimPh: subsetPh, ph_spikeCount: subsetSpikes, ph_stimDur: subsetDur, \
                          ph_normResp: subsetNormResp, ph_normCentSf: normCentSf});

          print('itreation ' + str(i) + '...NLL is:' + str(loss));
        
          if (i/500.0) == round(i/500.0):
            NLL = m.run(full, feed_dict={ph_stimOr: fixedOr, ph_stimTfFull: fixedTf, ph_stimCo: fixedCo, \
                        ph_stimSf: fixedSf, ph_stimPh: fixedPh, ph_spikeCount: spikes, \
                        ph_stimDur: stim_dur, ph_normResp: normResp, ph_normCentSf: normCentSf});

        else:
	  opt = \
                m.run(optimizer, feed_dict={ph_stimOr: fixedOr, ph_stimTf: fixedTf, ph_stimCo: fixedCo, \
                            ph_stimSf: fixedSf, ph_stimPh: fixedPh, ph_spikeCount: spikes, \
                            ph_stimDur: stim_dur, ph_normResp: normResp, ph_normCentSf: normCentSf});

        
          if (i/500.0) == round(i/500.0):
            NLL = m.run(okok, feed_dict={ph_stimOr: fixedOr, ph_stimTf: fixedTf, ph_stimCo: fixedCo, \
                        ph_stimSf: fixedSf, ph_stimPh: fixedPh, ph_spikeCount: spikes, \
                        ph_stimDur: stim_dur, ph_normResp: normResp, ph_normCentSf: normCentSf});

        if (i/500.0) == round(i/500.0): # save every once in a while!!!
          
          print('iteration ' + str(i) + '...NLL is ' + str(NLL) + ' and params are ' + str(curr_params));
          
          if NLL < currNLL or numpy.any(numpy.isnan(curr_params)): # if the saved params are NaN, overwrite them

       	    real_params = m.run(applyConstraints(v_prefSf, v_dOrdSp, v_normConst, \
                                v_respExp, v_respScalar, v_noiseEarly, v_noiseLate, v_varGain));

            if numpy.any(numpy.isnan(real_params)): # don't save a fit with NaN!
              print('.nanParam.');
              continue;

            print('.update.');
            print('.params.'); print(real_params);
            print('.NLL|fullData.'); print(NLL);
            currNLL = NLL;
            currParams = real_params;
	    # reload fitlist in case changes have been made with the file elsewhere!
            fitList = numpy.load(loc_data + fitListName); # no .item() needed...
            fitList[cellNum-1]['NLL'] = NLL;
            fitList[cellNum-1]['params'] = real_params;
            numpy.save(loc_data + fitListName, fitList);   

    # Now the fitting is done    
    # Now get "true" model parameters and NLL
    if subset_frac > 0:
      NLL = m.run(full, feed_dict={ph_stimOr: fixedOr, ph_stimTfFull: fixedTf, ph_stimCo: fixedCo, \
                            ph_stimSf: fixedSf, ph_stimPh: fixedPh, ph_spikeCount: spikes, \
                            ph_stimDur: stim_dur, ph_normResp: normResp, ph_normCentSf: normCentSf});
    else:
      NLL = m.run(okok, feed_dict={ph_stimOr: fixedOr, ph_stimTf: fixedTf, ph_stimCo: fixedCo, \
                            ph_stimSf: fixedSf, ph_stimPh: fixedPh, ph_spikeCount: spikes, \
                            ph_stimDur: stim_dur, ph_normResp: normResp, ph_normCentSf: normCentSf});


    x = m.run(applyConstraints(v_prefSf, v_dOrdSp, v_normConst, \
                v_respExp, v_respScalar, v_noiseEarly, v_noiseLate, v_varGain));

    # Put those into fitList and save...ONLY if better than before
    if NLL < currNLL:
      # reload (as above) to avoid overwriting changes made with the file elsewhere
      fitList = numpy.load(loc_data + fitListName); # no .item() needed...
      fitList[cellNum-1]['NLL'] = NLL;
      fitList[cellNum-1]['params'] = x;

      numpy.save(loc_data + fitListName, fitList);

    print('Final parameters are ' + str(fitList[cellNum-1]['params']));
    
    return NLL, x;


if __name__ == '__main__':

    if len(sys.argv) < 4:
      print('uhoh...you need three arguments here'); # and one is the script itself...
      print('First should be cell number, second is number of fit iterations/updates, third is fraction of data to be used in subsample...currently ignored, anyway');
      exit();

    print('Running cell ' + sys.argv[1] + ' for ' + sys.argv[2] + ' iterations with learning rate ' + sys.argv[3]);

    if len(sys.argv) > 4: # subsample data for each iteration
      print('Additionally, each iteration will have ' + sys.argv[4] + ' of the data (subsample fraction)');
      setModel(int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5]));
    else: # all trials in each iteration
      setModel(int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3]));
