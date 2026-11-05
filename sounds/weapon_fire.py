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


# The 'saw' profile's knobs.
SAW_DETUNE=.004            # Each side's pitch offset (fraction); wider sounds bigger but blurrier.
SAW_WAH_START_RATE=2     # Wah pulses per second at the start of the shot.
SAW_WAH_END_RATE=0.1        # Wah pulses per second at the end.
SAW_WAH_CURVE=1.5          # Higher keeps the wah slow for longer, then rushes at the end.
SAW_WAH_LOW=450            # The wah's lowest cutoff, in Hz.
SAW_WAH_HIGH=3600          # The wah's highest cutoff, in Hz.
SAW_RESONANCE=.86          # How sharply the wah sings, from 0 to just under 1.
SAW_DRIVE=4                # Overdrive; higher is harsher.


def _saw(definition, rate):
    """A raw, overdriven stereo sawtooth: the zap dives in, then a resonant wah snarls over it."""
    duration=definition.sound_duration
    t=np.arange(round(rate*duration))/rate
    # The pitch dives from two octaves up to the base note, a laser's zap settling into a drone.
    dive=1+3*np.exp(-t/.03)
    # One saw per side, barely detuned for width, over a saw an octave below; few voices keep the edge clean, not hissy.
    channels=[]
    for side,d in enumerate((-SAW_DETUNE,SAW_DETUNE)):
        signal=np.zeros(len(t))
        for ratio,level in ((1,1),(.5,.7*definition.sound_body)):
            increment=definition.sound_pitch*ratio*(1+d)*dive/rate
            signal+=_polyblep_saw(np.cumsum(increment)+side*.25,increment)*level
        channels.append(signal)
    sub=definition.sound_body*.5*np.sin(math.tau*np.cumsum(definition.sound_pitch*.5*dive)/rate)
    # A wah: the resonant peak swings between its low and high cutoffs, starting wide open, its pulses quickening.
    wah_rate=SAW_WAH_START_RATE+(SAW_WAH_END_RATE-SAW_WAH_START_RATE)*(t/duration)**SAW_WAH_CURVE
    wah=.5+.5*np.cos(math.tau*np.cumsum(wah_rate)/rate)
    cutoff=SAW_WAH_LOW*(SAW_WAH_HIGH/SAW_WAH_LOW)**wah
    attack=1-np.exp(-t/.003)
    envelope=attack*np.exp(-t*1.6/duration)
    fade=np.minimum(1,(duration-t)/.03)
    out=[]
    for side in channels:
        filtered=_resonant_lowpass(side/1.7,cutoff,rate,SAW_RESONANCE)
        # Hard overdrive squares off the saw for a harsh, snarling edge.
        out.append(np.tanh((filtered+sub)*envelope*SAW_DRIVE)*.8*fade)
    return np.stack(out,axis=1)


PROFILES={'tone':_tone,'blast':_blast,'saw':_saw}


def samples(definition, rate):
    return PROFILES[definition.sound_profile](definition,rate)


if __name__ == '__main__':
    # Audition a weapon's sound: python -m sounds.weapon_fire [weapon_id], default railgun.
    import sys, time, pygame
    from weapons.catalog import CATALOG
    weapon=CATALOG[sys.argv[1] if len(sys.argv)>1 else 'railgun']
    pygame.mixer.init(44100,-16,2)
    pcm=(np.clip(samples(weapon,44100),-1,1)*32767).astype(np.int16)
    if pcm.ndim==1:
        pcm=np.repeat(pcm[:,None],2,axis=1)
    pygame.sndarray.make_sound(pcm).play()
    time.sleep(weapon.sound_duration+.1)
