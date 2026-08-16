# Arduino CLI — MESFlow ESP Kiosk

From workspace root:

```bash
cd esp-kiosk
./scripts/setup-arduino.sh
./scripts/detect-board.sh
./scripts/list-includes.sh
./scripts/build.sh
```

Flash requires an explicit serial port:

```bash
./scripts/flash.sh /dev/ttyACM0
```

Monitor:

```bash
./scripts/monitor.sh /dev/ttyACM0
```

Configuration:

```text
esp-kiosk/.mesflow-arduino.env
```

Default FQBN is only a starting value:

```text
esp32:esp32:esp32s3
```

Verify the actual board/options before flashing. Do not guess partition settings.
