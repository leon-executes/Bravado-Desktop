/* SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
 * Bravado Desktop spectral profiles. Windows x64 effect, single precision.
 * The host supplies deinterleaved audio. Each instance processes one pair.
 */
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifndef BRAVADO_SIDECHAIN
#define BRAVADO_SIDECHAIN 0
#endif
enum { N = 4096, HALF = N/2, HOP = N/4, POINTS = 400, TAPS = 13,
       INPUTS = BRAVADO_SIDECHAIN ? 4 : 2 };
static const double pi = 3.14159265358979323846;
typedef struct { float re, im; } Complex;
typedef struct { int index; float mix; } Lookup;
typedef struct Effect Effect;
typedef intptr_t (*Dispatch)(Effect *, int, int, intptr_t, void *, float);
typedef void (*Process)(Effect *, float **, float **, int);
typedef void (*Set)(Effect *, int, float);
typedef float (*Get)(Effect *, int);

/* VST 2.x effect ABI on Windows x64. */
struct Effect {
    int magic;
    Dispatch dispatch;
    Process accumulate;
    Set set;
    Get get;
    int programs, parameters, inputs, outputs, flags;
    intptr_t reserved[2];
    int latency, quality[2];
    float io_ratio;
    void *object, *host_data;
    int id, version;
    Process replace;
    void *replace_double;
    char future[56];
};
_Static_assert(sizeof(Effect) == 192, "Requires the Windows x64 effect ABI");

typedef struct {
    Effect effect;
    Dispatch host;
    int pos, channels;
    float mode, lift, root_step, inverse_root;
    float input[INPUTS][N], output[2][N], window[N];
    Complex bins[2][N], twiddle[HALF];
    int reverse[N], radius;
    Lookup tap[POINTS][TAPS], band[HALF+1];
    float power[HALF+1], level[POINTS], dry_level[POINTS], gain[POINTS];
} Spectral;

static float clamp(float x, float lo, float hi) {
    return fmaxf(lo, fminf(x, hi));
}
static float smooth(float x) {
    x = clamp(x, 0, 1);
    return x*x*(3-2*x);
}
static Lookup lookup(double at, int last) {
    double x = fmax(0, fmin(at, last));
    int i = (int)x;
    if (i == last) --i;
    return (Lookup){i, (float)(x-i)};
}
static float interpolate(const float *values, Lookup at) {
    return values[at.index] + at.mix*(values[at.index+1]-values[at.index]);
}
static void configure(Spectral *s, double rate) {
    double high = fmin(20000, rate/2);
    double log_span = log(high/25);
    s->radius = (int)floor(0.5*log(2)*(POINTS-1)/log_span);
    for (int i=0; i<POINTS; ++i) {
        double hz = 25*exp(log_span*i/(POINTS-1));
        for (int j=0; j<TAPS; ++j) {
            double bin = hz*exp2((j-6)/144.0)*N/rate;
            s->tap[i][j] = lookup(bin, HALF);
        }
    }
    for (int k=0; k<=HALF; ++k) {
        double hz = k*rate/N;
        s->band[k] = lookup(log(fmax(hz,25)/25)*(POINTS-1)/log_span, POINTS-1);
        if (hz < 25 || hz > high) s->band[k].index = -1;
    }
}
static void fft(Spectral *s, Complex *a, int inverse) {
    for (int i=0; i<N; ++i) {
        int j = s->reverse[i];
        if (i < j) { Complex tmp=a[i]; a[i]=a[j]; a[j]=tmp; }
    }
    for (int size=2; size<=N; size*=2) {
        int half=size/2, stride=N/size;
        for (int base=0; base<N; base+=size) {
            for (int j=0; j<half; ++j) {
                Complex w=s->twiddle[j*stride], x=a[base+j], y=a[base+j+half];
                if (inverse) w.im = -w.im;
                Complex v = {w.re*y.re-w.im*y.im, w.re*y.im+w.im*y.re};
                a[base+j] = (Complex){x.re+v.re, x.im+v.im};
                a[base+j+half] = (Complex){x.re-v.re, x.im-v.im};
            }
        }
    }
}
/* Maintain the sorted neighborhood as the one-octave median slides. */
static void insert(float *sorted, int count, float value) {
    int j=count;
    while (j && sorted[j-1]>value) { sorted[j]=sorted[j-1]; --j; }
    sorted[j]=value;
}
static void envelopes(Spectral *s) {
    float sorted[POINTS];
    int lo=0, hi=0, count=0;
    for (int i=0; i<POINTS; ++i) {
        float level=s->level[i], lift=0;
        if (!BRAVADO_SIDECHAIN && s->mode>=0.5f) {
            while (lo < i-s->radius) {
                int j=0;
                while (j<count-1 && sorted[j]!=s->level[lo]) ++j;
                memmove(sorted+j,sorted+j+1,(count-j-1)*sizeof(float));
                --count; ++lo;
            }
            while (hi<POINTS && hi<=i+s->radius) {
                insert(sorted,count++,s->level[hi++]);
            }
            float median=0.5f*(sorted[(count-1)/2]+sorted[count/2]);
            lift=0.75f*smooth((level-median+8)/8)*fmaxf(-3-level,0);
        } else if (level<0) {
            lift=-level-powf(-level,s->inverse_root);
        }
        if (BRAVADO_SIDECHAIN) {
            float original=s->dry_level[i];
            float weight=original<=-200 ? 0 : exp2f(fminf(original+18,0)/36);
            s->gain[i]=fminf(fmaxf(lift,0),72*s->lift*weight)*smooth((level+80)/20);
        } else {
            s->gain[i]=s->lift==0 ? 0 : fminf(lift,72*s->lift)*smooth((level+80)/20);
        }
    }
}
static void analyze(Spectral *s, int first_input, float *levels) {
    for (int c=0; c<2; ++c) {
        for (int i=0; i<N; ++i)
            s->bins[c][i]=(Complex){s->window[i]*s->input[first_input+c][(s->pos+i)&(N-1)],0};
        fft(s,s->bins[c],0);
    }
    for (int k=0; k<=HALF; ++k) {
        float sum=0;
        for (int c=0; c<s->channels; ++c) {
            Complex x=s->bins[c][k];
            sum+=x.re*x.re+x.im*x.im;
        }
        s->power[k]=sum*(16.0f/(N*N))/s->channels;
    }
    for (int i=0; i<POINTS; ++i) {
        float power=0;
        for (int j=0; j<TAPS; ++j) power+=interpolate(s->power,s->tap[i][j]);
        levels[i]=10*log10f(fmaxf(power/TAPS,1e-20f));
    }
}
static void frame(Spectral *s) {
    /* Analyze the unprocessed pair first; retain the wet complex bins for synthesis. */
    if (BRAVADO_SIDECHAIN) analyze(s,2,s->dry_level);
    analyze(s,0,s->level);
    envelopes(s);
    for (int k=0; k<=HALF; ++k) {
        if (s->band[k].index<0) continue;
        float g=exp2f(interpolate(s->gain,s->band[k])/6.020599913f);
        for (int c=0; c<2; ++c) {
            Complex *b=s->bins[c];
            b[k].re*=g; b[k].im*=g;
            if (k>0 && k<HALF) b[N-k]=(Complex){b[k].re,-b[k].im};
        }
    }
    for (int c=0; c<2; ++c) {
        fft(s,s->bins[c],1);
        for (int i=0; i<N; ++i)
            s->output[c][(s->pos+i)&(N-1)] += s->bins[c][i].re*s->window[i]*(2.0f/(3*N));
    }
}
static void process(Effect *e, float **in, float **out, int count) {
    Spectral *s=e->object;
    for (int i=0; i<count; ++i) {
        for (int c=0; c<INPUTS; ++c) {
            float x=in[c][i];
            s->input[c][s->pos]=isfinite(x) && fabsf(x)>1e-20f ? x : 0;
        }
        for (int c=0; c<2; ++c) {
            out[c][i]=s->output[c][s->pos];
            s->output[c][s->pos]=0;
        }
        s->pos=(s->pos+1)&(N-1);
        if (!(s->pos&(HOP-1))) frame(s);
    }
}
static void set(Effect *e, int index, float value) {
    Spectral *s=e->object;
    if (!isfinite(value)) return;
    if (index==0) s->mode=value>=0.5f;
    if (index==1) s->lift=clamp(value,0,1);
    if (index==2) {
        static const float roots[]={1.1f,1.2f,1.3f};
        int step=(int)roundf(clamp(value,0,1)*2);
        s->root_step=step*0.5f;
        s->inverse_root=1.0f/roots[step];
    }
}
static float get(Effect *e, int index) {
    Spectral *s=e->object;
    return index==0 ? s->mode : index==1 ? s->lift : index==2 ? s->root_step : 0;
}
static intptr_t dispatch(Effect *e, int op, int index, intptr_t value, void *ptr, float arg) {
    Spectral *s=e->object;
    switch (op) {
    case 1: free(s); return 1;
    case 5: if (ptr) strcpy(ptr,"Bravado"); return 1;
    case 8: if (ptr) strcpy(ptr,index==0 ? "Profile" : index==1 ? "Lift" : "Root"); return 1;
    case 10: if (arg>=8000 && arg<=768000) configure(s,arg); return 1;
    case 12:
        if (value) {
            memset(s->input,0,sizeof(s->input)); memset(s->output,0,sizeof(s->output));
            s->pos=0;
            s->channels = s->host && s->host(e,4,1,0,NULL,0)==1 ? 1 : 2;
        }
        return 1;
    case 35: return 1;
    case 45: case 48: if (ptr) strcpy(ptr,BRAVADO_SIDECHAIN ? "Bravado Crevasse" : "Bravado Spectral"); return 1;
    case 47: if (ptr) strcpy(ptr,"Bravado"); return 1;
    case 49: return 1;
    case 58: return 2400;
    default: return 0;
    }
}
__declspec(dllexport) Effect *VSTPluginMain(Dispatch host) {
    Spectral *s=calloc(1,sizeof(*s));
    if (!s) return NULL;
    s->effect=(Effect){.magic=0x56737450,.dispatch=dispatch,.set=set,.get=get,
        .programs=1,.parameters=3,.inputs=INPUTS,.outputs=2,.flags=16,.latency=N,.io_ratio=1,
        .object=s,.id=BRAVADO_SIDECHAIN ? 0x42764372 : 0x42765370,.version=2,.replace=process};
    s->host=host; s->channels=2; s->lift=5.0f/72; s->inverse_root=1.0f/1.1f;
    for (int i=0; i<N; ++i) {
        s->reverse[i]=(s->reverse[i/2]/2)+(i%2)*HALF;
        s->window[i]=(float)(0.5-0.5*cos(2*pi*i/N));
        if (i<HALF) s->twiddle[i]=(Complex){(float)cos(2*pi*i/N),(float)-sin(2*pi*i/N)};
    }
    configure(s,48000);
    return &s->effect;
}
