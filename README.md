# 🍌 NSE VCP Pattern Screener

An autonomous quantitative technical screener and Volatility Contraction Pattern (VCP) engine for Indian Equities (NSE), reverse-engineered from [BananaPatterns](https://bananapatterns.com/screens) and powered **100% by free daily National Stock Exchange (NSE) Bhavcopy data**.

---

## 🌟 Key Features

- **₹0 Data Cost**: Uses official daily NSE Bhavcopy archives (`sec_bhavdata_full_*.csv` and `ind_close_all_*.csv`). No paid API subscriptions needed.
- **4-Stage Lifecycle State Machine**:
  1. **Forming (`watch`)**: Leaders pausing and coiling tighter under their pivot ceiling.
  2. **Fresh Breakouts (`trig`)**: Stocks that cleared resistance within the last 5 sessions on heavy volume ($\ge 1.5\times$ 20-day median).
  3. **Climbing (`hold`)**: Established breakouts trending upward while holding above trailing stop-loss and 50-DMA.
  4. **Played Out (`exit`)**: Completed setups closed out by rule (hit −8% stop loss or closed below 50-DMA).
- **Core Quantitative Dials**:
  - **`coil` (Volatility Contraction)**: Ratio of 2nd-half ATR% to 1st-half ATR% inside the base ($< 1.0 = \text{tightening}$).
  - **`dry` (Volume Dry-Up)**: Ratio of 2nd-half volume to 1st-half volume ($< 1.0 = \text{exhausted supply}$).
  - **`rs` (Relative Strength)**: 1–99 percentile ranking across the entire liquid Indian market benchmarked against Nifty 500.
  - **`squats` & `pokes`**: Quantifies intraday false breakouts and failed tests at the pivot.
  - **`ext` (Distance from Pivot)**: Current price percentage relative to resistance ceiling.
- **Pre-Configured Screens**:
  - `VCP`: Volatility Contraction Pattern (Mark Minervini / O'Neil style).
  - `Blue Sky`: Level 1 bases forming directly at All-Time Highs with zero overhead supply.
  - `Multi-Year Breakouts`: 1+ year accumulation bases releasing upward.
  - `IPO Base`: Young leaders (listed $< 1$ year) forming their first institutional base.
  - `Custom Dials`: Full interactive sliders for custom criteria.
- **Interactive Web Dashboard**:
  - Dark-mode responsive UI matching the BananaPatterns design language.
  - HTML5 Canvas candlestick charts with pivot resistance lines, moving averages, and volume dry-up histograms.
  - BananaPatterns-compatible JSON REST API (`POST /api/screen`).

---

## 📐 Mathematical Formulation

### 1. Volatility Contraction (`coil`)
Divides the consolidation base duration into two equal chronological halves:
$$\text{coil} = \frac{\overline{\text{ATR\%}}_{\text{2nd half}}}{\overline{\text{ATR\%}}_{\text{1st half}}}$$
When $\text{coil} < 1.0$, volatility is tightening. A value between $0.3\times$ and $0.9\times$ identifies classic coiled springs.

### 2. Volume Dry-Up (`dry`)
$$\text{dry} = \frac{\overline{\text{Volume}}_{\text{2nd half}}}{\overline{\text{Volume}}_{\text{1st half}}}$$
When $\text{dry} < 1.0$, institutional selling pressure has evaporated inside the base.

### 3. Extension vs. Pivot (`ext`)
$$\text{ext} = \left(\frac{\text{Price}_{\text{close}}}{\text{Price}_{\text{pivot}}} - 1\right) \times 100$$
- $\text{ext} < 0\% \implies$ Still forming under the ceiling.
- $\text{ext} \ge 0\% \implies$ Clearing or extended past pivot.

### 4. Relative Strength Rating (`rs`, 1–99)
Calculates rolling price returns across 4 quarters ($Q_1, Q_2, Q_3, Q_4$):
$$\text{Score} = 0.4 \times R_{3M} + 0.2 \times R_{6M} + 0.2 \times R_{9M} + 0.2 \times R_{12M}$$
The entire liquid universe is then mapped to percentile ranks $\text{RS} \in [1, 99]$.

---

## 🚀 Quick Start

### 1. Installation
```bash
git clone https://github.com/Sathya06272006/nse-vcp-screener.git
cd nse-vcp-screener
pip install -r requirements.txt
```

### 2. Run the Screener & Web Server
```bash
python run.py
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## 📡 REST API Reference

### `POST /api/screen`
Evaluates screens and partitions stocks into the 4 stages.

**Request Body:**
```json
{
  "sel": "h:VCP",
  "spec": {
    "rs": [70, 99],
    "coil": [0.3, 0.9],
    "dry": [0.05, 0.9],
    "baseWk": [3, 300],
    "baseDepth": [2, 35],
    "vs50": [0, 200]
  }
}
```

**Response (`200 OK`):**
```json
{
  "ok": true,
  "sel": "h:VCP",
  "counts": [12, 3, 18, 45],
  "stages": {
    "p-k-watch": { "total": 12, "rows": [...] },
    "p-k-trig":  { "total": 3,  "rows": [...] },
    "p-k-hold":  { "total": 18, "rows": [...] },
    "p-k-exit":  { "total": 45, "rows": [...] }
  }
}
```

---

## 🛠️ Data Sources
- **Equities Master**: `https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv`
- **Daily Bhavcopy**: `https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv`
- **Indices Bhavcopy**: `https://nsearchives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv`

---

## ⚖️ Disclaimer
This software is for educational, research, and technical pattern study purposes only. It is not investment advice or SEBI-registered advisory. Always manage risk first.
