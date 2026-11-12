/*
 * ================================================================
 *  Edge-AI Smart Dustbin - MAIN CONTROLLER (ESP32 DevKit V1)
 * ================================================================
 *  Reads all sensors, moves the lid + sorting tray, talks to the
 *  ESP32-CAM over UART and to the Django server over Wi-Fi.
 *
 *  Board:      "ESP32 Dev Module"
 *  Libraries:  ArduinoJson (v7), ESP32Servo, DHT sensor library (Adafruit) + Adafruit Unified Sensor
 *  Setup:      copy secrets.example.h -> secrets.h and edit it
 *
 *  Wiring (see docs/HARDWARE.md for the full diagram):
 *   HC-SR04 organic     TRIG 5   ECHO 18 (via 1k/2k divider)
 *   HC-SR04 inorganic   TRIG 19  ECHO 21 (via 1k/2k divider)
 *   HC-SR04 hand (lid)  TRIG 22  ECHO 23 (via 1k/2k divider)
 *   IR sensor (tray)    OUT 34   (LOW = item present)
 *   MQ-135 gas          AO  35   (via 10k/20k divider, 5V -> 3.3V)
 *   DHT22               DATA 4   (10k pull-up to 3.3V)
 *   Tray servo MG996R   SIG 27   (own 5V supply, common GND)
 *   Lid  servo MG996R   SIG 14   (own 5V supply, common GND)
 *   Buzzer              25       LEDs: green 26, red 33, blue 32 (220R each)
 *   ESP32-CAM UART      RX2 16 <- CAM TX(GPIO14),  TX2 17 -> CAM RX(GPIO13)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <DHT.h>
#include "secrets.h"

#define FIRMWARE "1.0.0"

// ---------------- pins
const int TRIG_ORG = 5,  ECHO_ORG = 18;
const int TRIG_INO = 19, ECHO_INO = 21;
const int TRIG_HAND = 22, ECHO_HAND = 23;
const int IR_TRAY = 34, MQ135_PIN = 35, DHT_PIN = 4;
const int SERVO_TRAY = 27, SERVO_LID = 14;
const int BUZZER = 25, LED_GREEN = 26, LED_RED = 33, LED_BLUE = 32;
const int CAM_RX = 16, CAM_TX = 17;

// ---------------- mechanics (adjust to your build)
const int TRAY_CENTER = 90, TRAY_ORGANIC = 30, TRAY_INORGANIC = 150;
const int LID_CLOSED = 0, LID_OPEN = 100;
const float HAND_DISTANCE_CM = 15;       // hand closer than this opens the lid
const unsigned long LID_AUTO_CLOSE_MS = 5000;
const unsigned long CAM_TIMEOUT_MS = 8000;

// ---------------- MQ-135 (calibrate R0 in clean outdoor air, see docs/HARDWARE.md)
const float MQ_RL_KOHM = 10.0;   // load resistor on the module (check: 1k or 10k)
const float MQ_R0_KOHM = 76.6;   // sensor resistance in clean air (calibrate!)
const float ADC_DIVIDER = 1.5;   // 10k/20k divider: Vsensor = Vadc * 1.5

// ---------------- state
Servo trayServo, lidServo;
DHT dht(DHT_PIN, DHT22);
HardwareSerial CamSerial(2);

String mode = "auto";            // auto | manual | maintenance (from server)
bool lidOpen = false;
bool lidHeld = false;            // opened from dashboard -> stay open
unsigned long lidCloseAt = 0;
bool booted = true;
bool anyFull = false;
unsigned long lastTelemetry = 0, lastPoll = 0;
unsigned long telemetryInterval = 30000, pollInterval = 2000;
int lastOrganicLevel = -1, lastInorganicLevel = -1;

// ================================================================ helpers
void beep(int times, int ms = 80) {
  for (int i = 0; i < times; i++) {
    digitalWrite(BUZZER, HIGH); delay(ms);
    digitalWrite(BUZZER, LOW);  delay(ms);
  }
}

float readUltrasonicOnce(int trig, int echo) {
  digitalWrite(trig, LOW);  delayMicroseconds(3);
  digitalWrite(trig, HIGH); delayMicroseconds(10);
  digitalWrite(trig, LOW);
  unsigned long us = pulseIn(echo, HIGH, 30000);   // 30 ms ~ 5 m
  if (us == 0) return -1;
  return us * 0.0343f / 2.0f;
}

// median of 5 readings: removes random spikes from bags/odd shapes
float readDistanceCm(int trig, int echo) {
  float v[5]; int n = 0;
  for (int i = 0; i < 5; i++) {
    float d = readUltrasonicOnce(trig, echo);
    if (d > 0) v[n++] = d;
    delay(30);
  }
  if (n == 0) return -1;
  for (int i = 0; i < n; i++)
    for (int j = i + 1; j < n; j++)
      if (v[j] < v[i]) { float t = v[i]; v[i] = v[j]; v[j] = t; }
  return v[n / 2];
}

float readGasPpm() {
  float vAdc = analogReadMilliVolts(MQ135_PIN) / 1000.0f;
  float vSensor = vAdc * ADC_DIVIDER;
  if (vSensor < 0.05f) return -1;
  float rs = (5.0f - vSensor) / vSensor * MQ_RL_KOHM;
  return 116.6020682f * pow(rs / MQ_R0_KOHM, -2.769034857f);  // CO2-equivalent curve
}

bool itemOnTray() { return digitalRead(IR_TRAY) == LOW; }

void setLid(bool open) {
  lidServo.write(open ? LID_OPEN : LID_CLOSED);
  lidOpen = open;
}

void tilt(const String& compartment) {
  trayServo.write(compartment == "organic" ? TRAY_ORGANIC : TRAY_INORGANIC);
  delay(1200);                    // let the item slide off
  trayServo.write(TRAY_CENTER);
  delay(400);
}

void updateLeds() {
  digitalWrite(LED_RED, anyFull ? HIGH : LOW);
  digitalWrite(LED_GREEN, (!anyFull && WiFi.status() == WL_CONNECTED) ? HIGH : LOW);
  digitalWrite(LED_BLUE, mode == "maintenance" ? ((millis() / 500) % 2) : LOW);  // blink
}

// ================================================================ Wi-Fi + HTTP
void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("Wi-Fi connecting");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) { delay(250); Serial.print("."); }
  Serial.println(WiFi.status() == WL_CONNECTED ? " OK " + WiFi.localIP().toString() : " failed");
}

// method "GET" or "POST"; returns HTTP code (<=0 = network error)
int api(const char* method, const String& path, JsonDocument* body, JsonDocument* out) {
  if (WiFi.status() != WL_CONNECTED) return -1;
  HTTPClient http;
  http.setTimeout(5000);
  http.begin(String(SERVER_URL) + "/api/device" + path);
  http.addHeader("X-API-KEY", API_KEY);
  int code;
  if (strcmp(method, "GET") == 0) {
    code = http.GET();
  } else {
    String payload = "{}";
    if (body) serializeJson(*body, payload);
    http.addHeader("Content-Type", "application/json");
    code = http.POST(payload);
  }
  if (out && code > 0) deserializeJson(*out, http.getString());
  if (code == 401) Serial.println("!! Wrong API_KEY in secrets.h");
  http.end();
  return code;
}

void fetchConfig() {
  JsonDocument cfg;
  if (api("GET", "/config/", nullptr, &cfg) == 200) {
    mode = cfg["mode"].as<String>();
    telemetryInterval = (cfg["telemetry_interval_s"] | 30) * 1000UL;
    pollInterval = (cfg["command_poll_s"] | 2) * 1000UL;
    Serial.printf("Config: bin '%s', mode %s\n", cfg["name"].as<const char*>(), mode.c_str());
  }
}

void sendTelemetry() {
  JsonDocument doc, res;
  float dOrg = readDistanceCm(TRIG_ORG, ECHO_ORG);
  float dIno = readDistanceCm(TRIG_INO, ECHO_INO);
  if (dOrg > 0) doc["organic_distance_cm"] = dOrg;
  if (dIno > 0) doc["inorganic_distance_cm"] = dIno;
  float gas = readGasPpm();
  if (gas > 0) doc["gas_ppm"] = gas;
  float t = dht.readTemperature(), h = dht.readHumidity();
  if (!isnan(t)) doc["temperature"] = t;
  if (!isnan(h)) doc["humidity"] = h;
  doc["lid_open"] = lidOpen;
  doc["firmware"] = FIRMWARE;
  doc["wifi_rssi"] = WiFi.RSSI();
  doc["ip"] = WiFi.localIP().toString();
  doc["booted"] = booted;

  int code = api("POST", "/telemetry/", &doc, &res);
  if (code == 201) {
    booted = false;
    mode = res["mode"].as<String>();
    int org = res["organic_level"].isNull() ? -1 : (int)res["organic_level"].as<float>();
    int ino = res["inorganic_level"].isNull() ? -1 : (int)res["inorganic_level"].as<float>();
    bool full = org >= 90 || ino >= 90;
    if (full && !anyFull) beep(3, 150);          // just became full
    anyFull = full;
    lastOrganicLevel = org; lastInorganicLevel = ino;
    Serial.printf("Telemetry: organic %d%%, inorganic %d%%, gas %.0f ppm\n", org, ino, gas);
  } else {
    Serial.printf("Telemetry failed (%d)\n", code);
  }
}

void ack(int id, bool ok, const String& message, JsonDocument* result = nullptr) {
  JsonDocument doc;
  doc["status"] = ok ? "done" : "failed";
  doc["message"] = message;
  if (result) doc["result"] = *result;
  api("POST", "/commands/" + String(id) + "/ack/", &doc, nullptr);
}

// ================================================================ sorting
// Ask the camera to classify the item on the tray; returns "organic"/"inorganic".
String askCamera() {
  while (CamSerial.available()) CamSerial.read();      // clear old bytes
  CamSerial.print("CAPTURE\n");
  unsigned long start = millis();
  String line;
  while (millis() - start < CAM_TIMEOUT_MS) {
    if (CamSerial.available()) {
      char c = CamSerial.read();
      if (c == '\n') {
        line.trim();
        if (line.startsWith("SORT ")) {
          String comp = line.substring(5, line.indexOf(' ', 5) > 0 ? line.indexOf(' ', 5) : line.length());
          Serial.println("Camera: " + line);
          return comp == "organic" ? "organic" : "inorganic";
        }
        if (line == "EMPTY") { Serial.println("Camera: tray is empty, nothing to sort"); return ""; }
        if (line.startsWith("ERR")) { Serial.println("Camera error: " + line); break; }
        line = "";
      } else {
        line += c;
      }
    }
    delay(5);
  }
  Serial.println("Camera timeout -> inorganic (safe default)");
  digitalWrite(LED_RED, HIGH); beep(2, 60);
  return "inorganic";                                   // never contaminate compost
}

void sortItem() {
  if (lidOpen && !lidHeld) setLid(false);              // close lid: steady light, safe hands
  delay(300);
  String comp = askCamera();
  if (comp == "") return;                               // camera saw an empty tray: false trigger, don't tilt
  tilt(comp);
  beep(1, 40);
  unsigned long t = millis();
  while (itemOnTray() && millis() - t < 3000) delay(50); // wait for the tray to be clear
}

// ================================================================ commands
void pollCommands() {
  JsonDocument res;
  if (api("GET", "/commands/", nullptr, &res) != 200) return;
  String newMode = res["mode"].as<String>();
  if (newMode != mode) {
    mode = newMode;
    Serial.println("Mode -> " + mode);
    if (mode == "maintenance") { setLid(true); lidHeld = true; }
    else if (lidHeld) { lidHeld = false; setLid(false); }
  }
  for (JsonObject cmd : res["commands"].as<JsonArray>()) {
    int id = cmd["id"];
    String action = cmd["action"].as<String>();
    Serial.println("Command: " + action);

    if (action == "open_lid")            { setLid(true); lidHeld = true; ack(id, true, "Lid opened"); }
    else if (action == "close_lid")      { setLid(false); lidHeld = false; ack(id, true, "Lid closed"); }
    else if (action == "sort_organic")   { tilt("organic"); ack(id, true, "Tray tilted to organic"); }
    else if (action == "sort_inorganic") { tilt("inorganic"); ack(id, true, "Tray tilted to inorganic"); }
    else if (action == "capture") {
      if (!itemOnTray()) ack(id, false, "No item on the tray");
      else { sortItem(); ack(id, true, "Item classified and sorted"); }
    }
    else if (action == "calibrate") {
      JsonDocument r;
      float o = readDistanceCm(TRIG_ORG, ECHO_ORG), i = readDistanceCm(TRIG_INO, ECHO_INO);
      if (o <= 2 || i <= 2) { ack(id, false, "Ultrasonic sensor not answering"); continue; }
      r["organic_depth_cm"] = o; r["inorganic_depth_cm"] = i;
      ack(id, true, "Measured " + String(o, 1) + " / " + String(i, 1) + " cm", &r);
    }
    else if (action == "set_mode")       { ack(id, true, "Mode " + mode); }
    else if (action == "buzzer") {
      digitalWrite(LED_GREEN, HIGH); digitalWrite(LED_RED, HIGH); digitalWrite(LED_BLUE, HIGH);
      beep(3, 120);
      digitalWrite(LED_BLUE, LOW);
      ack(id, true, "Buzzer and LEDs OK");
    }
    else if (action == "reboot")         { ack(id, true, "Rebooting"); delay(300); ESP.restart(); }
    else                                 { ack(id, false, "Unknown action"); }
  }
}

// ================================================================ setup / loop
void setup() {
  Serial.begin(115200);
  CamSerial.begin(115200, SERIAL_8N1, CAM_RX, CAM_TX);

  pinMode(TRIG_ORG, OUTPUT);  pinMode(ECHO_ORG, INPUT);
  pinMode(TRIG_INO, OUTPUT);  pinMode(ECHO_INO, INPUT);
  pinMode(TRIG_HAND, OUTPUT); pinMode(ECHO_HAND, INPUT);
  pinMode(IR_TRAY, INPUT);
  pinMode(BUZZER, OUTPUT); pinMode(LED_GREEN, OUTPUT); pinMode(LED_RED, OUTPUT); pinMode(LED_BLUE, OUTPUT);
  analogSetPinAttenuation(MQ135_PIN, ADC_11db);

  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  trayServo.setPeriodHertz(50); trayServo.attach(SERVO_TRAY, 500, 2400);
  lidServo.setPeriodHertz(50);  lidServo.attach(SERVO_LID, 500, 2400);
  trayServo.write(TRAY_CENTER);
  setLid(false);
  dht.begin();

  Serial.println("\nEdge-AI Smart Dustbin main controller " FIRMWARE);
  ensureWifi();
  fetchConfig();
  sendTelemetry();
  beep(1, 200);
}

void loop() {
  ensureWifi();
  unsigned long now = millis();

  if (now - lastPoll >= pollInterval) { lastPoll = now; pollCommands(); }
  if (now - lastTelemetry >= telemetryInterval) { lastTelemetry = now; sendTelemetry(); }

  // touchless lid
  if (mode != "maintenance" && !lidHeld) {
    float hand = readUltrasonicOnce(TRIG_HAND, ECHO_HAND);
    if (hand > 0 && hand < HAND_DISTANCE_CM) {
      if (!lidOpen) setLid(true);
      lidCloseAt = now + LID_AUTO_CLOSE_MS;
    } else if (lidOpen && now > lidCloseAt) {
      setLid(false);
    }
  }

  // automatic sorting
  if (mode == "auto" && itemOnTray()) {
    delay(300);                                   // debounce: item must stay
    if (itemOnTray()) sortItem();
  }

  updateLeds();
  delay(50);
}
