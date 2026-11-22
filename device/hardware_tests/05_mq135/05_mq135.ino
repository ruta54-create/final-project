/*
 * TEST 05 - MQ-135 gas sensor + R0 calibration (main ESP32 DevKit)
 * Wiring: VCC -> 5V (the heater needs 5V), GND -> GND,
 *         AO -> 10k resistor -> GPIO35, and GPIO35 -> 20k resistor -> GND   (5V -> 3.3V max)
 * Expected: values every 2 s. The sensor must heat for ~2 minutes (24 h the very first time).
 * Calibration: in clean outdoor air, wait until "R0 estimate" is stable and copy it into
 * MQ_R0_KOHM in device/esp32_main/esp32_main.ino.
 */
const int MQ135_PIN = 35;            // ADC1: still works while Wi-Fi is on (ADC2 does not)
const float MQ_RL_KOHM = 10.0;       // load resistor on the module (most modules: 10k, some: 1k)
const float ADC_DIVIDER = 1.5;       // 10k + 20k divider: Vsensor = Vadc * 30/20
const float CLEAN_AIR_RATIO = 3.6;   // Rs/R0 in clean air (MQ-135 datasheet)

void setup() {
  Serial.begin(115200);
  analogSetPinAttenuation(MQ135_PIN, ADC_11db);   // measure up to ~3.1 V
  Serial.println("TEST 05: MQ-135 (wait 2 minutes for the heater)");
}

void loop() {
  float vAdc = analogReadMilliVolts(MQ135_PIN) / 1000.0f;
  float vSensor = vAdc * ADC_DIVIDER;
  if (vSensor < 0.05f) {
    Serial.println("0 V: check AO wire, divider and 5V on VCC");
  } else {
    float rs = (5.0f - vSensor) / vSensor * MQ_RL_KOHM;
    Serial.printf("pin %.2f V  sensor %.2f V  Rs %.1f kOhm  R0 estimate %.1f kOhm\n",
                  vAdc, vSensor, rs, rs / CLEAN_AIR_RATIO);
  }
  delay(2000);
}
