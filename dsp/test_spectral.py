"""Exercise the shipped Windows x64 binary through the same effect ABI as APO."""
import ctypes as ct
from pathlib import Path
import unittest

import numpy as np

N, HOP = 4096, 1024
FloatPtr = ct.POINTER(ct.c_float)
Dispatch = ct.CFUNCTYPE(ct.c_ssize_t, ct.c_void_p, ct.c_int, ct.c_int,
                        ct.c_ssize_t, ct.c_void_p, ct.c_float)
Set = ct.CFUNCTYPE(None, ct.c_void_p, ct.c_int, ct.c_float)
Process = ct.CFUNCTYPE(None, ct.c_void_p, ct.POINTER(FloatPtr), ct.POINTER(FloatPtr), ct.c_int)


class Effect(ct.Structure):
    _fields_ = [
        ("magic", ct.c_int), ("dispatch", Dispatch), ("old_process", ct.c_void_p),
        ("set", Set), ("get", ct.c_void_p), ("counts", ct.c_int * 5),
        ("reserved", ct.c_void_p * 2), ("delay", ct.c_int), ("qualities", ct.c_int * 2),
        ("ratio", ct.c_float), ("object", ct.c_void_p), ("user", ct.c_void_p),
        ("id", ct.c_int), ("version", ct.c_int), ("process", Process),
    ]


def render(audio, rate, mode, limit, block=257, channels=2, root_step=0, original=None):
    name = "BravadoSpectral.dll" if original is None else "BravadoCrevasse.dll"
    dll = ct.CDLL(str(Path(__file__).with_name(name).resolve()))
    dll.VSTPluginMain.argtypes = [Dispatch]
    dll.VSTPluginMain.restype = ct.POINTER(Effect)
    host = Dispatch(lambda e, op, index, val, ptr, arg: int(op == 4 and index >= channels))
    handle = dll.VSTPluginMain(host)
    effect = handle.contents
    assert effect.magic == 0x56737450 and effect.delay == N
    assert tuple(effect.counts[1:4]) == (3, 2 if original is None else 4, 2)
    try:
        effect.dispatch(handle, 0, 0, 0, None, 0)
        effect.dispatch(handle, 10, 0, 0, None, rate)
        effect.dispatch(handle, 11, 0, block, None, 0)
        for i, (name, value) in enumerate(((b"Profile", mode), (b"Lift", None if limit is None else limit/72), (b"Root", root_step/2))):
            buf = ct.create_string_buffer(64)
            effect.dispatch(handle, 8, i, 0, buf, 0)
            assert buf.value == name
            if value is not None:
                effect.set(handle, i, value)
        effect.dispatch(handle, 12, 0, 1, None, 0)
        payload = audio if original is None else np.column_stack((audio,original))
        src = np.ascontiguousarray(payload.T, dtype=np.float32)
        out = np.empty((2,len(audio)),dtype=np.float32)
        for start in range(0, src.shape[1], block):
            ins, outs = [(FloatPtr*len(a))(*(row[start:].ctypes.data_as(FloatPtr) for row in a))
                         for a in (src,out)]
            effect.process(handle, ins, outs, min(block, src.shape[1]-start))
        return out.T.copy()
    finally:
        effect.dispatch(handle, 12, 0, 0, None, 0)
        effect.dispatch(handle, 1, 0, 0, None, 0)


def reference(audio, rate, mode, limit, channels=2, root_step=0, original=None):
    window = np.hanning(N+1)[:-1,None]
    freq = np.fft.rfftfreq(N, 1/rate)
    axis = np.geomspace(25, min(20000,rate/2), 400)
    taps = axis[:,None]*2**np.linspace(-1/24,1/24,13)
    radius = int(np.floor(0.5/np.log2(axis[-1]/25)*399))
    src = np.pad(audio, ((N, N),(0,0)))
    dry = None if original is None else np.pad(original, ((N,N),(0,0)))
    def levels(bins):
        power = ((abs(bins[:,:channels])*4/N)**2).mean(axis=1)
        return 10*np.log10(np.maximum(np.interp(taps,freq,power).mean(axis=1),1e-20))
    out = np.zeros_like(src)
    for end in range(HOP, len(audio), HOP):
        bins = np.fft.rfft(src[end:end+N]*window, axis=0)
        level = levels(bins)
        if mode == 0:
            gap = np.maximum(-level,0)
            desired = gap-gap**(1/(1.1+root_step/10))
        else:
            median = np.array([np.median(level[max(0,i-radius):i+radius+1]) for i in range(400)])
            t = np.clip((level-median+8)/8,0,1)
            desired = .75*t*t*(3-2*t)*np.maximum(-3-level,0)
        fade = np.clip((level+80)/20,0,1)
        gain = np.minimum(desired,limit)*fade*fade*(3-2*fade) if limit else np.zeros(400)
        if dry is not None:
            original_db = levels(np.fft.rfft(dry[end:end+N]*window,axis=0))
            budget = np.where(original_db <= -200,0,limit*2**np.minimum((original_db+18)/36,0))
            gain = np.clip(desired,0,budget)*fade*fade*(3-2*fade)
        freq_gain = np.interp(np.log(np.maximum(freq,1)),np.log(axis),gain,left=0,right=0)
        result = np.fft.irfft(bins*10**(freq_gain[:,None]/20),axis=0)
        out[end:end+N] += result*window*(2/3)
    return out[:len(audio)]


class SpectralTests(unittest.TestCase):
    def test_factory_lift(self):
        audio = np.random.default_rng(9).normal(0,.08,(19000,2))
        for original in (None, audio):
            implicit = render(audio,48000,0,None,original=original)
            np.testing.assert_array_equal(implicit,render(audio,48000,0,5,original=original))
            self.assertGreater(np.max(np.abs(implicit-render(audio,48000,0,6,original=original))),1e-4)

    def test_root_strengths_and_dry_reference(self):
        audio = np.random.default_rng(55).normal(0, .09, (19000,2))
        dry = audio.copy()
        dry[:7000] *= .015
        dry[7000:] += .5*np.cos(np.arange(len(dry)-7000)[:,None]/8)
        for rate in (44100,48000,96000,192000):
            for step in range(3):
                for original in (None,dry):
                    with self.subTest(rate=rate,step=step,weighted=original is not None):
                        options = dict(root_step=step,original=original)
                        actual = render(audio,rate,0,36,**options)
                        np.testing.assert_allclose(actual,reference(audio,rate,0,36,**options),atol=4e-5)
                        np.testing.assert_array_equal(actual,render(audio,rate,0,36,block=1537,**options))
        quiet = render(audio,48000,0,12,original=dry*0)
        np.testing.assert_allclose(quiet[N:],audio[:-N],atol=4e-7)
        self.assertFalse(render(audio*0,48000,0,12,original=dry).any())

    def test_crevasse_fades_quiet_output_even_with_loud_reference(self):
        wave = np.sin(2*np.pi*64*np.arange(5*N)/N)
        dry = np.column_stack((wave,wave))*.5
        for step in range(3):
            quiet = dry*1e-4
            actual = render(quiet,48000,0,6,root_step=step,original=dry)
            np.testing.assert_allclose(actual[N:],quiet[:-N],atol=5e-11)

    def test_reference_and_stream_boundaries(self):
        rng = np.random.default_rng(8)
        signal = rng.normal(0,.024,(19000,2))
        signal[7300:13200] *= .09
        for rate in (44100,48000,96000,192000):
            for mode in (0,1):
                with self.subTest(rate=rate, mode=mode):
                    result = render(signal,rate,mode,12)
                    np.testing.assert_allclose(result,reference(signal,rate,mode,12),atol=2e-5)
                    np.testing.assert_array_equal(result,render(signal,rate,mode,12,block=1537))

    def test_silence_unity_and_stereo(self):
        rng = np.random.default_rng(2026)
        left = rng.normal(0,.08,22000)
        signal = np.column_stack((left, -.5*left))
        for mode in (0,1):
            self.assertFalse(render(signal*0,48000,mode,72).any())
            unity = render(signal,48000,mode,0)
            np.testing.assert_allclose(unity[N:],signal[:-N],atol=3e-7)
            wet = render(signal,48000,mode,9)
            np.testing.assert_allclose(wet[:,1],-.5*wet[:,0],atol=1e-7)
            tiny = render(signal*1e-6,48000,mode,72)
            np.testing.assert_allclose(tiny[N:],signal[:-N]*1e-6,atol=3e-13)
        mono = np.column_stack((left,np.zeros_like(left)))
        np.testing.assert_allclose(render(mono,48000,0,12,channels=1),
                                   reference(mono,48000,0,12,channels=1),atol=3e-6)


if __name__ == "__main__":
    unittest.main()
