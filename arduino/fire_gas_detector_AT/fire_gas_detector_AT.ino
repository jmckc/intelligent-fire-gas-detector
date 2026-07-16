/**
 * fire_gas_detector.ino
 * Intelligent Fire & Gas Leak Detection System
 * Arduino Uno Firmware �?AT Command Version
 *
 * Pin Map:
 *   A0  �?MQ-2  analog output
 *   D2  �?MQ-2  digital output
 *   D3  �?IR Flame sensor digital output (LOW = flame)
 *   D4  �?DHT11 data
 *   D5  �?ESP-01 TX �?Arduino RX (SoftwareSerial)
 *   D6  �?ESP-01 RX �?Arduino TX (via voltage divider)
 *   D7  �?Relay (active LOW)
 *   D8  �?Buzzer
 *   D9  �?Red LED
 *   D10 �?Green LED
 *
 * ESP-01 WiFi Configuration:
 *   Change WIFI_SSID, WIFI_PASS, SERVER_IP before uploading
 */

#include <SoftwareSerial.h>
#include <DHT.h>

// ── Pin Definitions ────────────────────────────────────────────────────────
#define MQ2_ANALOG_PIN   A0
#define MQ2_DIGITAL_PIN  2
#define FLAME_PIN        3
#define DHT_PIN          4
#define ESP_RX_PIN       5
#define ESP_TX_PIN       6
#define RELAY_PIN        7
#define BUZZER_PIN       8
#define RED_LED_PIN      9
#define GREEN_LED_PIN    10

// ── Thresholds ─────────────────────────────────────────────────────────────
#define GAS_ANALOG_ALARM   400
#define TEMP_ALARM_C       60.0
#define TEMP_RISE_RATE     5.0
#define POLL_INTERVAL_MS   1000
#define RATE_WINDOW        10

// ── WiFi & Server Configuration ───────────────────────────────────────────
const char* WIFI_SSID   = "YOUR_WIFI_SSID";      // Change this
const char* WIFI_PASS   = "YOUR_WIFI_PASSWORD";  // Change this
const char* SERVER_IP   = "YOUR_SERVER_IP";      // Change to your PC LAN IP
const int   SERVER_PORT = 5000;

// ── SoftwareSerial ─────────────────────────────────────────────────────────
SoftwareSerial espSerial(ESP_RX_PIN, ESP_TX_PIN);

// ── DHT11 ──────────────────────────────────────────────────────────────────
DHT dht(DHT_PIN, DHT11);

// ── State Variables ────────────────────────────────────────────────────────
int   gasHistory[RATE_WINDOW];
int   historyIndex = 0;
bool  historyFull  = false;
float lastTemp     = 0.0;
bool  alarmActive  = false;
bool  wifiReady    = false;

unsigned long lastPollTime = 0;

// ── AT Command Helper ──────────────────────────────────────────────────────
String sendAT(String cmd, int timeout) {
  String response = "";
  espSerial.println(cmd);
  long start = millis();
  while (millis() - start < timeout) {
    while (espSerial.available()) {
      response += (char)espSerial.read();
    }
  }
  Serial.println("AT>> " + response);
  return response;
}

// ── WiFi Setup ─────────────────────────────────────────────────────────────
bool setupWiFi() {
  Serial.println(F("[WiFi] Testing ESP-01..."));
  String resp = sendAT("AT", 2000);
  if (resp.indexOf("OK") == -1) {
    Serial.println(F("[WiFi] ESP-01 not responding!"));
    return false;
  }

  Serial.println(F("[WiFi] Setting station mode..."));
  sendAT("AT+CWMODE=1", 2000);

  Serial.println(F("[WiFi] Connecting to WiFi..."));
  String cmd = "AT+CWJAP=\"";
  cmd += WIFI_SSID;
  cmd += "\",\"";
  cmd += WIFI_PASS;
  cmd += "\"";
  resp = sendAT(cmd, 15000);

  if (resp.indexOf("OK") != -1) {
    Serial.println(F("[WiFi] Connected!"));
    sendAT("AT+CIFSR", 2000);
    return true;
  }

  Serial.println(F("[WiFi] Connection FAILED"));
  return false;
}

// ── Send Data to Server ────────────────────────────────────────────────────
void sendToServer(String json) {
  if (!wifiReady) return;

  // Build HTTP POST
  String httpReq  = "POST /api/sensor-data HTTP/1.1\r\n";
  httpReq += "Host: ";
  httpReq += SERVER_IP;
  httpReq += ":";
  httpReq += String(SERVER_PORT);
  httpReq += "\r\n";
  httpReq += "Content-Type: application/json\r\n";
  httpReq += "Connection: close\r\n";
  httpReq += "Content-Length: ";
  httpReq += String(json.length());
  httpReq += "\r\n\r\n";
  httpReq += json;

  // Open TCP connection
  String cipCmd = "AT+CIPSTART=\"TCP\",\"";
  cipCmd += SERVER_IP;
  cipCmd += "\",";
  cipCmd += String(SERVER_PORT);
  String resp = sendAT(cipCmd, 5000);

  if (resp.indexOf("OK") == -1 && resp.indexOf("ALREADY") == -1) {
    Serial.println(F("[HTTP] TCP connect failed"));
    wifiReady = false;  // Reconnect on next cycle
    return;
  }

  // Send data
  sendAT("AT+CIPSEND=" + String(httpReq.length()), 2000);
  delay(100);
  espSerial.print(httpReq);

  // Read response
  String result = "";
  long start = millis();
  while (millis() - start < 10000) {
    while (espSerial.available()) {
      result += (char)espSerial.read();
    }
  }

  if (result.indexOf("201") != -1) {
    Serial.println(F("[HTTP] POST OK: 201"));
  } else {
    Serial.println(F("[HTTP] POST failed"));
  }

  // Close connection
  sendAT("AT+CIPCLOSE", 1000);
}

// ── Alarm Outputs ──────────────────────────────────────────────────────────
void setAlarmOutputs(bool on) {
  if (on) {
    digitalWrite(RELAY_PIN,     LOW);
    digitalWrite(RED_LED_PIN,   HIGH);
    digitalWrite(GREEN_LED_PIN, LOW);
    tone(BUZZER_PIN, 2048);
  } else {
    digitalWrite(RELAY_PIN,     HIGH);
    digitalWrite(RED_LED_PIN,   LOW);
    digitalWrite(GREEN_LED_PIN, HIGH);
    noTone(BUZZER_PIN);
    digitalWrite(BUZZER_PIN, LOW);
  }
}

// ──────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(9600);
  espSerial.begin(9600);
  dht.begin();

  pinMode(MQ2_DIGITAL_PIN, INPUT);
  pinMode(FLAME_PIN,        INPUT);
  pinMode(RELAY_PIN,        OUTPUT);
  pinMode(BUZZER_PIN,       OUTPUT);
  pinMode(RED_LED_PIN,      OUTPUT);
  pinMode(GREEN_LED_PIN,    OUTPUT);

  digitalWrite(RELAY_PIN,     HIGH);
  digitalWrite(GREEN_LED_PIN, HIGH);

  for (int i = 0; i < RATE_WINDOW; i++) gasHistory[i] = 0;

  Serial.println(F("[BOOT] Fire & Gas Detection System Ready (AT Mode)"));

  // Connect WiFi on startup
  wifiReady = setupWiFi();
}

// ──────────────────────────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();
  if (now - lastPollTime < POLL_INTERVAL_MS) return;
  lastPollTime = now;

  // ── Read Sensors ──────────────────────────────────────────────────────
  int   gasAnalog   = analogRead(MQ2_ANALOG_PIN);
  bool  gasDigital  = (digitalRead(MQ2_DIGITAL_PIN) == HIGH);
  bool  flameDetect = (digitalRead(FLAME_PIN) == LOW);
  float temperature = dht.readTemperature();
  float humidity    = dht.readHumidity();

  if (isnan(temperature)) temperature = -1.0;
  if (isnan(humidity))    humidity    = -1.0;

  // ── Rate of Change ────────────────────────────────────────────────────
  gasHistory[historyIndex] = gasAnalog;
  historyIndex = (historyIndex + 1) % RATE_WINDOW;
  if (historyIndex == 0) historyFull = true;

  int   oldestGas  = gasHistory[historyIndex];
  float gasRatePct = historyFull ? ((float)(gasAnalog - oldestGas) / max(oldestGas, 1)) * 100.0 : 0.0;
  float tempRate   = (lastTemp > 0.0 && temperature > 0.0) ? temperature - lastTemp : 0.0;
  lastTemp = temperature;

  // ── Alarm Logic ───────────────────────────────────────────────────────
  bool gasAlarm  = (gasAnalog >= GAS_ANALOG_ALARM);
  bool tempAlarm = (temperature >= TEMP_ALARM_C) ||
                   (tempRate   >= TEMP_RISE_RATE / RATE_WINDOW);
  bool newAlarm  = gasAlarm || flameDetect || tempAlarm;

  if (newAlarm != alarmActive) {
    alarmActive = newAlarm;
    setAlarmOutputs(alarmActive);
  }

  // ── Reconnect WiFi if needed ──────────────────────────────────────────
  if (!wifiReady) {
    Serial.println(F("[WiFi] Reconnecting..."));
    wifiReady = setupWiFi();
  }

  // ── Serial Debug ──────────────────────────────────────────────────────
  Serial.print(F("[DATA] gas="));  Serial.print(gasAnalog);
  Serial.print(F(" temp="));       Serial.print(temperature);
  Serial.print(F(" hum="));        Serial.print(humidity);
  Serial.print(F(" flame="));      Serial.print(flameDetect);
  Serial.print(F(" alarm="));      Serial.println(alarmActive);

  // ── Build JSON & Send ─────────────────────────────────────────────────
  String json = "{";
  json += "\"gas\":"      + String(gasAnalog);
  json += ",\"gas_rate\":" + String(gasRatePct, 1);
  json += ",\"temp\":"    + String(temperature, 1);
  json += ",\"hum\":"     + String(humidity, 1);
  json += ",\"flame\":"   + String(flameDetect  ? "true" : "false");
  json += ",\"gas_al\":"  + String(gasAlarm     ? "true" : "false");
  json += ",\"tmp_al\":"  + String(tempAlarm    ? "true" : "false");
  json += ",\"alarm\":"   + String(alarmActive  ? "true" : "false");
  json += "}";

  sendToServer(json);
}
