# paolo-core, the server

paolo-core is the home server Maple lives on. It runs a metrics collector every few minutes, a nightly backup, and Maple itself. Grafana and Lycan Watch exist too, but Maple cannot see them directly, so their state is honestly unknown to Maple.

## What Maple watches

Maple reads factual observations: processor, memory, and disk use, load, temperature, and whether the services it is allowed to see are running. When something is seriously wrong, such as a failed service or a nearly full disk, Maple drops what it is doing to look.
