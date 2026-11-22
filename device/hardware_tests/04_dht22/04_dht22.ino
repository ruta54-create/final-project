/*
 * TEST 04 - DHT22 temperature + humidity (main ESP32 DevKit)
 * Library: "DHT sensor library" by Adafruit (+ "Adafruit Unified Sensor")
 * Wiring: VCC -> 3V3, GND -> GND, DATA -> GPIO4, and a 10k resistor between DATA and 3V3 (pull-up)
 *         (3-pin modules on a small PCB already have the 10k resistor)
 * Expected: temperature (about room temperature) and humidity every 2 s. Breathe on it: humidity rises.
 */
#include <DHT.h>
DHT dht(4, DHT22);

void setup() {
  Serial.begin(115200);
  dht.begin();
  Serial.println("TEST 04: DHT22");
}

void loop() {
  delay(2000);                                   // the DHT22 needs 2 s between readings
  float t = dht.readTemperature(), h = dht.readHumidity();
  if (isnan(t) || isnan(h)) Serial.println("read failed: check DATA wire and the 10k pull-up");
  else Serial.printf("temperature %.1f C   humidity %.0f %%\n", t, h);
}
