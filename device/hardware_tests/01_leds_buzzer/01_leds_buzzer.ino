/*
 * TEST 01 - LEDs + buzzer (main ESP32 DevKit)
 * Wiring: GPIO26 -> 220R -> green LED -> GND
 *         GPIO33 -> 220R -> red LED   -> GND
 *         GPIO32 -> 220R -> blue LED  -> GND
 *         GPIO25 -> buzzer (+), buzzer (-) -> GND
 * Expected: green, red, blue light one after the other, then one beep. Repeats.
 */
const int LED_GREEN = 26, LED_RED = 33, LED_BLUE = 32, BUZZER = 25;

void setup() {
  Serial.begin(115200);
  pinMode(LED_GREEN, OUTPUT); pinMode(LED_RED, OUTPUT); pinMode(LED_BLUE, OUTPUT); pinMode(BUZZER, OUTPUT);
  Serial.println("TEST 01: LEDs + buzzer");
}

void flash(int pin, const char* name) {
  Serial.printf("%s ON\n", name);
  digitalWrite(pin, HIGH); delay(500); digitalWrite(pin, LOW);
}

void loop() {
  flash(LED_GREEN, "green");
  flash(LED_RED, "red");
  flash(LED_BLUE, "blue");
  Serial.println("beep");
  digitalWrite(BUZZER, HIGH); delay(150); digitalWrite(BUZZER, LOW);
  delay(1500);
}
