# Roadmap and open questions

## Dense cells hit the ~120 results cap

A Maps list stops at about 120 cards. In the Milan run (17 Nov 2026) `park`,
`church` and `garden` reached it in 48–49 cells out of 49 while still finding
many new places per cell, so those categories are probably under-covered.
`viewpoint`, `zoo` and `amusement_park` also hit 120, but with almost no new
places: there the list is padded with already-known places and nothing is lost.

Idea: split a cell into 4 sub-cells when `cards >= 118` **and** `new >= 5`.
On Milan that is 216 cells → 864 extra searches (~7 h). Measure first on 2–3
dense `park` cells.

## Filtering non-sights

`park` searches also return parking lots ("Parking lot", "Free parking lot",
"Parking garage"). Filter them on `category` after scraping, not during, so the
raw data stays complete.

## Resume a stopped run

Today a stopped run restarts from zero. A resume option could read the partial
file and skip the (category, cell) pairs already done.
