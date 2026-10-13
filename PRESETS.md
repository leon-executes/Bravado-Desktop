# Presets

## Choose and compare

1. Choose **Nordrassil** for body and depth; **Signature** for that foundation with
   clearer lower mids and more focused articulation. **Flat** is the reference.
2. Select a preset, then click **Apply changes** or **Enable**.
3. Compare the same passage at matched listening volume. **Save as** keeps personal edits.

Library order: **Signature → Pocket Physics → Flat → Nordrassil → Marble Alibi → Red Herring → Silent Anvil**.

## Version 0.8.9

Bands display from low to high frequency. **Sort bands** is always available in
the equalizer toolbar; saved presets and sets sort automatically. Imported preamp
stages retain their processing sequence while their controls display in frequency order.

- **Bravado Signature Preset** is the 17-band Nordrassil from 0.8.8, unchanged in sound.
- **Nordrassil** is the 14-band Signature from 0.8.8, unchanged in sound.
- **Silent Anvil** is the original Bravado Signature, unchanged in sound.
- Pocket Physics, Flat, Marble Alibi and Red Herring are unchanged.

Signature and Nordrassil have **+1.4 dB preamp**. All other factory preamps are **0 dB**.
Room, Separation, doubling, delay, rumble filtering and output trim are off/zero.
The 16 kHz band in Signature and Nordrassil remains disabled, with its stored
−4 dB gain and Q 1.2 preserved. The 20 kHz cut remains enabled.

Existing applied settings do not change on launch. An exact old factory curve
receives its current name in the panel; edited and personally named curves are retained.
Choose and apply Signature to hear its additional filters.

## Signature definition layer

| Additional peak | Gain | Q | Intent |
| --- | ---: | ---: | --- |
| 420 Hz | −2.4 dB | 1.2 | Relieve overlapping lower-mid weight |
| 2100 Hz | +0.9 dB | 2.2 | Add focused articulation |
| 6000 Hz | +1.2 dB | 2.0 | Support attack and texture below the 9 kHz emphasis |

These are editable bands at 420, 2100 and 6000 Hz, shown in frequency order. Disable all three
to recover Nordrassil's exact curve. Native APO peak filters preserve the complete
frequency/gain/Q definitions; no second audio stream, plugin, new ceiling or
automatic attenuation is introduced.

Calculated at 48 kHz, 90 Hz changes by −0.08 dB and 160 Hz by −0.29 dB. The total
500 Hz response falls from +4.46 to +2.44 dB. At six standard rates from 44.1 to
192 kHz, the change below 120 Hz stays within 0.16 dB. Maximum steady-state response
is approximately +9.62 dB versus Nordrassil's +9.71 dB. These calculations do not
certify transient headroom, acoustic improvement or speaker protection. Positive
boosts can still clip; lower the editable preamp if distortion appears.

The layer is an authored listening candidate. No controlled listening panel or
device measurement establishes universal superiority. Avoid equating added
brightness or increased level with improved detail.

## Calculated gain

48 kHz, including preamp and enabled filters, integrated over 20 Hz–20 kHz.
Pink noise has equal energy per octave; white noise has equal energy per Hz.
These electrical estimates are not LUFS or acoustic loudness.

| Preset | Pink-noise gain | White-noise gain | Maximum response |
| --- | ---: | ---: | ---: |
| Bravado Signature Preset | +6.30 dB | +4.18 dB | +9.62 dB |
| Pocket Physics | +4.36 dB | +1.18 dB | +10.03 dB |
| Flat | -0.00 dB | -0.00 dB | +0.00 dB |
| Nordrassil | +6.48 dB | +3.92 dB | +9.71 dB |
| Marble Alibi | +3.66 dB | +1.76 dB | +8.27 dB |
| Red Herring | +4.37 dB | +0.73 dB | +13.60 dB |
| Silent Anvil | +5.26 dB | +1.66 dB | +10.20 dB |

## Other tonal directions

- **Pocket Physics:** sub-bass foundation, dense 90–160 Hz body and focused 9 kHz detail.
- **Marble Alibi:** forward voices, firm bass and broader treble articulation.
- **Red Herring:** deepest bass weight, concentrated punch and relieved lower mids.
- **Silent Anvil:** the original full-bodied, vivid Bravado curve.

The contours use different gains and bandwidths. Filter overlap means a zero slider
does not guarantee a flat total response at that frequency. Higher Q concentrates
a peak or dip; lower Q spreads it. These are tonal choices, not universal device
calibration or emulation of another manufacturer's hardware.

## APO and Reddit findings

The alternatives use the same native APO peak-filter path as Silent Anvil.
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

All factory bands use native APO **PK** filters. Values below include stored OFF bands.
The source of truth is `defaults()` and the factory constants in the matching `bravado.py`.

### Bravado Signature Preset

Preamp: **+1.4 dB**.

| Hz | Gain dB | Q | State |
| ---: | ---: | ---: | --- |
| 24 | 2.8 | 1.2 | On |
| 30 | 4.5 | 1.3 | On |
| 50 | 2.8 | 2.5 | On |
| 90 | 6 | 1.8 | On |
| 160 | 5.7 | 1.6 | On |
| 300 | 4 | 1.3 | On |
| 420 | -2.4 | 1.2 | On |
| 500 | 0 | 1.8 | On |
| 1000 | 4.8 | 1.2 | On |
| 1600 | 4.6 | 1.6 | On |
| 2100 | 0.9 | 2.2 | On |
| 3000 | -4.3 | 1.3 | On |
| 5000 | 2.8 | 1.5 | On |
| 6000 | 1.2 | 2 | On |
| 9000 | 6 | 1.7 | On |
| 16000 | -4 | 1.2 | Off |
| 20000 | -5 | 1.2 | On |

### Pocket Physics

Preamp: **+0 dB**.

| Hz | Gain dB | Q | State |
| ---: | ---: | ---: | --- |
| 24 | 4 | 1.6 | On |
| 30 | 7 | 2.2 | On |
| 50 | 0 | 2.5 | On |
| 90 | 8 | 2.3 | On |
| 160 | 8 | 2.3 | On |
| 300 | 4 | 1.8 | On |
| 500 | -4 | 2.1 | On |
| 1000 | 3.5 | 2 | On |
| 1600 | 3.7 | 2 | On |
| 3000 | -4.5 | 1.6 | On |
| 5000 | 1.6 | 2 | On |
| 9000 | 8 | 3 | On |
| 16000 | -4.5 | 1.5 | On |
| 20000 | -5.5 | 1.5 | On |

### Flat

Preamp: **+0 dB**.

| Hz | Gain dB | Q | State |
| ---: | ---: | ---: | --- |
| 10 | 0 | 2.5 | On |
| 30 | 0 | 3.75 | On |
| 50 | 0 | 2.5 | On |
| 90 | 0 | 3 | On |
| 160 | 0 | 2 | On |
| 300 | 0 | 1.41 | On |
| 500 | 0 | 1.41 | On |
| 1000 | 0 | 2 | On |
| 1600 | 0 | 2 | On |
| 3000 | 0 | 1 | On |
| 5000 | 0 | 1.5 | On |
| 9000 | 0 | 2 | On |
| 16000 | 0 | 1 | On |
| 20000 | 0 | 1 | On |

### Nordrassil

Preamp: **+1.4 dB**.

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

### Marble Alibi

Preamp: **+0 dB**.

| Hz | Gain dB | Q | State |
| ---: | ---: | ---: | --- |
| 10 | 0 | 0.71 | On |
| 30 | 7 | 2.8 | On |
| 50 | 1 | 2.5 | On |
| 90 | 7.4 | 2.4 | On |
| 160 | 4.8 | 2.3 | On |
| 300 | 2.2 | 1.7 | On |
| 500 | -2.8 | 2.1 | On |
| 1000 | 5.8 | 1.8 | On |
| 1600 | 6.5 | 2.2 | On |
| 3000 | -5.5 | 1.8 | On |
| 5000 | 4 | 2 | On |
| 9000 | 5.8 | 2 | On |
| 16000 | -4 | 1.5 | On |
| 20000 | -5 | 1.5 | On |

### Red Herring

Preamp: **+0 dB**.

| Hz | Gain dB | Q | State |
| ---: | ---: | ---: | --- |
| 20 | 6 | 1.05 | On |
| 30 | 10 | 2.8 | On |
| 50 | 0 | 2.5 | On |
| 90 | 9 | 3.2 | On |
| 160 | 4.8 | 2.2 | On |
| 300 | 1.3 | 1.8 | On |
| 500 | -4 | 1.9 | On |
| 1000 | 3.2 | 1.8 | On |
| 1600 | 4 | 2 | On |
| 3000 | -4.8 | 1.6 | On |
| 5000 | 1 | 2 | On |
| 9000 | 6.8 | 2.6 | On |
| 16000 | -4.5 | 1.5 | On |
| 20000 | -5.5 | 1.5 | On |

### Silent Anvil

Preamp: **+0 dB**.

| Hz | Gain dB | Q | State |
| ---: | ---: | ---: | --- |
| 10 | 8.9 | 2.5 | On |
| 30 | 9.1 | 3.75 | On |
| 50 | 4 | 2.5 | On |
| 90 | 8.2 | 3 | On |
| 160 | 7.1 | 2 | On |
| 300 | 6 | 1.41 | On |
| 500 | 2.2 | 1.41 | On |
| 1000 | 5.1 | 2 | On |
| 1600 | 5.8 | 2 | On |
| 3000 | -3.3 | 1 | On |
| 5000 | 3.3 | 1.5 | On |
| 9000 | 6 | 2 | On |
| 16000 | -3.8 | 1 | On |
| 20000 | -5.1 | 1 | On |

## Validation

Regression checks cover exact preservation of the approved Signature and Anvil
curves, independent factory models, name migration without changing audio,
all seven native exports/imports, disabled-band preservation and finite stable
response at 44.1/48/88.2/96/176.4/192 kHz. Definition checks bound bass changes,
verify lower-mid relief and articulation, and compare maximum frequency response.
Those bounds are tests, not runtime gain caps. Packaged validation uses temporary
APO configuration; it does not apply a preset to the live playback device.
