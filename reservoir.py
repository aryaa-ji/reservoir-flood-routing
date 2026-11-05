# ============================================================
#  RESERVOIR & FLOOD ROUTING - simple dam design calculation
#  Author: Arya Aji
#
#  Step 1: Storage curve      - how much water the valley holds
#  Step 2: Storage zones      - space for sediment + drinking water
#  Step 3: Flood routing      - what happens during a big flood
#  Step 4: Dam height         - how tall the dam must be
#
#  Run:  python reservoir.py
# ============================================================

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

os.makedirs("outputs", exist_ok=True)   # create the outputs folder if it is missing


# ------------------------------------------------------------
# INPUT VALUES  (example data - change them and run again)
# ------------------------------------------------------------
sediment_per_year = 15000      # m³ of sediment per year
design_life = 100              # years

population = 120000            # people supplied
demand_per_person = 150        # litres per person per day
ecological_flow = 0.15         # m³/s always released to the river

spillway_length = 15           # m
spillway_C = 2.1               # weir coefficient

flood_peak = 350               # m³/s
time_to_peak = 8               # hours
base_flow = 5                  # m³/s

freeboard = 1.5                # m safety margin


# ------------------------------------------------------------
# STEP 1: STORAGE CURVE
# Volume between two levels = average area x height difference
# ------------------------------------------------------------
data = pd.read_csv("elevation_area.csv")
levels = data["elevation_m"].values
areas = data["area_km2"].values * 1_000_000          # km² -> m²

volumes = [0]
for i in range(1, len(levels)):
    slice_volume = (areas[i - 1] + areas[i]) / 2 * (levels[i] - levels[i - 1])
    volumes.append(volumes[-1] + slice_volume)
volumes = np.array(volumes)

# helper functions: read level from volume and volume from level
def volume_at(level):
    return np.interp(level, levels, volumes)

def level_at(volume):
    return np.interp(volume, volumes, levels)


# ------------------------------------------------------------
# STEP 2: STORAGE ZONES
# ------------------------------------------------------------
dead_storage = sediment_per_year * design_life                      # m³

drinking_water = population * demand_per_person / 1000 * 365        # m³ per year
eco_water = ecological_flow * 365 * 24 * 3600                       # m³ per year
active_storage = drinking_water + eco_water                         # m³

dead_level = level_at(dead_storage)
normal_level = level_at(dead_storage + active_storage)   # = spillway crest


# ------------------------------------------------------------
# STEP 3: FLOOD ROUTING
# Water in - water out = change in storage   (every 15 minutes)
# Spillway:  Q = C * L * H^1.5
# Reservoir is FULL when the flood starts (worst case, DIN 19700)
# ------------------------------------------------------------
dt = 15 * 60                                   # time step: 15 min in seconds
time = np.arange(0, 48.25, 0.25)               # 0 to 48 hours

# design flood (smooth single peak)
inflow = base_flow + (flood_peak - base_flow) * (time / time_to_peak * np.exp(1 - time / time_to_peak)) ** 3

storage = volume_at(normal_level)
outflow = []
water_level = []

for Q_in in inflow:
    level = level_at(storage)
    head = max(level - normal_level, 0)                 # water above spillway crest
    Q_out = spillway_C * spillway_length * head ** 1.5   # spillway discharge

    storage = storage + (Q_in - Q_out) * dt             # update stored water

    outflow.append(Q_out)
    water_level.append(level)

outflow = np.array(outflow)
water_level = np.array(water_level)


# ------------------------------------------------------------
# STEP 4: DAM HEIGHT
# ------------------------------------------------------------
max_level = water_level.max()
dam_crest = max_level + freeboard
dam_height = dam_crest - levels[0]

peak_in = inflow.max()
peak_out = outflow.max()
reduction = (1 - peak_out / peak_in) * 100
delay = time[outflow.argmax()] - time[inflow.argmax()]


# ------------------------------------------------------------
# RESULTS
# ------------------------------------------------------------
results = pd.DataFrame({
    "Parameter": ["Dead storage", "Dead storage level", "Active storage",
                  "Normal level (spillway crest)", "Peak inflow", "Peak outflow",
                  "Peak reduction", "Peak delay", "Max. flood level",
                  "Dam crest level", "Dam height"],
    "Value": [dead_storage / 1e6, dead_level, active_storage / 1e6,
              normal_level, peak_in, peak_out,
              reduction, delay, max_level,
              dam_crest, dam_height],
    "Unit": ["million m³", "m", "million m³", "m", "m³/s", "m³/s",
             "%", "h", "m", "m", "m"],
})
results["Value"] = results["Value"].round(2)
print(results.to_string(index=False))
results.to_csv("outputs/results.csv", index=False)


# ------------------------------------------------------------
# CHARTS
# ------------------------------------------------------------
# Chart 1: flood routing
plt.figure(figsize=(8, 5))
plt.plot(time, inflow, label="Inflow (flood)", linewidth=2)
plt.plot(time, outflow, label="Outflow (spillway)", linewidth=2)
plt.title(f"Flood routing - peak reduced by {reduction:.0f} %")
plt.xlabel("Time [h]")
plt.ylabel("Discharge [m³/s]")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("outputs/flood_routing.png", dpi=150)

# Chart 2: storage curve with important levels
plt.figure(figsize=(8, 5))
plt.plot(volumes / 1e6, levels, color="black", linewidth=2, label="Storage curve")
plt.axhline(dam_crest, color="grey", linestyle="--", label=f"Dam crest {dam_crest:.1f} m")
plt.axhline(max_level, color="red", linestyle="--", label=f"Max. flood level {max_level:.1f} m")
plt.axhline(normal_level, color="blue", linestyle="--", label=f"Normal level {normal_level:.1f} m")
plt.axhline(dead_level, color="brown", linestyle="--", label=f"Dead storage level {dead_level:.1f} m")
plt.title("Storage curve and reservoir levels")
plt.xlabel("Storage volume [million m³]")
plt.ylabel("Water level [m]")
plt.legend(loc="lower right")
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("outputs/storage_curve.png", dpi=150)

print("\nCharts saved in the outputs folder.")
