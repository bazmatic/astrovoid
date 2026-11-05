"""Weapon firing synthesis. Local noise generators never alter gameplay randomness."""
import math
import numpy as np


def _tone(definition, rate):
    duration=definition.sound_duration
    t=np.arange(round(rate*duration))/rate
    phase=math.tau*definition.sound_pitch*(t-.3*t*t/duration)
    waveform=np.sin(phase)+definition.sound_body*np.sin(phase*.5)
    return waveform*np.exp(-t*6/duration)*(9000/32767)


def _blast(definition, rate):
    t=np.arange(round(rate*definition.sound_duration))/rate
    noise=np.random.default_rng(1701).standard_normal(len(t))
    # A sharp broadband crack, followed by the falling pressure wave of a heavy report.
    crack=np.diff(noise,prepend=noise[0])*.24*np.exp(-t/.012)
    phase=math.tau*(52*t+98*.055*(1-np.exp(-t/.055)))
    attack=1-np.exp(-t/.001)
    boom=.74*np.sin(phase)*attack*np.exp(-t/.12)
    sub=.27*np.sin(math.tau*48*t)*attack*np.exp(-t/.15)
    width=max(1,round(rate/.9e3))
    rumble=np.convolve(noise,np.ones(width)/width,mode='same')
    tail=rumble*.8*attack*np.exp(-t/.14)
    clack=.16*np.sin(math.tau*230*t)*np.exp(-t/.025)
    signal=np.tanh((crack+boom+sub+tail+clack)*1.5)*.88
    # Clean ends prevent digital clicks while retaining the percussive attack.
    fade=np.minimum(1,t/.0005)*np.minimum(1,(definition.sound_duration-t)/.012)
    return signal*fade


def _polyblep_saw(phase, increment):
    """A sawtooth from -1 to 1 with its jump smoothed (polyBLEP), so the high harmonics stay bright without aliasing."""
    frac=phase%1
    saw=2*frac-1
    dt=np.maximum(increment,1e-9)
    after=frac<dt
    x=frac[after]/dt[after]
    saw[after]-=x+x-x*x-1
    before=frac>1-dt
    x=(frac[before]-1)/dt[before]
    saw[before]-=x*x+x+x+1
    return saw


def _resonant_lowpass(signal, cutoff, rate, resonance):
    """A state-variable low-pass whose cutoff moves sample by sample; the resonance sings at the cutoff."""
    out=np.empty_like(signal)
    low=band=0.0
    damping=2*(1-resonance)
    tune=2*np.sin(math.pi*np.minimum(cutoff,rate/6)/rate)
    for i,x in enumerate(signal):
        low+=tune[i]*band
        band+=tune[i]*(x-low-damping*band)
        out[i]=low
    return out


def _saw(definition, rate):
    """A huge stereo supersaw power chord: the zap dives in, a resonant filter roars open and slowly closes."""
    duration=definition.sound_duration
    t=np.arange(round(rate*duration))/rate
    # The pitch dives from two octaves up to the base note, a laser's zap settling into a drone.
    dive=1+3*np.exp(-t/.03)
    # Seven voices spread a few percent apart and across the stereo field, on the root, fifth and octave below.
    detunes=np.linspace(-.024,.024,7)
    pans=np.linspace(-1,1,7)
    left=np.zeros(len(t)); right=np.zeros(len(t))
    for ratio,level in ((1,1),(1.5,.55),(.5,.8*definition.sound_body)):
        for i,(d,pan) in enumerate(zip(detunes,pans)):
            pitch=definition.sound_pitch*ratio*(1+d)*dive
            increment=pitch/rate
            voice=_polyblep_saw(np.cumsum(increment)+i*.137+ratio*.31,increment)*level
            left+=voice*(1-pan)/2; right+=voice*(1+pan)/2
    sub=definition.sound_body*.6*np.sin(math.tau*np.cumsum(definition.sound_pitch*.5*dive)/rate)
    # The filter opens to a bright roar in the first 40 ms, then closes slowly with a ringing peak.
    cutoff=700+9000*np.exp(-t/.09)*(1-np.exp(-t/.012))+1200*np.exp(-t/.5)
    attack=1-np.exp(-t/.003)
    envelope=attack*np.exp(-t*2.2/duration)
    fade=np.minimum(1,(duration-t)/.03)
    channels=[]
    for side in (left,right):
        filtered=_resonant_lowpass(side/7,cutoff,rate,.82)
        channels.append(np.tanh((filtered*1.4+sub)*envelope*2.6)*.85*fade)
    return np.stack(channels,axis=1)


PROFILES={'tone':_tone,'blast':_blast,'saw':_saw}


def samples(definition, rate):
    return PROFILES[definition.sound_profile](definition,rate)
