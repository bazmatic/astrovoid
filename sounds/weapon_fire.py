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


PROFILES={'tone':_tone,'blast':_blast}


def samples(definition, rate):
    return PROFILES[definition.sound_profile](definition,rate)
