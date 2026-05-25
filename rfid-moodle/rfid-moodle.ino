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
struct WifiNetwork {
  const char* ssid;
  const char* password;
};

WifiNetwork networks[] = {
  {"UKrtelecom_433750", "SS3q9tbC"},
  {"Boscolviv", "Boscolviv"},
  {"TP-Link_C4BE", "49909210"}
};
const int networkCount = sizeof(networks) / sizeof(networks[0]);

// --- СЕРВЕР (DigitalOcean) ---
const char* SERVER_HOST = "mentorly.space";
const int   SERVER_PORT = 443;
const char* ENDPOINT    = "/api/rfid/scan/";

// --- БЕЗПЕКА: HMAC-SHA256 ключ ---
const char* HMAC_SECRET = "807067887ba3c4bb067eacb82275aec4f1632dcec41616e93414b6d24d942454";

// --- Лічильник послідовних невдач HTTP ---
int consecutiveFailures = 0;
const int MAX_FAILURES  = 3;

// -------------------------------------------------------

Adafruit_PN532 nfc(I2C_SDA, I2C_SCL);

// --- Базові функції LED ---
inline void ledOn()  { digitalWrite(LED_PIN, HIGH); }
inline void ledOff() { digitalWrite(LED_PIN, LOW);  }

// --- Звукові та світлові сигнали ---

// Миттєвий відгук при зчитуванні картки
void beepScan() {
  ledOn(); digitalWrite(BUZZ_PIN, HIGH);
  delay(80);
  ledOff(); digitalWrite(BUZZ_PIN, LOW);
}

// Сигнал успішного підключення до мережі: 3× (LED вимк → бізк+спалах)
// Перед викликом LED має бути ввімкнений (горів під час пошуку)
void beepConnected() {
  for (int i = 0; i < 3; i++) {
    ledOff();
    delay(350);
    ledOn(); digitalWrite(BUZZ_PIN, HIGH);
    delay(200);
    ledOff(); digitalWrite(BUZZ_PIN, LOW);
    delay(100);
  }
}

// 1 або 2 коротких сигнали (вхід / вихід)
void beepDirection(int count) {
  for (int i = 0; i < count; i++) {
    ledOn(); digitalWrite(BUZZ_PIN, HIGH);
    delay(120);
    ledOff(); digitalWrite(BUZZ_PIN, LOW);
    if (i < count - 1) delay(120);
  }
}

// Один довгий сигнал — помилка
void beepError() {
  ledOn(); digitalWrite(BUZZ_PIN, HIGH);
  delay(1000);
  ledOff(); digitalWrite(BUZZ_PIN, LOW);
}

// --- NTP синхронізація ---
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
    Serial.println("\n[ПОПЕРЕДЖЕННЯ] NTP не синхронізовано — сервер відхилятиме запити!");
  }
}

// --- HMAC-SHA256 підпис ---
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

// --- WiFi підключення (каскадне по 3 роутерах) ---
// LED горить суцільно весь час пошуку — gасне або змінюється лише після з'єднання
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  ledOn();  // Суцільне світіння: йде пошук мережі

  for (int i = 0; i < networkCount; i++) {
    Serial.printf("\nСпроба підключення до мережі %d: %s", i + 1, networks[i].ssid);
    WiFi.disconnect(true);
    delay(500);
    WiFi.begin(networks[i].ssid, networks[i].password);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {  // ~10 с на мережу
      delay(500);
      Serial.print(".");
      attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
      Serial.printf("\nWiFi OK — IP: %s (Мережа: %s)\n",
        WiFi.localIP().toString().c_str(), networks[i].ssid);
      beepConnected();  // 3 спалахи з бізком — підключено
      syncTime();
      ledOff();         // Готовий до роботи
      return;
    }

    Serial.printf("\n[!] %s недоступна. Перехід...", networks[i].ssid);
  }

  // Жодна мережа не підключилась
  Serial.println("\n[ПОМИЛКА] Жодна мережа недоступна. Перезавантаження...");
  beepError();
  delay(3000);
  ESP.restart();
}

// -------------------------------------------------------

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZ_PIN, OUTPUT);

  ledOn();  // Живлення подано, ще не підключено — суцільне світіння без мигання

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
  // --- Перевірка WiFi: якщо впало — перепідключитись ---
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] З'єднання втрачено, перепідключення...");
    connectWiFi();
    return;
  }

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

  beepScan();  // Миттєвий відгук на зчитування

  // --- Підписаний запит ---
  time_t now;
  time(&now);
  String timestamp = String((unsigned long)now);
  String message   = uidStr + ":" + timestamp;
  String signature = computeHMAC(message, String(HMAC_SECRET));

  Serial.printf("Timestamp: %s | Signature: %s\n",
    timestamp.c_str(), signature.c_str());

  WiFiClientSecure client;
  client.setInsecure();  // skip cert — HMAC guards authenticity
  HTTPClient http;
  String url = String("https://") + SERVER_HOST + ":" + SERVER_PORT + ENDPOINT;
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Timestamp",  timestamp);
  http.addHeader("X-Signature",  signature);

  String jsonBody = "{\"uid\":\"" + uidStr + "\"}";
  int httpCode = http.POST(jsonBody);

  if (httpCode > 0) {
    consecutiveFailures = 0;  // Успішний HTTP — скидаємо лічильник
    String response = http.getString();
    Serial.printf("HTTP %d: %s\n", httpCode, response.c_str());

    if (httpCode == 403) {
      Serial.println("[БЕЗПЕКА] Підпис відхилено сервером.");
      beepError();
    } else if (httpCode == 404) {
      // Картка не прив'язана до жодного студента
      Serial.println("[!] Невідома картка.");
      beepError();
    } else {
      StaticJsonDocument<256> doc;
      if (!deserializeJson(doc, response)) {
        String direction = doc["direction"] | "";
        if (direction == "in") {
          delay(100);
          beepDirection(1);  // 1 сигнал — ВХІД
        } else if (direction == "out") {
          delay(100);
          beepDirection(2);  // 2 сигнали — ВИХІД
        } else {
          beepDirection(1);  // Інший режим (напр. assign)
        }
      } else {
        beepDirection(1);
      }
    }
  } else {
    // HTTP-запит повністю не вдався (немає з'єднання тощо)
    Serial.printf("[ПОМИЛКА] Запит не вдався: %s\n",
      http.errorToString(httpCode).c_str());
    beepError();

    consecutiveFailures++;
    Serial.printf("[ПОМИЛКА] Невдач підряд: %d / %d\n", consecutiveFailures, MAX_FAILURES);

    if (consecutiveFailures >= MAX_FAILURES) {
      Serial.println("[ПЕРЕЗАПУСК] Занадто багато невдач — перезавантаження...");
      delay(1500);
      ESP.restart();  // Повний рестарт → setup() → connectWiFi()
    }
  }

  http.end();
  delay(2000);  // Антидребезг між картками
}
