# Intervals.icu Workout Samples

## Bike Workouts

Bike workouts are commonly expressed in time and FTP percentage and/or zones.

Examples of time: 1m30s, 1h30m, 90m, 135s, 2h, 3h, etc.

### Race Prep Activation Workout

Expressed in percentage of threshold power (FTP):

```
# Race Prep Activation Workout

- 5m 50-55%
- 5m ramp 55-65%

3x
- 3m ramp 65-90%
- 2m 55%

- 10m ramp 65-55%
```

Alternative Version (TT Focus) but expressed in Power Zones:

```
# Race Prep Activation Workout

- 5m z1
- 5m ramp z1-z2

4x
- 1m30s z5
- 1m30s z1

- 10m ramp z2-z1
```

### Opener Workout (Day Before Race)

Expressed in Power Zones:

```
# Opener Workout (Day Before Race)

- 10m z1-z2

3x
- 1m z4
- 2m z1

3x
- 15s z6
- 45s z1

- 10m z1
```

### Sweet Spot Maintenance (Early Taper)

A mix of Power Zones and percentage of threshold power (FTP):

```
# Sweet Spot Maintenance (Early Taper)

- 15m z1-z2

2x
- 2m 90%
- 2m 65%

2x
- 12m 88-92%
- 4m 65%

- 12m z1-z2
```

### Power Touch Activation

Another example:

```
# Power Touch Activation

- 8m z1
- 4m ramp z1-z3

5x
- 45s 95%
- 2m15s 65%

3x
- 20s 110%
- 1m40s 65%

- 8m z1
```

## Run Workouts

Like bike workouts, run workouts are commonly expressed in time, but can also be expressed in distance (km). And instead of power, run workouts can be expressed in threshold pace percentage and/or zones.

### Sprint Run Workout

A sprint run workout expressed in percentage of threshold pace:

```
# Sprint Run Workout

- 15m 82-92% Pace

8x
- 10s 160-185% Pace
- 3m z2 Pace

- 10m 82-92% Pace
```

### Sprint Run Workout

A similar sprint run workout expressed in Pace Zones:

```
# Sprint Run Workout

- 15m z2-z3 Pace

8x
- 10s z7 Pace
- 3m z2 Pace

- 10m z2-z3 Pace

> Notes: Aerobic base with neuromuscular power development
```

## Swim Workouts

### Swim Workout

A swim workouts are commonly expressed in distance (km) and in percentage of threshold pace and/or zones.

Distances are commonly expressed in kilometers and usually in portions of 0.025km (25m, the size of most pools)

```
# Swim Workout

- 0.025km 82-86% Pace Warmup

10x
- 0.1kms 95% Pace Work
- 0.0km 0% Pace Rest

- 0.025km 82-86% Pace Cooldown
```

### Swim Workout

Another swim workout expressed in Pace Zones:

```
# Swim Workout

- 1km z2-z3 Pace Warmup

8x
- 0.1km z7 Pace Work
- 0.0km 0% Pace Rest

- 1km z2-z3 Pace Cooldown

> Notes: Aerobic base with neuromuscular power development
```

In the two cases above "Warmup", "Work", "Rest", and "Cooldown" are examples of how you can add comments to each subsctructure of the workout.
