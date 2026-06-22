# Hall-Sensor Neighbor Detection: Design & Order Plan

Design date: 2026-05-18. Replaces the PN5180 NFC reader on each cube with a
passive magnetic sensing layout. Written to support ordering PCBs and parts
**without prior bench validation** (no lab access for ~4 weeks).

## Why replace PN5180

Per `logs/diag_cubes.log` + `logs/diag_cubes.log.bak` (~336k samples,
2026-03-04 → 2026-05-03):

- All documented ESP32 chip failures are on the GPIO connected to the
  PN5180 BUSY signal (GPIO 35 on v6, GPIO 36 on v1). No other GPIO has
  failed. Root-cause hypothesis: ground bounce between ESP32 and PN5180,
  driven by the 13.56 MHz RF stage and absence of a ground plane.
- Cube 2's old PN5180 logged 5500 lifetime resets; 7% of one-second
  windows had multi-second `nfc_max_us` stalls before replacement
  (2026-04-29). "Healthy" cubes still exhibit the same failure mode at
  lower frequency.
- Even when healthy, a tag-adjacent PN5180 spends 100–400 ms/sec inside
  `readNfcCard()` (each call ~20 ms at 20 Hz). End-to-end neighbor-change
  detection has a worst case of ~70 ms.

Hall replacement removes the RF source, the BUSY-pin failure path, and
the ~20 ms read cost. Expected per-read latency: <100 µs.

MQTT/broker latency is **not** the bottleneck (p50 `mqtt_us` ≈ 155 µs on
all cubes). Don't conflate transport with NFC.

## Architecture

**Constant-weight 2-of-6 ID encoding + opposite-polarity center
presence sensor.** All-digital, no ADC.

### Sensor layout (mating face of the cube, viewed from the neighbor)

```
   ●───●───●         6× ID sensors (south-pole-detect unipolar)
   │   ✕   │         12 mm pitch, 2×3 grid
   ●───●───●         1× presence sensor (north-pole-detect unipolar)
                     at geometric center between rows
```

Sensor PCB footprint: ~28 × 16 mm core (sensors + traces), ~34 × 22 mm
including mounting holes, decoupling, and connector.

Mount the sensor PCB inside the detecting face of the cube with the
**sensor side of the board against the cube wall** (sensors point at
the magnets). PCB thickness doesn't contribute to the magnet-to-die
gap in this orientation, so standard 1.6 mm is fine.

### Magnet layout (mating face of the *neighbor* cube)

Same 2×3 grid at 12 mm pitch, plus the center presence position. Each
cube populates:

- **2 ID magnets**, south-pole-out, in one of 15 weight-2 patterns
- **1 presence magnet**, north-pole-out, in the center position
- Optional: 2–4 **alignment magnets**, weak (3 mm × 1 mm N42), at face
  corners, mated against steel inserts on the neighbor's sensor face for
  light tactile snap (no strong detent — players complained about
  separation force in the past)

### Why this scheme

| Failure mode | Defense |
|---|---|
| Half-mated cube (some ID magnets disengaged) | Weight ≠ 2 → reject |
| Crosstalk tripping a third ID sensor | Weight = 3+ → reject |
| Slide-to-shifted-weight-2 (magnets land on wrong sensors) | Presence magnet drags off center sensor → reject |
| Stray magnet field of wrong polarity | Unipolar sensors ignore wrong-polarity fields |
| Presence-magnet crosstalk into ID sensors | South-detect sensors ignore presence's north field |
| ID-magnet crosstalk into presence sensor | North-detect sensor ignores ID magnets' south field |
| Cube rotated (90°/180°/270°) | Off-center presence position acts as rotation key; with table-flat constraint, only correct orientation triggers presence |
| Backwards magnet at assembly | Wrong-polarity field is invisible to unipolar sensors → caught as weight 1 or 0 |

The opposite-polarity presence is what lets the presence sensor sit at
the geometric center of the ID array without crosstalk — keeps the PCB
small.

## ID assignment

C(6,2) = 15 patterns. Use 12 for cubes 1–12, 3 spare for diagnostics or
future expansion.

Sensor position numbering, looking at the sensor PCB from outside the
cube:

```
    1   2   3       (top row)
        ✕            (presence, between rows)
    4   5   6       (bottom row)
```

| Cube | Magnet positions | Bit mask (P6 P5 P4 P3 P2 P1) |
|------|------------------|------------------------------|
|  1   | 1, 2 | 000011 |
|  2   | 1, 3 | 000101 |
|  3   | 1, 4 | 001001 |
|  4   | 1, 5 | 010001 |
|  5   | 1, 6 | 100001 |
|  6   | 2, 3 | 000110 |
|  7   | 2, 4 | 001010 |
|  8   | 2, 5 | 010010 |
|  9   | 2, 6 | 100010 |
| 10   | 3, 4 | 001100 |
| 11   | 3, 5 | 010100 |
| 12   | 3, 6 | 100100 |
| spare | 4, 5 / 4, 6 / 5, 6 |

All cubes also have the **center presence magnet** populated, north-pole-out.

Magnet polarity convention (toward the cube wall = toward the neighbor):

- ID magnets: **south pole out**
- Presence magnet: **north pole out**
- Alignment magnets (if used): **south pole out**, mated against steel
  inserts on the neighbor's sensor face

## Bill of materials

### Per cube (sensor side)

| Item | Part | LCSC | Qty | Unit price | Notes |
|------|------|------|-----|------------|-------|
| ID Hall sensor | GH1230KSW (unipolar south-detect, SOT-23-3L) | C2683247 | 6 | $0.17 | 2.8–24 V supply, open-drain output |
| Presence Hall sensor | TI DRV5055**A4**QDBZR (linear ratiometric, SOT-23) | C266123 | 1 | $0.73 | 3.3 V supply, 12.5 mV/mT centered at VCC/2 = 1.65 V, ±169 mT range — picked for no saturation at small magnet-to-die gaps |
| Pull-up resistor | 10 kΩ 0603 | basic | 6 | trivial | One per ID sensor (open-drain output) |
| Decoupling cap | 100 nF 0402 | basic | 7 | trivial | One per sensor |
| Connector to main board | 9-pin JST-XH 2.5 mm header (HC-XHB-9A) | C2845497 | 1 | $0.10 | Mates to v6 main board's existing NFC header; see pinout table below |
| Presence pigtail | 2-pin header or flying wire | TBD | 1 | trivial | Presence signal to GPIO 36 tap on main board |

**Per-cube sensor electronics: ~$1.75 + connector + PCB**

### Per cube (magnet side)

| Item | Spec | Qty | Notes |
|------|------|-----|-------|
| ID magnets | N42, 3 mm dia × 2 mm thick, axial polarity | 2 | South-pole-out per ID table |
| Presence magnet | N42, 3 mm dia × 2 mm thick, axial polarity | 1 | North-pole-out, center position |
| Alignment magnets (optional) | N42, 3 mm dia × 1 mm thick | 2–4 | South-pole-out at corners of mating face |
| Steel inserts for alignment | M3 steel washers or pucks | 2–4 | At corners of sensor face, mated against alignment magnets |

### For 12 cubes

- 72× GH1230KSW (+10 spares)
- 12× DRV5055A4QDBZR (+5 spares)
- ~120 magnets (3 mm × 2 mm) — order ~150 for losses
- ~60 alignment magnets (3 mm × 1 mm) if using them
- 12× sensor PCBs (assembled by JLC)
- Include a **small polarity test breakout** on the same JLC panel
  (~$2 marginal) carrying 1× GH1230KSW + 1× DRV5055A4QDBZR on breakout
  headers for first-receipt polarity verification. Optionally add a
  3rd footprint for SS341RT (digital presence alternative) on the same
  SOT-23-3 pad pattern as the DRV5055 to validate the dual-footprint
  claim before relying on it in v2.

## PCB design

- **2 layers**, standard 1.6 mm thickness, no ground plane required
  (Hall sensors are quiet DC loads; the PN5180-driven failure mode is
  gone)
- Sensor side faces the cube wall (sensors point at the magnets); PCB
  thickness is not in the magnet-to-die gap budget
- Component side carries decoupling caps and pull-ups
- Two M2 mounting holes for fixed alignment to the enclosure — sensor
  position relative to the cube wall must be within ±1 mm of nominal,
  so don't rely on the connector cable for mechanical positioning
- Trace routing: short, direct GND from each sensor to a star-ground
  point near the connector. Carry-over discipline from the PN5180-era
  short-ground-wire fix, even though Hall sensors don't need it
- Sensor pitch: **12 mm center-to-center**. Tightening below 10 mm risks
  ID-to-ID crosstalk; widening past 15 mm wastes board area without
  benefit. 12 mm chosen as comfortable middle.

## Main board changes

**None for the connector** — the sensor board reuses the existing
PN5180 connector. This means existing v6 main PCBs can be repurposed
without a respin; only the daughterboard is new.

The PN5180 connector carries: SPI (MOSI, MISO, SCK), NSS (32), RST (17),
BUSY (35), +5V, +3.3V, GND. Six freed GPIOs + 2 power rails + GND.

### Pin assignment

The v6 main board's existing NFC connector is a **9-pin JST-XH 2.5 mm
header** (footprint `CONN-TH_9P_P2.50_HCTL_HC-XHB-9A`, LCSC C2845497).
The daughterboard must mate physically to this same connector.

Extracted from `pcb/v6/kicad/schematic-netlist.xml`:

| Conn pin | v6 net | Hall function | ESP32 GPIO | Notes |
|---------:|--------|---------------|-----------:|-------|
| 1 | GND   | GND                  | —  | star-ground anchor on daughterboard |
| 2 | BUSY  | ID sensor 6 (P6)     | 35 | input-only; 10 kΩ pull-up on PCB (open-drain) |
| 3 | SCK   | ID sensor 4 (P4)     | 18 | 10 kΩ pull-up on PCB |
| 4 | MISO  | ID sensor 5 (P5)     | 34 | input-only; 10 kΩ pull-up on PCB |
| 5 | MOSI  | ID sensor 3 (P3)     | 23 | 10 kΩ pull-up on PCB |
| 6 | NSS   | ID sensor 1 (P1)     | 32 | 10 kΩ pull-up on PCB |
| 7 | RST   | ID sensor 2 (P2)     | 17 | 10 kΩ pull-up on PCB |
| 8 | 3V    | +3.3 V               | —  | sensor supply (10 mA DRV5055 + 6× 2 mA GH1230 = ~22 mA, well within AMS1117 budget) |
| 9 | +5V   | NC                   | —  | **do not route** on daughterboard — Hall sensors are 3.3 V only |

Presence sensor: **separate 2-wire pigtail** from daughterboard
(presence OUT + GND) to the existing GPIO 36 tap point (the
`HALL_SENSOR_PIN` pad already used by v6_with_hall builds). Do not
route presence through the 9-pin connector.

Six ID signals ride the existing PN5180 connector. The 7th (presence)
runs over a separate 2-wire pigtail (signal + optional GND if not
already connected at the connector) terminating at the existing GPIO 36
pad — same pin already used by `HALL_SENSOR_PIN` in v6_with_hall builds.

Primary part is **DRV5055A4QDBZR** (analog linear). If laying out the
footprint, verify pin-for-pin against SS341RT before claiming
compatibility — both are SOT-23-3 but the pin order (VCC/OUT/GND vs
GND/OUT/VCC) is not standardized across vendors. If they happen to
match, mark the footprint as dual-use; if not, commit to the DRV5055
pinout and treat SS341RT swap as a v2 respin.

Power: +3.3 V from the existing connector pin. Drop +5V to the sensor
board entirely (Hall sensors run at 3.3 V).

## Firmware decoding logic

Pseudocode for the read loop, replacing `readNfcCard()`:

```c
const uint8_t cube_id_table[16] = {
    // index = 6-bit ID mask, value = cube_id (0 = invalid)
    [0b000011] = 1,
    [0b000101] = 2,
    [0b001001] = 3,
    [0b010001] = 4,
    [0b100001] = 5,
    [0b000110] = 6,
    [0b001010] = 7,
    [0b010010] = 8,
    [0b100010] = 9,
    [0b001100] = 10,
    [0b010100] = 11,
    [0b100100] = 12,
    // all other masks: invalid (0)
};

uint8_t read_neighbor_id() {
    bool presence = digitalRead(PIN_PRESENCE);
    if (!presence) return 0;  // no neighbor

    uint8_t id_mask = 0;
    if (digitalRead(PIN_ID1)) id_mask |= 0b000001;
    if (digitalRead(PIN_ID2)) id_mask |= 0b000010;
    if (digitalRead(PIN_ID3)) id_mask |= 0b000100;
    if (digitalRead(PIN_ID4)) id_mask |= 0b001000;
    if (digitalRead(PIN_ID5)) id_mask |= 0b010000;
    if (digitalRead(PIN_ID6)) id_mask |= 0b100000;

    if (__builtin_popcount(id_mask) != 2) return 0;
    return cube_id_table[id_mask & 0x3F];  // sparse lookup, 0 = invalid
}
```

Polling rate: 1 kHz is comfortable (each digitalRead is ~µs).

### On debounce

Each Hall sensor has built-in hysteresis (GH1230KSW: 1 mT operate/release
gap; SS341RT: ~12.5 mT gap), which handles **single-sensor chatter at
the threshold**. Hysteresis does *not* handle **multi-sensor incoherence
during motion** — as a cube seats, ID magnets engage their sensors
sequentially over a few ms, so you transiently see weight = 1 or 3
before settling at 2.

The weight check + presence check already reject these transient states
(they just don't qualify as valid IDs). Without debounce you'd see brief
"no neighbor → neighbor X → no neighbor" cycles in the published stream
during sloppy play.

**Short debounce recommended**: require 5–10 consecutive identical
reads at 1 kHz polling = 5–10 ms confirmation window. Suppresses
motion-blur publication without adding meaningful latency.

### Analog presence + alignment feedback UX

Presence uses **DRV5055A4QDBZR**, a 3.3 V linear/ratiometric Hall in
SOT-23. Output centered at VCC/2 ≈ 1.65 V; field swings it positive or
negative depending on polarity (12.5 mV/mT, ±169 mT range so no
saturation risk at close gaps). Read via ADC1 on GPIO 36.

Two reasons to go analog over digital from day one:

1. **Sharper "fully seated" gate.** Threshold on magnitude above a
   known seating floor; partial proximity doesn't trigger. Replaces
   debounce on the presence channel — the magnitude itself encodes
   seating depth.

2. **Alignment feedback for the player.** The analog magnitude maps
   directly to "how well-aligned is the cube" and can be rendered on
   the existing HUB75 screen. No new hardware needed:
   - Color-shifted letter: dim/red when no neighbor, fading through
     orange to bright green as alignment strength rises
   - Or a thin bar at screen edge filling as alignment improves
   - Solves the silent "why isn't it working" failure when cubes are
     nearly-but-not-quite mated

Polarity discrimination preserved: presence magnet is north-pole-out,
so seating drives the ADC reading negative. Threshold on signed
voltage isolates from south-out ID-magnet crosstalk (which would push
the reading positive — wrong direction, ignored).

Calibration: per-part zero offset varies ±50 mV. Handle via a running
minimum-magnitude tracker (the lowest |reading| observed over a sliding
window approximates the no-neighbor baseline). Or sample at boot
assuming no neighbor at startup. NVS-persist for fast convergence.

ID channels remain digital with short (5–10 ms) debounce for
multi-sensor motion blur as described above.

## Failure mode coverage

| Scenario | Behavior |
|---|---|
| No neighbor | presence = 0 → return 0 (no neighbor) |
| Fully-seated valid neighbor | weight = 2, presence = 1 → return cube ID |
| Half-mated (1 ID magnet engaged) | weight = 1 → return 0 |
| Half-mated (presence engaged, 1 ID off) | weight = 1 → return 0 |
| Lateral slide by 12 mm to shifted weight-2 | presence magnet drags off → presence = 0 → return 0 |
| ID magnet installed backwards | Unipolar south-detect ignores north-out magnet → weight = 1 → return 0 (caught) |
| Presence magnet installed backwards | Unipolar north-detect ignores south-out magnet → presence = 0 → return 0 (caught) |
| Cube rotated 90°/180°/270° | Presence magnet at wrong position → presence = 0 → return 0 (caught, given table-flat constraint) |
| Stray external magnetic field | Most likely trips wrong polarity = invisible, or single sensor = weight 1 → return 0 |

**Uncaught failure**: two ID magnets *both* installed backwards on the
same cube. Reads as "no neighbor" rather than as a different cube ID, so
fails closed. Mitigation: assembly fixture or visual check, plus
first-boot self-test where each cube's NVS-stored expected pattern is
compared against pairing reads with a known reference.

## Risks of ordering blind

These are the assumptions that have **not** been bench-validated. If
any fails, mitigation noted:

1. **DRV5055A4 polarity convention and saturation behavior** —
   TI datasheet should confirm direction of voltage swing for north vs
   south fields. Firmware threshold direction is a one-line fix at
   flash time if the convention turns out to be the other sign.
   Saturation should not be an issue with the A4 grade (±169 mT range);
   only a concern if the magnet-to-die gap turns out tiny *and* you've
   swapped to A3 or A1 to save cost.

2. **Polarity convention of GH1230KSW** — assumed south-pole detect per
   LCSC's "unipolar" + positive operate-point convention. Same mitigation:
   verify on breakout first.

3. **Crosstalk at 12 mm pitch** — extrapolated from dipole field math,
   not measured. If a magnet at one position trips its diagonal neighbor
   at 12 mm pitch, the constant-weight check still catches it (weight
   ≥ 3), but a real bench measurement would shrink the uncertainty.
   Mitigation: 12 mm is conservative; widen to 15 mm only if first
   prototype shows crosstalk problems.

4. **DRV5055A4 output swing at expected gap** — calculated ~50–100 mT
   for 3 mm × 2 mm N42 at 3 mm gap. A4 sensitivity is 12.5 mV/mT, so
   expected swing is 625–1250 mV off the 1.65 V midpoint — well above
   noise and well below the ±169 mT saturation limit. If actual gap is
   larger (wall + PCB + air > 5 mm), swing drops linearly with field
   (≈1/r³ for a dipole) and discrimination from baseline gets harder.
   Mitigation: budget the gap carefully in CAD; consider 5 mm × 2 mm
   N42 for presence if gap stretches. Do **not** swap to DRV5055A1/A2/A3
   without re-checking saturation — A1 (100 mV/mT, ±21 mT) would
   saturate at this gap.

   For GH1230KSW ID sensors: 3 mT operate / 2 mT release. At 50–100 mT
   field, margin is 15–30×. Same gap-stretch caveat applies but with
   far more headroom.

5. **Cube wall thickness, internal mounting space, PCB clearance** —
   not re-verified against current enclosure. Sensor board is ~34 × 22 mm;
   needs to fit inside the detecting face with room for the connector.
   Mitigation: measure existing PN5180 board footprint in the enclosure
   first; the new board should be smaller, but confirm before fab.

6. **Backwards-magnet at assembly is silent for the
   "both-flipped" case** — Mitigation: print a polarity diagram per
   cube; use a magnetic-viewing film during assembly to confirm pole
   orientation visually.

## Order checklist

Before sending to JLC:

- [ ] Datasheets pulled for GH1230KSW and SS341RT — confirm polarity
      conventions match LCSC's operate-point sign
- [ ] Confirm sensor PCB fits inside the detecting face of the current
      cube enclosure (measure or check CAD)
- [ ] Schematic capture: 6 ID sensors with 10 kΩ pull-ups, 1 linear
      Hall (DRV5055A4QDBZR) presence sensor with no pull-up, 100 nF
      decoupling on each, connector matching existing PN5180 pinout,
      separate presence pigtail
- [ ] Presence trace lands on GPIO 36 (ADC1_CH0) — already routed via
      the existing v6_with_hall tap point
- [ ] PCB layout: 2-layer, 1.6 mm, 12 mm pitch, M2 mounting holes,
      sensor side facing the cube wall
- [ ] Polarity-test breakout board on same panel (1 of each part type
      + breakout headers)
- [ ] Main board: **no changes required**. Existing v6 PCBs accept the
      new sensor daughterboard via the unmodified PN5180 connector,
      plus a flying wire from the new sensor board's presence output
      to the existing GPIO 36 tap point.
- [ ] Order:
      - 12× sensor PCBs assembled (BOM above)
      - 1× polarity test breakout assembled
      - 12× main PCBs (bare or assembled depending on cost)
      - 150× 3 mm × 2 mm N42 axial magnets
      - 60× 3 mm × 1 mm N42 axial magnets (alignment, optional)
      - 60× M3 steel washers (alignment receivers)

## Open questions to resolve before ordering

- Datasheet confirmation of GH1230KSW polarity convention (LCSC lists
  "unipolar" with 3 mT operate / 2 mT release; confirm south-pole-detect
  is the convention vs north-pole-detect — flip magnet polarity
  globally if wrong, no PCB change needed)
- DRV5055A4 datasheet sign convention for north vs south fields (firmware
  threshold direction is a one-line fix)
- SS341RT pin order vs DRV5055A4 — only matters if you want the
  dual-footprint capability; otherwise commit to DRV5055A4 pinout
- Cube enclosure measurements vs sensor board footprint (34 × 22 mm)
- Whether to include alignment magnets at this stage or defer to v2 of
  the enclosure
- Per-cube assembly plan: jig design for repeatable magnet placement
  and polarity orientation
