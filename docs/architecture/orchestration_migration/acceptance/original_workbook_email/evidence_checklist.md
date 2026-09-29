# Phase 1 — independent evidence checklist (derived from the materialized workbook copy)

Rows scanned: **25251** across **46** sheets.

Source: the indexed materialized copy of `Consolidated Price List 2019.xlsx`
(`sheet_datasets/default/ff2597d26fc6/`, content hash `ff2597d26fc6d0ea216c0fd9b933090dc64e3348`).
Derived by `phase1_evidence.py` from the parquet rows themselves — NOT from any earlier report
and NOT from the app's answer. Every value below is what the file actually holds.

Legend: `blank` = the cell is empty; `zero` = the cell holds 0; `nan` = a non-numeric value.
These are three different things and are never merged.


## No. 381

**Identity: AMBIGUOUS** → 7 candidate rows: `gmpump!501, roperwhitney!88, roperwhitney!89, servo!343, servo!406, tennsmith!338, tennsmith!340`


- `gmpump!501` — identity cell `G501` (column `c7`) = `381`

- `roperwhitney!88` — identity cell `A88` (column `MODEL NO.`) = `381`
  - money columns (header verbatim):
    - `P88` **U.S. COST** = <zero> `zero`
    - `Q88` **CANADIAN AT FACTORY** = <zero> `zero`
    - `R88` **CANADIAN COST INCL. MISC** = <zero> `zero`
    - `S88` **ELECTRICAL COSTS** = <nan> `nan`
    - `U88` **FREIGHT BY WEIGHT** = 166.6 `number`
    - `V88` **FREIGHT BY %** = <nan> `nan`
    - `W88` **FLAT FREIGHT RATE** = <nan> `nan`
    - `X88` **FULL COST CDN** = 166.6 `number`
    - `Y88` **CDN NET MULT** = 31 `number`
    - `AA88` **CDN NET** = 189.32 `number`
    - `AB88` **CDN LIST MULT** = 35 `number`
    - `AD88` **CDN LIST** = 236.66 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `O88` WEIGHT=245, `T88` WEIGHT_2=245, `Z88` c26=1.14, `AC88` c29=1.25, `AJ88` 35=<nan>

- `roperwhitney!89` — identity cell `D89` (column `DESCRIPTION`) = `NO. 381 HVY DUTY WELDED FLOOR MOUNT STAND`
  - money columns (header verbatim):
    - `P89` **U.S. COST** = <zero> `zero`
    - `Q89` **CANADIAN AT FACTORY** = <zero> `zero`
    - `R89` **CANADIAN COST INCL. MISC** = <zero> `zero`
    - `S89` **ELECTRICAL COSTS** = <nan> `nan`
    - `U89` **FREIGHT BY WEIGHT** = 108.8 `number`
    - `V89` **FREIGHT BY %** = <nan> `nan`
    - `W89` **FLAT FREIGHT RATE** = <nan> `nan`
    - `X89` **FULL COST CDN** = 108.8 `number`
    - `Y89` **CDN NET MULT** = 32 `number`
    - `AA89` **CDN NET** = 136 `number`
    - `AB89` **CDN LIST MULT** = 35 `number`
    - `AD89` **CDN LIST** = 170 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `O89` WEIGHT=160, `T89` WEIGHT_2=160, `Z89` c26=1.25, `AC89` c29=1.25, `AJ89` 35=<nan>

- `servo!343` — identity cell `D343` (column `c4`) = `381`
  - other numeric columns (NOT price-like, do not quote as a price): `T343` 0.65=<nan>

- `servo!406` — identity cell `D406` (column `c4`) = `381`
  - other numeric columns (NOT price-like, do not quote as a price): `T406` 0.65=<nan>

- `tennsmith!338` — identity cell `A338` (column `MODEL NO.`) = `381`
  - money columns (header verbatim):
    - `M338` **U.S. LIST** = 1,845 `number`
    - `O338` **U.S. COST** = 1,476 `number`
    - `P338` **CANADIAN AT FACTORY** = 2,110.68 `number`
    - `Q338` **CDN INCL. MISC** = 2,152.89 `number`
    - `R338` **QPS** = <nan> `nan`
    - `T338` **FREIGHT BY WEIGHT** = 137.5 `number`
    - `U338` **FREIGHT BY %** = <nan> `nan`
    - `V338` **FLAT FREIGHT RATE** = <nan> `nan`
    - `W338` **FULL COST CDN** = 2,290.39 `number`
    - `Y338` **CDN NET** = 2,602.8 `number`
    - `AA338` **CDN LIST** = 3,253.5 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `J338` WEIGHT (LBS)=275, `S338` WEIGHT=275, `X338` c24=1.14, `Z338` c26=1.25, `AF338` 0.75=<nan>, `AG338` 30=<nan>

- `tennsmith!340` — identity cell `D340` (column `DESCRIPTION`) = `No. 381 Heavy Duty Welded Floor`
  - money columns (header verbatim):
    - `M340` **U.S. LIST** = 495 `number`
    - `O340` **U.S. COST** = 396 `number`
    - `P340` **CANADIAN AT FACTORY** = 566.28 `number`
    - `Q340` **CDN INCL. MISC** = 577.61 `number`
    - `R340` **QPS** = <nan> `nan`
    - `T340` **FREIGHT BY WEIGHT** = 60 `number`
    - `U340` **FREIGHT BY %** = <nan> `nan`
    - `V340` **FLAT FREIGHT RATE** = <nan> `nan`
    - `W340` **FULL COST CDN** = 637.61 `number`
    - `Y340` **CDN NET** = 724.58 `number`
    - `AA340` **CDN LIST** = 905.72 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `J340` WEIGHT (LBS)=120, `S340` WEIGHT=120, `X340` c24=1.14, `Z340` c26=1.25, `AF340` 0.75=<nan>, `AG340` 30=<nan>

## U-22

**Identity: resolved** → `linmac!26`


- `linmac!26` — identity cell `A26` (column `Part Number`) = `U-22`
  - money columns (header verbatim):
    - `C26` **List Price** = 1,777 `number`
    - `E26` **US NET** = 680 `number`
    - `G26` **QPS** = <nan> `nan`
    - `H26` **Freight** = 135 `number`
    - `I26` **Landed** = 1,107.4 `number`
    - `M26` **List Price_2** = 1,777 `number`
    - `N26` **Profit** = 669.6 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `D26` Weight=<nan>, `F26` Exch=972.4, `J26` Warehouse=1,165.68, `K26` Brenn=1,421.57, `L26` Dealer=1,776.96

- **Unresolved near-misses** (20 shown of the rows sharing tokens):
  - `_40_tooling!119` cell `E119` (col `c5`) = `22.8MM` — shares ['22']
  - `burrking!4` cell `K4` (col `c11`) = `U.S. Cost` — shares ['u']
  - `burrking!29` cell `AA29` (col `MULT#1`) = `MULT#22` — shares ['22']
  - `burrking!396` cell `Q396` (col `c17`) = `22.034819664` — shares ['22']
  - `burrking!419` cell `K419` (col `c11`) = `22.989599999999999` — shares ['22']
  - `burrking!518` cell `Q518` (col `c17`) = `22.076178696000003` — shares ['22']
  - `burrking!535` cell `S535` (col `c19`) = `22.968049104000002` — shares ['22']
  - `burrking!550` cell `M550` (col `c13`) = `22.068755279999994` — shares ['22']

## No. 622

**Identity: AMBIGUOUS** → 4 candidate rows: `roperwhitney!266, roperwhitney!268, roperwhitney!279, roperwhitney!293`


- `roperwhitney!266` — identity cell `A266` (column `MODEL NO.`) = `622`
  - money columns (header verbatim):
    - `P266` **U.S. COST** = <zero> `zero`
    - `Q266` **CANADIAN AT FACTORY** = <zero> `zero`
    - `R266` **CANADIAN COST INCL. MISC** = <zero> `zero`
    - `S266` **ELECTRICAL COSTS** = <nan> `nan`
    - `U266` **FREIGHT BY WEIGHT** = <zero> `zero`
    - `V266` **FREIGHT BY %** = <nan> `nan`
    - `W266` **FLAT FREIGHT RATE** = <nan> `nan`
    - `X266` **FULL COST CDN** = <zero> `zero`
    - `Y266` **CDN NET MULT** = 32 `number`
    - `AA266` **CDN NET** = <zero> `zero`
    - `AB266` **CDN LIST MULT** = 35 `number`
    - `AD266` **CDN LIST** = <zero> `zero`
  - other numeric columns (NOT price-like, do not quote as a price): `O266` WEIGHT=50, `T266` WEIGHT_2=50, `Z266` c26=1.25, `AC266` c29=1.25, `AJ266` 35=<nan>

- `roperwhitney!268` — identity cell `A268` (column `MODEL NO.`) = `622`
  - money columns (header verbatim):
    - `P268` **U.S. COST** = 1,012.5 `number`
    - `Q268` **CANADIAN AT FACTORY** = 1,447.88 `number`
    - `R268` **CANADIAN COST INCL. MISC** = 1,447.88 `number`
    - `S268` **ELECTRICAL COSTS** = <nan> `nan`
    - `U268` **FREIGHT BY WEIGHT** = 101.35 `number`
    - `V268` **FREIGHT BY %** = <nan> `nan`
    - `W268` **FLAT FREIGHT RATE** = <nan> `nan`
    - `X268` **FULL COST CDN** = 1,549.23 `number`
    - `Y268` **CDN NET MULT** = 32 `number`
    - `AA268` **CDN NET** = 1,936.53 `number`
    - `AB268` **CDN LIST MULT** = 35 `number`
    - `AD268` **CDN LIST** = 2,420.67 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `O268` WEIGHT=50, `T268` WEIGHT_2=50, `Z268` c26=1.25, `AC268` c29=1.25, `AJ268` 35=<nan>

- `roperwhitney!279` — identity cell `A279` (column `MODEL NO.`) = `622 &`
  - money columns (header verbatim):
    - `P279` **U.S. COST** = 56 `number`
    - `Q279` **CANADIAN AT FACTORY** = 80.08 `number`
    - `R279` **CANADIAN COST INCL. MISC** = 80.08 `number`
    - `S279` **ELECTRICAL COSTS** = <nan> `nan`
    - `U279` **FREIGHT BY WEIGHT** = <nan> `nan`
    - `V279` **FREIGHT BY %** = 5.61 `number`
    - `W279` **FLAT FREIGHT RATE** = 10 `number`
    - `X279` **FULL COST CDN** = 95.69 `number`
    - `Y279` **CDN NET MULT** = 32 `number`
    - `AA279` **CDN NET** = 119.61 `number`
    - `AB279` **CDN LIST MULT** = 35 `number`
    - `AD279` **CDN LIST** = 149.51 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `O279` WEIGHT=<nan>, `T279` WEIGHT_2=<nan>, `Z279` c26=1.25, `AC279` c29=1.25, `AJ279` 35=<nan>

- `roperwhitney!293` — identity cell `A293` (column `MODEL NO.`) = `622`
  - money columns (header verbatim):
    - `P293` **U.S. COST** = 136 `number`
    - `Q293` **CANADIAN AT FACTORY** = 194.48 `number`
    - `R293` **CANADIAN COST INCL. MISC** = 194.48 `number`
    - `S293` **ELECTRICAL COSTS** = <nan> `nan`
    - `U293` **FREIGHT BY WEIGHT** = <nan> `nan`
    - `V293` **FREIGHT BY %** = 13.61 `number`
    - `W293` **FLAT FREIGHT RATE** = 10 `number`
    - `X293` **FULL COST CDN** = 218.09 `number`
    - `Y293` **CDN NET MULT** = 32 `number`
    - `AA293` **CDN NET** = 272.62 `number`
    - `AB293` **CDN LIST MULT** = 35 `number`
    - `AD293` **CDN LIST** = 340.77 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `O293` WEIGHT=<nan>, `T293` WEIGHT_2=<nan>, `Z293` c26=1.25, `AC293` c29=1.25, `AJ293` 35=<nan>

## TK Manual Flanger

**Identity: resolved** → `tinknocker!42`


- `tinknocker!42` — identity cell `A42` (column `c1`) = `TK Manual Flanger`
  - money columns (header verbatim):
    - `D42` **Price** = 1,609 `number`
    - `H42` **Factory Price** = 950 `number`
    - `I42` **Factory Discount** = 712.5 `number`
    - `J42` **Freight** = 812.5 `number`
    - `K42` **Exchange** = 1,161.88 `number`
    - `M42` **Brennan margin** = 1,366.91 `number`
    - `N42` **Dealer Margin** = 1,608.13 `number`
    - `O42` **Dealer Factor** = 1.69 `number`
    - `P42` **Brennan Factor** = 1.44 `number`
    - `R42` **Exchange Rate** = <nan> `nan`
    - `T42` **Brennan Margin** = <nan> `nan`
    - `U42` **Dealer Margin_2** = 0.28 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `L42` CSA=1,161.88

- **Unresolved near-misses** (20 shown of the rows sharing tokens):
  - `burrking!49` cell `A49` (col `BURR KING`) = `MODEL 720  -  MANUAL TENSION 2 X 72 BELT (C) ` — shares ['manual']
  - `circ_cold_saw!7` cell `B7` (col `c2`) = `30/60 RPM Manual` — shares ['manual']
  - `circ_cold_saw!8` cell `B8` (col `c2`) = `30/60 RPM Manual` — shares ['manual']
  - `circ_cold_saw!9` cell `B9` (col `c2`) = `30/60 RPM Manual` — shares ['manual']
  - `circ_cold_saw!10` cell `B10` (col `c2`) = `30/60 RPM Manual` — shares ['manual']
  - `circ_cold_saw!11` cell `B11` (col `c2`) = `60/120 Manual` — shares ['manual']
  - `circ_cold_saw!12` cell `B12` (col `c2`) = `60/120 Manual` — shares ['manual']
  - `circ_cold_saw!13` cell `B13` (col `c2`) = `60/120 Manual` — shares ['manual']

## SLE24-16

**Identity: resolved** → `tennsmith!101`


- `tennsmith!101` — identity cell `A101` (column `MODEL NO.`) = `SLE24-16`
  - money columns (header verbatim):
    - `M101` **U.S. LIST** = 4,500 `number`
    - `O101` **U.S. COST** = 3,600 `number`
    - `P101` **CANADIAN AT FACTORY** = 5,148 `number`
    - `Q101` **CDN INCL. MISC** = 5,250.96 `number`
    - `R101` **QPS** = 650 `number`
    - `T101` **FREIGHT BY WEIGHT** = <nan> `nan`
    - `U101` **FREIGHT BY %** = <nan> `nan`
    - `V101` **FLAT FREIGHT RATE** = 350 `number`
    - `W101` **FULL COST CDN** = 6,250.96 `number`
    - `Y101` **CDN NET** = 7,103.59 `number`
    - `AA101` **CDN LIST** = 8,879.49 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `J101` WEIGHT (LBS)=350, `S101` WEIGHT=<nan>, `X101` c24=1.14, `Z101` c26=1.25, `AF101` 0.75=<nan>, `AG101` 30=<nan>

- **Unresolved near-misses** (20 shown of the rows sharing tokens):
  - `_20_tooling!6` cell `R6` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']
  - `_20_tooling!7` cell `R7` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']
  - `_20_tooling!8` cell `A8` (col `#20 ROUND PUNCHES AND DIES – STOCKING SIZES`) = `3/16` — shares ['16']
  - `_20_tooling!8` cell `E8` (col `c5`) = `3/16` — shares ['16']
  - `_20_tooling!8` cell `R8` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']
  - `_20_tooling!9` cell `R9` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']
  - `_20_tooling!10` cell `R10` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']
  - `_20_tooling!11` cell `R11` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']

## TK 1624

**Identity: resolved** → `tinknocker!101`


- `tinknocker!101` — identity cell `A101` (column `c1`) = `TK 1624 Slitter`
  - money columns (header verbatim):
    - `D101` **Price** = 8,040 `number`
    - `H101` **Factory Price** = 3,950 `number`
    - `I101` **Factory Discount** = 2,962.5 `number`
    - `J101` **Freight** = 3,712.5 `number`
    - `K101` **Exchange** = 5,308.88 `number`
    - `M101` **Brennan margin** = 6,833.97 `number`
    - `N101` **Dealer Margin** = 8,039.97 `number`
    - `O101` **Dealer Factor** = 2.04 `number`
    - `P101` **Brennan Factor** = 1.73 `number`
    - `R101` **Exchange Rate** = <nan> `nan`
    - `T101` **Brennan Margin** = <nan> `nan`
    - `U101` **Dealer Margin_2** = 0.28 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `L101` CSA=5,808.88

- **Unresolved near-misses** (20 shown of the rows sharing tokens):
  - `ercolina!236` cell `I236` (col `c9`) = `1624` — shares ['1624']
  - `ercolina!277` cell `H277` (col `c8`) = `1624` — shares ['1624']
  - `ercolina!278` cell `H278` (col `c8`) = `1624` — shares ['1624']
  - `ercolina!279` cell `H279` (col `c8`) = `1624` — shares ['1624']
  - `ercolina!280` cell `H280` (col `c8`) = `1624` — shares ['1624']
  - `gmpump!15` cell `AD15` (col `c30`) = `1624.2491232999998` — shares ['1624']
  - `gmpump!374` cell `V374` (col `c22`) = `1624` — shares ['1624']
  - `linmac!44` cell `A44` (col `Part Number`) = `TK-2236` — shares ['tk']

## TK Multi Wheel Gang Slitter

**Identity: NOT FOUND** under exact/token matching — no row carries this name.


- **Unresolved near-misses** (20 shown of the rows sharing tokens):
  - `ams!59` cell `B59` (col `c2`) = `MULTI-LOC STANDARD LEFT HAND` — shares ['multi']
  - `ams!65` cell `B65` (col `c2`) = `MULTI-LOC STANDARD RIGHT HAND` — shares ['multi']
  - `ams!71` cell `B71` (col `c2`) = `STANDARD DUTY MULTI-LOC STOP BLOCKS ONLY` — shares ['multi']
  - `ams!76` cell `B76` (col `c2`) = `MULTI-LOC HEAVY DUTY LEFT HAND` — shares ['multi']
  - `ams!82` cell `B82` (col `c2`) = `MULTI-LOC HEAVY DUTY RIGHT HAND` — shares ['multi']
  - `ams!88` cell `B88` (col `c2`) = `HEAVY DUTY MULTI-LOC STOP BLOCKS ONLY` — shares ['multi']
  - `ams!95` cell `B95` (col `c2`) = `MULTI-LOC ACCESSORIES` — shares ['multi']
  - `burrking!40` cell `A40` (col `BURR KING`) = `8 inch Contact Wheel` — shares ['wheel']

## GSL48-16

**Identity: resolved** → `tennsmith!106`


- `tennsmith!106` — identity cell `A106` (column `MODEL NO.`) = `GSL48-16`
  - money columns (header verbatim):
    - `M106` **U.S. LIST** = 6,575 `number`
    - `O106` **U.S. COST** = 5,260 `number`
    - `P106` **CANADIAN AT FACTORY** = 7,521.8 `number`
    - `Q106` **CDN INCL. MISC** = 7,672.24 `number`
    - `R106` **QPS** = 1,500 `number`
    - `T106` **FREIGHT BY WEIGHT** = <nan> `nan`
    - `U106` **FREIGHT BY %** = <nan> `nan`
    - `V106` **FLAT FREIGHT RATE** = 800 `number`
    - `W106` **FULL COST CDN** = 9,972.24 `number`
    - `Y106` **CDN NET** = 11,332.45 `number`
    - `AA106` **CDN LIST** = 14,165.56 `number`
  - other numeric columns (NOT price-like, do not quote as a price): `J106` WEIGHT (LBS)=545, `S106` WEIGHT=<nan>, `X106` c24=1.14, `Z106` c26=1.25, `AF106` 0.75=<nan>, `AG106` 30=<nan>

- **Unresolved near-misses** (20 shown of the rows sharing tokens):
  - `_20_tooling!6` cell `R6` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']
  - `_20_tooling!7` cell `R7` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']
  - `_20_tooling!8` cell `A8` (col `#20 ROUND PUNCHES AND DIES – STOCKING SIZES`) = `3/16` — shares ['16']
  - `_20_tooling!8` cell `E8` (col `c5`) = `3/16` — shares ['16']
  - `_20_tooling!8` cell `R8` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']
  - `_20_tooling!9` cell `R9` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']
  - `_20_tooling!10` cell `R10` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']
  - `_20_tooling!11` cell `R11` (col `CANADA COST US $$$$_2`) = `16.2` — shares ['16']

## Distractors (must NOT join the active eight)

- `GSL24-16` → 0 match(es)
- `SLE16-8` → 0 match(es)
- `U-38` → 0 match(es)
- `Manual Flanger` → 1 match(es): `tinknocker!A42`=TK Manual Flanger
- `1624` → 6 match(es): `ercolina!I236`=1624, `ercolina!H277`=1624, `ercolina!H278`=1624, `ercolina!H279`=1624, `ercolina!H280`=1624
- `Multi Wheel Gang Slitter` → 0 match(es)

`GSL24-16`, `SLE16-8` and `U-38` have **no** row in this workbook copy — they are not
substitutes for anything in the active eight.

