# Presets

## Choose and compare

1. Library order: **Signature → Pocket Physics → Flat → Nordrassil → Marble Alibi → Red Herring**.
   Choose **Nordrassil** for broad strength between Signature's fullness and Pocket's punch.
2. Select a preset. Click **Apply changes**, or **Enable** when disconnected.
3. Compare the same passage at matched listening volume. **Flat** is the reference.
4. Edit frequency, Q and gain to suit the device. **Save as** keeps a personal copy.

Nordrassil uses an explicit **+1.4 dB** preamp; the other five remain at **0 dB**.
All five existing presets retain their exact settings. Room, Separation,
doubling, delay, rumble filtering and output trim are off/zero in the factory presets.
The alternatives are assertive tonal choices, not universal device corrections.
Positive EQ boosts need playback headroom; lower the editable preamp if distortion
appears. No automatic attenuation, limiter or ceiling is added.

## Nordrassil

Nordrassil combines full bass and lower-mid body with a shaped 3 kHz dip and
defined 9 kHz detail. Its preamp is **+1.4 dB**. The 16 kHz band is **disabled**;
its stored −4 dB gain and Q 1.2 remain available if you choose to enable it.
The 20 kHz cut stays enabled. Room, Separation and doubling are off.

The following 48 kHz comparison includes preamp and enabled filters only.
Mean-square gain is calculated over 20 Hz–20 kHz for pink noise (equal energy
per octave) and white noise (equal energy per Hz). Values describe electrical
signal gain, not LUFS, acoustic loudness or a controlled listening result.

| Preset | Pink-noise gain | White-noise gain | Maximum frequency-response gain |
| --- | ---: | ---: | ---: |
| Bravado Signature Preset | +5.26 dB | +1.66 dB | +10.20 dB |
| Pocket Physics | +4.36 dB | +1.18 dB | +10.03 dB |
| Flat | -0.00 dB | -0.00 dB | +0.00 dB |
| Nordrassil | +6.48 dB | +3.92 dB | +9.71 dB |
| Marble Alibi | +3.66 dB | +1.76 dB | +8.27 dB |
| Red Herring | +4.37 dB | +0.73 dB | +13.60 dB |

The maximum response is about +9.7 dB, below Signature's +10.2 dB maximum.
These are steady-state estimates; recording spectrum, transient peaks and
downstream processing still determine clipping. Lower the visible preamp if
playback distorts. No automatic attenuation, ceiling or limiter is added.

All bands are **PK**. Only the 16 kHz band is disabled.

| Hz | Gain dB | Q | State |
| ---: | ---: | ---: | --- |
| 24 | 2.8 | 1.2 | On |
| 30 | 4.5 | 1.3 | On |
| 50 | 2.8 | 2.5 | On |
| 90 | 6 | 1.8 | On |
| 160 | 5.7 | 1.6 | On |
| 300 | 4 | 1.3 | On |
| 500 | 0 | 1.8 | On |
| 1000 | 4.8 | 1.2 | On |
| 1600 | 4.6 | 1.6 | On |
| 3000 | -4.3 | 1.3 | On |
| 5000 | 2.8 | 1.5 | On |
| 9000 | 6 | 1.7 | On |
| 16000 | -4 | 1.2 | Off |
| 20000 | -5 | 1.2 | On |

## Other tonal directions

| Preset | Main emphasis | Deliberate trade-off |
| --- | --- | --- |
| Marble Alibi | Forward 1–1.6 kHz voices, firm 90 Hz punch, broader treble articulation | Less deep-bass dominance and less 160 Hz density than the specialist alternatives |
| Red Herring | Strongest 20–30 Hz weight, concentrated 90 Hz punch, deepest 500 Hz relief | Quieter vocal presence and restrained 5 kHz energy; 9 kHz remains distinct |
| Pocket Physics | 24–30 Hz foundation, broad 90–160 Hz body, supported 300 Hz warmth, strongest/narrowest 9 kHz peak | Less deep-sub emphasis than Red; more body and treble contrast than Marble |

These are separate original contours. They are not gain-scaled copies of one
curve. Frequency regions, bandwidths and bass-to-mid-to-treble balances differ.
They use Signature's assertive scale while retaining their own tonal priorities.

## Filter shape matters

All bands use native APO **peak filters** (`PK`). Each has an explicit centre
frequency, gain and **Q**. A higher Q concentrates a peak or dip around its centre;
a lower Q spreads its influence. The audible result is the complete cascade, not
the largest slider. See the [APO configuration reference](https://sourceforge.net/p/equalizerapo/wiki/Configuration%20reference/).

- **Sub-bass:** Red adds a 20 Hz peak (+6 dB, Q 1.05) below its existing 30 Hz
  peak. Pocket adds a 24 Hz peak (+4 dB, Q 1.6) and broadens its 30 Hz peak to
  +7 dB, Q 2.2. Both reuse the previously neutral 10 Hz slot; Marble is unchanged.
  These shapes fill 18–40 Hz without another 90 Hz boost or a large 50 Hz lift.
- **90 Hz:** the main punch peak. Its Q differs by preset; Red concentrates the
  attack region while Pocket overlaps more deliberately with 160 Hz body.
- **50 Hz:** zero on Red and Pocket, +1 dB on Marble. Adjacent bands still add gain
  there, but the combined response stays far below each preset's 90 Hz emphasis.
- **500 Hz / 3 kHz:** defined peak cuts. The intervening vocal region stays present;
  Marble deliberately brings it further forward.
- **9 kHz:** a real peak in every alternative. Pocket's Q 3 gives the narrowest,
  strongest focus. Marble combines its peak with more 5 kHz articulation.
- **16 / 20 kHz:** Q 1.5 peak cuts restrain the upper treble without broadly
  attenuating the 9 kHz region, including at higher sample rates.

This is an authored balance, not evidence that particular frequencies are always
bad or good. EQ multiplies the device and room response. These contours cannot
reproduce a reference transducer or repair an acoustic cancellation universally.

## APO and Reddit findings

The alternatives use the same native APO peak-filter path as Signature.
Their distinct characters come from the filter definitions, not another engine.
Copying gain numbers alone is insufficient when filter type, frequency, Q or shelf
convention differs. The revised exports preserve all of those parameters.

- [Oratory1990's technical FAQ](https://www.reddit.com/r/oratory1990/wiki/index/faq/):
  use the full parametric filter definition; Peace's Q-defined shelves match the
  intended convention. Bass preference and device response vary. A measured
  correction belongs to its target device. Bravado uses that method, not a borrowed
  headphone correction as universal EQ.
- [Reddit bass-EQ discussion](https://www.reddit.com/r/headphones/comments/1d7zk7x/why_does_this_eq_sound_so_much_better_than_any_eq/):
  community observations prompted checks for overlapping bass boosts and louder-is-better
  comparison bias. They are listening anecdotes, not validation of these presets.
- [Surface Laptop Studio APO project](https://github.com/piereligio/Equalizer-APO-Surface-Laptop-Studio):
  its separate physical-mode profiles illustrate why laptop correction is specific.
  We do not copy its corrections or add its optional compressor/plugin dependencies.

Research reviewed 4 October 2026. The numerical settings below are original Bravado
choices informed by those references and listening feedback. No third-party profile
or source code is incorporated. Identical per-channel EQ preserves stereo routing
and introduces no additional cross-channel cancellation on a linear mono downmix.

## Brand references

Manufacturer descriptions establish design intent, not independent performance
proof. EQ does not reproduce electrostatic transducers, force-cancelling woofers,
physical venting or adaptive room processing.

| Reference | Published design priority | Decision in Bravado |
| --- | --- | --- |
| [TRUTHEAR HEXA](https://truthear.com/products/hexa) and [ZERO:RED](https://truthear.com/products/zero-red) | HEXA describes moderate bass and natural bass/mid integration; RED describes bass emphasis with a neutral-oriented upper range and smoother listening | Marble Alibi prioritises voice definition. Red Herring separates bass weight from a low-mid dip. Neither copies an IEM ear-gain target onto speakers. |
| [Sennheiser HD 600](https://uk.sennheiser-hearing.com/products/hd-600) and [HE 1](https://global.sennheiser-hearing.com/products/sennheiser-he-1) | Reference listening and transparent open-back reproduction; HE 1 pursues low distortion through specialised transducers and electronics | Marble Alibi gives voice strong presence and relieves 500 Hz congestion and 3 kHz glare. No claim of electrostatic speed, resolution or HD 600 calibration. |
| [Warwick APERIO technology](https://warwickacoustics.com/headphones/collection/aperio/technology/) | Low-distortion electrostatic transducers, resonance control, carefully managed gain and low crosstalk | Marble Alibi favours smooth changes and untouched stereo relationships. EQ cannot supply Warwick's mechanical or electrical performance. |
| [64 Audio U4s](https://www.64audio.com/products/u4s) and [apex](https://www.64audio.com/pages/apex) | Engaging bass, balanced mids and open treble; physical venting changes the ear-canal experience | Red Herring combines broad bass weight with restrained upper-mid energy and a focused 9 kHz peak. No simulated venting or forced stereo widening. |
| [MacBook Pro audio design](https://www.apple.com/uk/newsroom/2021/10/apple-unveils-game-changing-macbook-pro/) | Six speakers, force-cancelling woofers and tweeters produce bass and spatial presentation from a compact enclosure | Pocket Physics favours audible bass body and clarity. It cannot add woofer excursion, force cancellation or Apple's spatial processing. |
| [Teenage Engineering OB–4](https://teenage.engineering/products/ob-4) and [OD-11](https://teenage.engineering/products/od-11/technology) | Compact natural reproduction, bass-reflex engineering and room-oriented speaker design | Pocket Physics uses broad body/presence adjustments. No bass-reflex or ortho-directional emulation; these are physical acoustic designs. |
| [LG xboom by will.i.am](https://www.lg.com/us/newsroom/media-entertainment/lg-reveals-2025-xboom-by-william-audio-products-fortified-with-signature-sound-and-ai-versatility) | A warmer, balanced signature with selectable emphasis and adaptive features | Red Herring supplies warmth without heavily recessing voices; Pocket Physics prioritises useful punch. These are fixed presets, not LG AI Sound or room calibration. |


## Names

- **Marble Alibi:** a nod to the HE 1's marble and the electrostatic ideal.
- **Red Herring:** a RED hint; no single device target is the answer for everything.
- **Pocket Physics:** compact-speaker ambition meeting the laws of acoustics.

Original names, not advertising quotations or endorsement claims. The references
inform three directions rather than seven purported brand emulations.

## Exact settings

For Marble, Red and Pocket, all 14 bands are enabled **PK** filters.
Each cell is **gain dB / Q**. Nordrassil has its own table above.
Source of truth: `VOICES` and `factory_presets()` in `bravado.py` in the matching source release.

| Hz (Marble / Red / Pocket) | Marble Alibi | Red Herring | Pocket Physics |
| ---: | ---: | ---: | ---: |
| 10 / 20 / 24 | 0 / 0.71 | 6 / 1.05 | 4 / 1.6 |
| 30 | 7 / 2.8 | 10 / 2.8 | 7 / 2.2 |
| 50 | 1 / 2.5 | 0 / 2.5 | 0 / 2.5 |
| 90 | 7.4 / 2.4 | 9 / 3.2 | 8 / 2.3 |
| 160 | 4.8 / 2.3 | 4.8 / 2.2 | 8 / 2.3 |
| 300 | 2.2 / 1.7 | 1.3 / 1.8 | 4 / 1.8 |
| 500 | -2.8 / 2.1 | -4 / 1.9 | -4 / 2.1 |
| 1000 | 5.8 / 1.8 | 3.2 / 1.8 | 3.5 / 2 |
| 1600 | 6.5 / 2.2 | 4 / 2 | 3.7 / 2 |
| 3000 | -5.5 / 1.8 | -4.8 / 1.6 | -4.5 / 1.6 |
| 5000 | 4 / 2 | 1 / 2 | 1.6 / 2 |
| 9000 | 5.8 / 2 | 6.8 / 2.6 | 8 / 3 |
| 16000 | -4 / 1.5 | -4.5 / 1.5 | -4.5 / 1.5 |
| 20000 | -5 / 1.5 | -5.5 / 1.5 | -5.5 / 1.5 |

## Compare with Signature

Combined digital response in dB at 48 kHz, **including preamp**. Equal graph scales;
no visual exaggeration. These values include filter overlap.

| Preset | 20 Hz | 30 Hz | 50 Hz | 90 Hz | 160 Hz | 500 Hz | 1.2 kHz | 3 kHz | 9 kHz |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Bravado Signature Preset | +1.9 | +10.1 | +5.6 | +10.2 | +9.4 | +5.0 | +5.8 | -1.4 | +5.5 |
| Marble Alibi | +1.3 | +7.4 | +2.7 | +8.3 | +6.0 | -1.2 | +6.1 | -3.8 | +5.7 |
| Red Herring | +7.8 | +13.6 | +3.0 | +10.1 | +5.7 | -3.1 | +3.3 | -4.0 | +6.3 |
| Pocket Physics | +4.8 | +9.9 | +2.9 | +9.5 | +9.6 | -2.4 | +3.4 | -3.6 | +7.5 |

The earlier alternatives peaked around +1.2 to +1.6 dB including their negative
preamps; these revisions operate on Signature's much stronger tonal scale. The
change includes both contour and level. Match playback loudness when comparing
their character; a higher curve alone is not evidence of higher audio quality.

## Validation

Regression tests check stable poles, finite response and native APO export/import
of magnitude and phase at 44.1, 48, 88.2, 96, 176.4 and 192 kHz. They check bass,
90-versus-50 Hz emphasis, the midrange dips and 9 kHz lift. Regional comparisons
ensure Red retains the deepest weight, Pocket the most 120–220 Hz body and Marble
the strongest 900–1800 Hz presence. The sub-bass regression also verifies that the added response stays below
0.04 dB above 300 Hz, below 1.3 dB at 50 Hz and below 0.35 dB at 90 Hz.
Those are response checks, not runtime gain caps.

Nordrassil's reference test checks every frequency, gain, Q and enabled flag
against the approved settings. At all six sample rates, it verifies stability and
that the disabled 16 kHz band contributes neither gain nor phase. Native APO
export/import retains that band as OFF with its original values. The factory
order and all six native exports are tested.

Packaged checks cover preset protection, preview/export, applying to temporary APO
configuration, relocation and restart. No controlled listening panel or multi-device
acoustic measurements were performed. Choose by listening on your actual equipment.
