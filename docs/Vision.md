# Climate Flow Vision

Climate Flow is a Home Assistant integration for running ordered climate
control flows.

A flow contains stages. Each stage applies a climate state and may remain
active until a completion condition is satisfied.

Possible completion conditions include:

- A duration
- A local clock time
- A measured temperature threshold

Example:

1. Set cooling to 20°C until the room reaches 26°C.
2. Set cooling to 26°C until 07:00.
3. Turn the climate device off.

This document describes the current direction, not a permanent public API.
The design may change as the project develops.