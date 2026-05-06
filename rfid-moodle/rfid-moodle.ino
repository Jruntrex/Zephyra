#include <Wire.h>
#include <Adafruit_PN532.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "mbedtls/md.h"

// --- ПІНИ ---
#define I2C_SDA 8
#define I2C_SCL 9
#define LED_PIN 10
#define BUZZ_PIN 7

// --- НАЛАШТУВАННЯ МЕРЕЖІ ---
const char* WIFI_SSID     = "TP-Link_C4BE";
const char* WIFI_PASSWORD = "49909210";

// --- СЕРВЕР (DigitalOcean) ---
const char* SERVER_HOST = "mentorly.space";
const int   SERVER_PORT = 443;
const char* ENDPOINT    = "/api/rfid/scan/";

// --- БЕЗПЕКА: HMAC-SHA256 ключ ---
// Має точно збігатись зі значенням CARD_SCAN_API_KEY у файлі .env на сервері
const char* HMAC_SECRET = "807067887ba3c4bb067eacb82275aec4f1632dcec41616e93414b6d24d942454";

// -------------------------------------------------------

Adafruit_PN532 nfc(I2C_SDA, I2C_SCL);

// --- NTP синхронізація часу ---
void syncTime() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("Синхронізація NTP...");
  time_t now = 0;
  int attempts = 0;
  while (now < 1000000000UL && attempts < 20) {
    delay(500);
    time(&now);
    Serial.print(".");
    attempts++;
  }
  if (now > 1000000000UL) {
    Serial.printf("\nЧас синхронізовано: %lu\n", (unsigned long)now);
  } else {
    Serial.println("\n[ПОПЕРЕДЖЕННЯ] Час не синхронізовано — сервер відхилятиме запити!");
  }
}

// --- HMAC-SHA256 підпис повідомлення ---
// Повертає hex-рядок підпису довжиною 64 символи
String computeHMAC(const String& message, const String& key) {
  unsigned char hmacResult[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
  mbedtls_md_hmac_starts(&ctx,
    (const unsigned char*)key.c_str(), key.length());
  mbedtls_md_hmac_update(&ctx,
    (const unsigned char*)message.c_str(), message.length());
  mbedtls_md_hmac_finish(&ctx, hmacResult);
  mbedtls_md_free(&ctx);

  String result = "";
  for (int i = 0; i < 32; i++) {
    if (hmacResult[i] < 0x10) result += "0";
    result += String(hmacResult[i], HEX);
  }
  return result;
}

// --- Звукові сигнали ---
void beepSuccess(int count) {
  for (int i = 0; i < count; i++) {
    digitalWrite(LED_PIN, HIGH);
    digitalWrite(BUZZ_PIN, HIGH);
    delay(120);
    digitalWrite(LED_PIN, LOW);
    digitalWrite(BUZZ_PIN, LOW);
    if (i < count - 1) delay(120);
  }
}

void beepError() {
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(BUZZ_PIN, HIGH);
  delay(1000);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZ_PIN, LOW);
}

// --- WiFi підключення ---
void connectWiFi() {
  Serial.printf("\nПідключення до %s...", WIFI_SSID);
  WiFi.disconnect(true);
  delay(1000);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWiFi OK — IP: %s\n", WiFi.localIP().toString().c_str());
    beepSuccess(3);
    syncTime();
  } else {
    Serial.println("\n[ПОМИЛКА] WiFi не підключено.");
    beepError();
  }
}

// -------------------------------------------------------

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZ_PIN, OUTPUT);

  connectWiFi();

  nfc.begin();
  if (!nfc.getFirmwareVersion()) {
    Serial.println("PN532 не знайдено! Перевірте підключення.");
    while (1) beepError();
  }

  nfc.SAMConfig();
  Serial.println("--- СИСТЕМА ГОТОВА ---");
}

void loop() {
  uint8_t uid[7] = {0};
  uint8_t uidLength;

  if (!nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 500)) return;

  // Формуємо UID як рядок "AA:BB:CC:DD"
  String uidStr = "";
  for (uint8_t i = 0; i < uidLength; i++) {
    if (i > 0) uidStr += ":";
    if (uid[i] < 0x10) uidStr += "0";
    uidStr += String(uid[i], HEX);
  }
  uidStr.toUpperCase();
  Serial.printf("\nЗчитано UID: %s\n", uidStr.c_str());

  // Миттєвий відгук на зчитування
  digitalWrite(LED_PIN, HIGH);
  digitalWrite(BUZZ_PIN, HIGH);
  delay(80);
  digitalWrite(LED_PIN, LOW);
  digitalWrite(BUZZ_PIN, LOW);

  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    return;
  }

  // --- Формуємо підписаний запит ---
  time_t now;
  time(&now);
  String timestamp = String((unsigned long)now);

  // Підписуємо: "UID:timestamp"
  String message   = uidStr + ":" + timestamp;
  String signature = computeHMAC(message, String(HMAC_SECRET));

  Serial.printf("Timestamp: %s | Signature: %s\n",
    timestamp.c_str(), signature.c_str());

  WiFiClientSecure client;
  client.setInsecure();  // skip cert verification — HMAC guards authenticity
  HTTPClient http;
  String url = String("https://") + SERVER_HOST + ":" + SERVER_PORT + ENDPOINT;
  http.begin(client, url);
  http.addHeader("Content-Type",  "application/json");
  http.addHeader("X-Timestamp",   timestamp);
  http.addHeader("X-Signature",   signature);

  String jsonBody = "{\"uid\":\"" + uidStr + "\"}";
  int httpCode = http.POST(jsonBody);

  if (httpCode > 0) {
    String response = http.getString();
    Serial.printf("HTTP %d: %s\n", httpCode, response.c_str());

    if (httpCode == 403) {
      // Сервер відхилив — невірний ключ або час не синхронізовано
      Serial.println("[БЕЗПЕКА] Підпис відхилено сервером.");
      beepError();
    } else {
      StaticJsonDocument<256> doc;
      if (!deserializeJson(doc, response)) {
        String direction = doc["direction"] | "";
        if (direction == "in") {
          delay(100);
          beepSuccess(1);  // 1 сигнал — ВХІД
        } else if (direction == "out") {
          delay(100);
          beepSuccess(2);  // 2 сигнали — ВИХІД
        } else {
          beepSuccess(1);
        }
      } else {
        beepSuccess(1);
      }
    }
  } else {
    Serial.printf("[ПОМИЛКА] Запит не вдався: %s\n",
      http.errorToString(httpCode).c_str());
    beepError();
  }

  http.end();
  delay(2000);  // Антидребезг між картками
}
