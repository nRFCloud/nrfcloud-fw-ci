# Assorted scripts and FW images to initialize CI devices

Note: The old Thingy:91 needs a manual FW upgrade to be performed on the connectivity bridge.
To do this, set the SWD selector to nrf52, connect a jlink and use the following command:

```bash
nrfutil device program --firmware t91-connbr-ncs3.2.hex --family nrf52 --traits jlink && nrfutil device reset --traits jlink
```

In case of UART problems, the connectivity bridge on the Thingy:91 X can be updated headless using MCUBoot and the built-in support for triggering bootloader mode.