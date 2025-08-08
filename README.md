
## Temp Workaround
Due to the decomissioning of Efergy (https://github.com/home-assistant/core/issues/149908) this has been created as a temp workaround.

<img width="1544" height="1025" alt="image" src="https://github.com/user-attachments/assets/ba1630f7-0c96-4f98-b18f-9876eda53e80" />


## Setup

To get an app token:

1. Manually download the files and copy them to \custom_components\efergy then restart Home Assistant.
2. (Optional) remove your current Efergy integration.
3. Go to Integrations > Add > Efergy (Custom) > Add API Key.

## Integration entities

The following sensors will be created:

- **Power Usage**: Shows the aggregate instant value of power consumption. An entity will also be created for each sensor attached to the household. If only one sensor is detected, it will be disabled by default.
- **Total Energy Consumption**: Shows the total energy consumption. (This was added for Energy Dashboard monitoring)
