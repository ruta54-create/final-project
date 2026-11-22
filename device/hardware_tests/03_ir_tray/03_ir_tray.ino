/*
 * TEST 03 - IR obstacle sensor FC-51 on the tray (main ESP32 DevKit)
 * Wiring: VCC -> 3V3 (NOT 5V: its output then stays 3.3V-safe), GND -> GND, OUT -> GPIO34
 * Expected: "ITEM ON TRAY" when you put an object 2-10 cm in front of the sensor, "empty" otherwise.
 * Turn the small blue potentiometer on the module to set the detection distance.
 */
const int IR_TRAY = 34;   // input-only pin; the module has its own pull-up resistor

void setup() {
  Serial.begin(115200);
  pinMode(IR_TRAY, INPUT);
  Serial.println("TEST 03: IR tray sensor");
}

void loop() {
  Serial.println(digitalRead(IR_TRAY) == LOW ? "ITEM ON TRAY" : "empty");
  delay(300);
}
