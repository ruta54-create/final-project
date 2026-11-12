/*
 * ================================================================
 *  Edge-AI Smart Dustbin - AI CAMERA (ESP32-S3-CAM recommended)
 * ================================================================
 *  Waits for "CAPTURE" from the main controller, takes a photo, runs the
 *  MobileNetV2 waste classifier ON THE CAMERA (edge AI), answers
 *  "SORT organic 0.93" (or "EMPTY") and uploads the photo + result to Django.
 *
 *  Model classes -> compartment of the bin
 *      organic, paper   -> ORGANIC compartment   (biodegradable)
 *      plastic, metal   -> INORGANIC compartment
 *      background       -> nothing on the tray (optional 5th class) -> no sorting
 *  Unsure (confidence < min_confidence from the dashboard) -> INORGANIC (never contaminate compost)
 *
 *  1) Select your board at the top of camera_pins.h (ESP32-S3-CAM, XIAO ESP32S3, AI-Thinker)
 *  2) Arduino IDE: install your Edge Impulse library (.zip) + ArduinoJson (v7)
 *  3) change the #include below to your library name
 *  4) copy secrets.example.h -> secrets.h and edit it
 *  Wiring: see camera_pins.h (UART to the main ESP32, LED ring MOSFET) and docs/HARDWARE.md
 */

#include <smart_dustbin_inferencing.h>        // <-- CHANGE to <your_project_inferencing.h>
#include "edge-impulse-sdk/dsp/image/image.hpp"
#include "esp_camera.h"
#include "img_converters.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "camera_pins.h"
#include "secrets.h"

#define FIRMWARE "2.0.0"
#define MODEL_VERSION "waste4-mobilenetv2-128-v1"   // change when you retrain (shown on the dashboard)

// Labels that go to the ORGANIC compartment. Everything else (plastic, metal) -> INORGANIC.
const char* ORGANIC_LABELS[] = {"organic", "paper", "food_waste", "fruit_peel", "vegetable", "leaves", "cardboard"};
const char* EMPTY_LABEL = "background";   // optional class: photo of the empty tray

#define RAW_COLS 320   // QVGA
#define RAW_ROWS 240

HardwareSerial MainSerial(1);
static uint8_t* rgbBuf = nullptr;        // RGB888 frame for the model
float minConfidence = 0.70;               // updated from the server
unsigned long lastHeartbeat = 0;

void light(bool on) {
  if (LIGHT_GPIO_NUM >= 0) digitalWrite(LIGHT_GPIO_NUM, on ? HIGH : LOW);
}

// ================================================================ camera
bool cameraInit() {
  camera_config_t c = {};
  c.pin_pwdn = PWDN_GPIO_NUM;   c.pin_reset = RESET_GPIO_NUM; c.pin_xclk = XCLK_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM; c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_d7 = Y9_GPIO_NUM; c.pin_d6 = Y8_GPIO_NUM; c.pin_d5 = Y7_GPIO_NUM; c.pin_d4 = Y6_GPIO_NUM;
  c.pin_d3 = Y5_GPIO_NUM; c.pin_d2 = Y4_GPIO_NUM; c.pin_d1 = Y3_GPIO_NUM; c.pin_d0 = Y2_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM; c.pin_href = HREF_GPIO_NUM; c.pin_pclk = PCLK_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.ledc_timer = LEDC_TIMER_0;
  c.ledc_channel = LEDC_CHANNEL_0;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_QVGA;          // 320x240
  c.jpeg_quality = 12;
  c.fb_count = 1;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_LATEST;

  if (esp_camera_init(&c) != ESP_OK) return false;
  sensor_t* s = esp_camera_sensor_get();
  s->set_vflip(s, 1);                     // depends on how the camera is mounted
  s->set_whitebal(s, 1);
  return true;
}

// Edge Impulse reads pixels through this callback (packed RGB as float)
static int getData(size_t offset, size_t length, float* out) {
  size_t px = offset * 3;
  for (size_t i = 0; i < length; i++, px += 3) {
    // esp32-camera returns BGR from fmt2rgb888 -> swap to RGB
    out[i] = (rgbBuf[px + 2] << 16) + (rgbBuf[px + 1] << 8) + rgbBuf[px];
  }
  return 0;
}

bool isOrganic(const char* label) {
  for (const char* l : ORGANIC_LABELS) if (strcasecmp(l, label) == 0) return true;
  return false;
}

// ================================================================ network
void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
  Serial.println(WiFi.status() == WL_CONNECTED ? "Wi-Fi OK " + WiFi.localIP().toString() : "Wi-Fi failed");
}

void heartbeat() {   // also refreshes min_confidence from the dashboard settings
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.begin(String(SERVER_URL) + "/api/device/config/?role=cam");
  http.addHeader("X-API-KEY", API_KEY);
  if (http.GET() == 200) {
    JsonDocument cfg;
    if (!deserializeJson(cfg, http.getString())) minConfidence = cfg["min_confidence"] | 0.70;
  }
  http.end();
}

void addField(String& s, const String& boundary, const char* name, const String& value) {
  s += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"" + name + "\"\r\n\r\n" + value + "\r\n";
}

// multipart/form-data upload of the photo + AI result
void uploadDetection(const uint8_t* jpg, size_t jpgLen, const char* label, const char* category,
                     const char* sortedTo, float confidence, int inferenceMs) {
  if (WiFi.status() != WL_CONNECTED) return;
  String boundary = "----smartbin" + String(millis());
  String head;
  addField(head, boundary, "label", label);
  addField(head, boundary, "category", category);
  addField(head, boundary, "sorted_to", sortedTo);
  addField(head, boundary, "confidence", String(confidence, 4));
  addField(head, boundary, "inference_ms", String(inferenceMs));
  addField(head, boundary, "firmware", FIRMWARE);
  addField(head, boundary, "model_version", MODEL_VERSION);
  addField(head, boundary, "ip", WiFi.localIP().toString());
  head += "--" + boundary + "\r\nContent-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n"
          "Content-Type: image/jpeg\r\n\r\n";
  String tail = "\r\n--" + boundary + "--\r\n";

  size_t total = head.length() + jpgLen + tail.length();
  uint8_t* body = (uint8_t*)ps_malloc(total);
  if (!body) { Serial.println("No PSRAM for upload"); return; }
  memcpy(body, head.c_str(), head.length());
  memcpy(body + head.length(), jpg, jpgLen);
  memcpy(body + head.length() + jpgLen, tail.c_str(), tail.length());

  HTTPClient http;
  http.setTimeout(10000);
  http.begin(String(SERVER_URL) + "/api/device/detection/");
  http.addHeader("X-API-KEY", API_KEY);
  http.addHeader("Content-Type", "multipart/form-data; boundary=" + boundary);
  int code = http.POST(body, total);
  Serial.printf("Upload -> %d\n", code);
  http.end();
  free(body);
}

// ================================================================ capture + classify
void handleCapture() {
  light(true);                                // uniform light = better accuracy
  delay(150);
  camera_fb_t* fb = esp_camera_fb_get();      // drop a stale frame
  if (fb) esp_camera_fb_return(fb);
  fb = esp_camera_fb_get();
  light(false);
  if (!fb) { MainSerial.print("ERR camera\n"); return; }

  // keep a copy of the JPEG for the upload
  size_t jpgLen = fb->len;
  uint8_t* jpg = (uint8_t*)ps_malloc(jpgLen);
  if (jpg) memcpy(jpg, fb->buf, jpgLen);

  bool ok = fmt2rgb888(fb->buf, fb->len, PIXFORMAT_JPEG, rgbBuf);
  esp_camera_fb_return(fb);
  if (!ok) { MainSerial.print("ERR decode\n"); free(jpg); return; }

  // resize 320x240 -> model input (e.g. 96x96)
  ei::image::processing::crop_and_interpolate_rgb888(
      rgbBuf, RAW_COLS, RAW_ROWS, rgbBuf, EI_CLASSIFIER_INPUT_WIDTH, EI_CLASSIFIER_INPUT_HEIGHT);

  ei::signal_t signal;
  signal.total_length = EI_CLASSIFIER_INPUT_WIDTH * EI_CLASSIFIER_INPUT_HEIGHT;
  signal.get_data = &getData;
  ei_impulse_result_t result = {0};
  unsigned long t0 = millis();
  EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
  int inferenceMs = millis() - t0;
  if (err != EI_IMPULSE_OK) { MainSerial.print("ERR model\n"); free(jpg); return; }

  // best and second-best class (the runner-up helps when reviewing mistakes on the dashboard)
  const char* best = "unknown";
  const char* second = "";
  float conf = 0, conf2 = 0;
#if EI_CLASSIFIER_OBJECT_DETECTION == 1
  for (uint32_t i = 0; i < result.bounding_boxes_count; i++)
    if (result.bounding_boxes[i].value > conf) { conf = result.bounding_boxes[i].value; best = result.bounding_boxes[i].label; }
#else
  for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
    float v = result.classification[i].value;
    if (v > conf) { conf2 = conf; second = best; conf = v; best = result.classification[i].label; }
    else if (v > conf2) { conf2 = v; second = result.classification[i].label; }
  }
#endif

  if (strcasecmp(best, EMPTY_LABEL) == 0) {   // the tray is empty: nothing to sort, nothing to upload
    MainSerial.print("EMPTY\n");
    Serial.printf("tray empty (%.0f%%)\n", conf * 100);
    free(jpg);
    return;
  }

  const char* category = isOrganic(best) ? "organic" : "inorganic";
  // safety rule: unsure -> inorganic (never contaminate the compost)
  const char* sortedTo = conf >= minConfidence ? category : "inorganic";

  // answer the main controller FIRST so the tray moves immediately
  MainSerial.printf("SORT %s %.3f\n", sortedTo, conf);
  Serial.printf("%s (%s) %.0f%%  [2nd: %s %.0f%%]  %d ms -> %s\n", best, category, conf * 100,
                second, conf2 * 100, inferenceMs, sortedTo);

  if (jpg) {
    uploadDetection(jpg, jpgLen, best, category, sortedTo, conf, inferenceMs);
    free(jpg);
  }
}

// ================================================================ setup / loop
void setup() {
  Serial.begin(115200);
  MainSerial.begin(115200, SERIAL_8N1, UART_RX_GPIO, UART_TX_GPIO);
  if (LIGHT_GPIO_NUM >= 0) { pinMode(LIGHT_GPIO_NUM, OUTPUT); light(false); }

  if (!psramFound()) Serial.println("!! PSRAM not found: enable it in Tools menu");
  rgbBuf = (uint8_t*)ps_malloc(RAW_COLS * RAW_ROWS * 3);
  if (!cameraInit() || !rgbBuf) {
    Serial.println("!! Camera init failed, restarting");
    delay(2000);
    ESP.restart();
  }
  Serial.printf(CAMERA_BOARD_NAME " ready. Model input %dx%d, %d labels\n",
                EI_CLASSIFIER_INPUT_WIDTH, EI_CLASSIFIER_INPUT_HEIGHT, EI_CLASSIFIER_LABEL_COUNT);
  ensureWifi();
  heartbeat();
  MainSerial.print("READY\n");
}

void loop() {
  static String line;
  while (MainSerial.available()) {
    char c = MainSerial.read();
    if (c == '\n') {
      line.trim();
      if (line == "CAPTURE") handleCapture();
      line = "";
    } else if (line.length() < 32) {
      line += c;
    }
  }
  if (millis() - lastHeartbeat > 60000) {
    lastHeartbeat = millis();
    ensureWifi();
    heartbeat();
  }
  delay(5);
}
