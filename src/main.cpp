#include <Arduino.h>
#include <ArduinoJson.h> 
#include <WiFi.h>
#include <HTTPClient.h>
#include <fpm.h>
#include <vector>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>


// Oled display data
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1  // Reset pin 

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// WiFi data
const char* ssid = "test_ssid";
const char* password = "test_password";

// Server data
const char* baseServerUrl = "server_ip_or_domain"; // e.g. "http://192.168.1.100:8000"
const char* uploadPath = "/upload";
const char* listPath = "/upload/list";

#define PRINTF_BUF_SZ 60
char printfBuf[PRINTF_BUF_SZ];

#define TEMPLATE_SZ 1024
uint8_t template_buffer[TEMPLATE_SZ];
static uint8_t serverTemplate[TEMPLATE_SZ]; 

// ESP32 uses HardwareSerial, UART2 on GPIO16 (RX2) and GPIO17 (TX2)
HardwareSerial fserial(2);  // UART2

// Fingerprint class
FPM finger(&fserial);
FPMSystemParams params;
uint16_t PACKET_LENGTH = 0;

bool fingerprintCheck(int16_t fid);
uint16_t readTemplate(uint16_t fid, uint8_t * buffer, uint16_t bufLen);
bool sendTemplateToServer(uint16_t fid_on_server, uint8_t* buffer, uint16_t length);
bool downloadTemplateFromServer(const char* url, uint8_t* buffer, size_t* length);
bool getTemplateListFromServer(const char* listUrl, std::vector<String>& templates);
bool uploadServerTemplateToBuffer(uint8_t* data, size_t len, uint8_t bufferId);
void printTemplateBuffer(const uint8_t* buffer, uint16_t totalBytes);
String getServerUrl(const String& path);
bool getFreeId(int16_t * fid);
bool emptyDatabase(void);
void displayMainScreen(void);


void setup()
{
    Serial.begin(115200);
    // Initialization UART2 with RX = GPIO16, TX = GPIO17, speed 57600
    fserial.begin(57600, SERIAL_8N1, 16, 17);

    // Start I2C on default ESP32 pins: SDA=21, SCL=22
    Wire.begin(21, 22); 

    // OLED initialization
    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {  // I2C address 0x3C
        Serial.println(F("SSD1306 allocation failed"));
        while (true); 
    }

    // Display something on the screen
    displayMainScreen();
    
    if (finger.begin()) {
        finger.readParams(&params);
        Serial.println("Found fingerprint sensor!");
        Serial.print("Capacity: "); Serial.println(params.capacity);
        Serial.print("Packet length: "); Serial.println(FPM::packetLengths[static_cast<uint8_t>(params.packetLen)]);
    } 
    else {
        Serial.println("Did not find fingerprint sensor. ");
        while (1) yield();
    }    
    PACKET_LENGTH = FPM::packetLengths[static_cast<uint8_t>(params.packetLen)];

    emptyDatabase();

    Serial.print("Connecting to the WiFi...");
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println(" connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
}
void loop()
{
    Serial.println("\r\nSend any character to enroll a finger...");
    while (Serial.available() == 0) yield();
    
    int16_t fid;
    if (getFreeId(&fid)) 
    {
        fingerprintCheck(fid);
    }
    else 
    {
        Serial.println("No free slot/ID in database!");
    }

    while (Serial.read() != -1);  // clear buffer
}


void printTemplateBuffer(const uint8_t* buffer, uint16_t totalBytes) {
    uint16_t numRows = totalBytes / 16;

    Serial.println(F("Printing template:"));
    const char * dashes = "---------------------------------------------";
    Serial.println(dashes);

    for (int row = 0; row < numRows; row++) {
        for (int col = 0; col < 16; col++) {
            Serial.print(buffer[row * 16 + col], HEX);
            Serial.print(" ");
        }

        Serial.println();
        yield();
    }

    Serial.println(dashes);
    Serial.print(totalBytes); Serial.println(" bytes read.");
}


bool uploadServerTemplateToBuffer(uint8_t* data, size_t len, uint8_t bufferId) {
    FPMStatus status = finger.uploadTemplate(bufferId);
    
    if (status != FPMStatus::OK) {
        Serial.printf("uploadTemplate(%d) failed: 0x%X\n", bufferId, static_cast<uint16_t>(status));
        return false;
    }

    uint16_t writeLen = len;
    uint16_t written = 0;

    while (writeLen) {
        // Last parameter means that this is the last packet
        bool ret = finger.writeDataPacket(data + written, NULL, &writeLen, writeLen <= PACKET_LENGTH);
        
        if (!ret) {
            Serial.printf("writeDataPacket() failed after writing %d bytes\n", written);
            return false;
        }

        written += writeLen;
        writeLen = len - written;

        yield();
    }

    return true;
}

bool emptyDatabase(void) 
{
    FPMStatus status = finger.emptyDatabase();
    
    switch (status) 
    {
        case FPMStatus::OK:
            snprintf(printfBuf, PRINTF_BUF_SZ, "Database empty.");
            Serial.println(printfBuf);
            break;
            
        case FPMStatus::DBCLEARFAIL:
            snprintf(printfBuf, PRINTF_BUF_SZ, "Could not clear sensor database.");
            Serial.println(printfBuf);
            return false;
            
        default:
            snprintf(printfBuf, PRINTF_BUF_SZ, "emptyDatabase(): error 0x%X", static_cast<uint16_t>(status));
            Serial.println(printfBuf);
            return false;
    }
    
    return true;
}

bool getFreeId(int16_t * fid) 
{
    for (int page = 0; page < (params.capacity / FPM_TEMPLATES_PER_PAGE) + 1; page++) 
    {
        FPMStatus status = finger.getFreeIndex(page, fid);
        
        switch (status) 
        {
            case FPMStatus::OK:
                if (*fid != -1) {
                    Serial.print("Free slot at ID ");
                    Serial.println(*fid);
                    return true;
                }
                break;
                
            default:
                snprintf(printfBuf, PRINTF_BUF_SZ, "getFreeIndex(%d): error 0x%X", page, static_cast<uint16_t>(status));
                Serial.println(printfBuf);
                return false;
        }
        
        yield();
    }
    
    Serial.println("No free slots!");
    return false;
}


uint16_t readTemplate(uint16_t fid, uint8_t * buffer, uint16_t bufLen)
{
    // Step 1: Load the template from the sensor's storage into one of its Buffers (Buffer 1 by default) 
    FPMStatus status = finger.loadTemplate(fid);
    
    switch (status) 
    {
        case FPMStatus::OK:
            Serial.print("Template "); Serial.print(fid); Serial.println(" loaded");
            break;
            
        case FPMStatus::DBREADFAIL:
            Serial.println(F("Invalid template or location"));
            return false;
            
        default:
            snprintf_P(printfBuf, PRINTF_BUF_SZ, PSTR("loadTemplate(%d): error 0x%X"), fid, static_cast<uint16_t>(status));
            Serial.println(printfBuf);
            return false;
    }
    
    // Step 2: Tell the sensor to begin transmitting the loaded template (from its internal buffer) to the MCU
    status = finger.downloadTemplate();
    switch (status) 
    {
        case FPMStatus::OK:
            break;
            
        default:
            snprintf_P(printfBuf, PRINTF_BUF_SZ, PSTR("downloadTemplate(%d): error 0x%X"), fid, static_cast<uint16_t>(status));
            Serial.println(printfBuf);
            return false; 
    }
    
    // Step 3: Read buffer in chunks into MCU RAM
    // Now, the sensor will send us the template from that Buffer, one packet at a time 
    bool readComplete = false;
    
    // As an argument, this holds the max number of bytes to read from the sensor.
    // Whenever the function returns successfully, it then holds the number of bytes actually read.
    uint16_t readLen = bufLen;
    
    uint16_t bufPos = 0;

    while (!readComplete) 
    {
        bool ret = finger.readDataPacket(buffer + bufPos, NULL, &readLen, &readComplete);
        
        if (!ret)
        {
            snprintf_P(printfBuf, PRINTF_BUF_SZ, PSTR("readDataPacket(): failed after reading %u bytes"), bufPos);
            Serial.println(printfBuf);
            return 0;
        }
        
        bufPos += readLen;
        readLen = bufLen - bufPos;
        
        yield();
    }
    
    // printTemplateBuffer(buffer, bufPos);
    
    return bufPos;
}


bool sendTemplateToServer(uint16_t fid_on_server, uint8_t* buffer, uint16_t length) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi not connected!");
        return false;
    }
    String uploadUrl = getServerUrl(uploadPath);
    HTTPClient http;
    http.begin(uploadUrl);

    // HTTP Header 
    http.addHeader("Content-Type", "application/octet-stream");

    // Send ID
    http.addHeader("X-Template-ID", String(fid_on_server));

    // Send POST request with data (binary)
    int httpResponseCode = http.POST(buffer, length);

    if (httpResponseCode > 0) {
        Serial.printf("Server answer: %d\n", httpResponseCode);
        String response = http.getString();
        Serial.println(response);
        http.end();
        return (httpResponseCode == 200);
    } else {
        Serial.printf("Error sending: %s\n", http.errorToString(httpResponseCode).c_str());
        http.end();
        return false;
    }
}

bool downloadTemplateFromServer(const char* url, uint8_t* buffer, size_t* length) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi not connected!");
        return false;
    }

    HTTPClient http;
    WiFiClient client;

    if (!http.begin(client, url)) {
        Serial.println("http.begin failed!");
        return false;
    }

    int httpCode = http.GET();
    if (httpCode == 200) {
        WiFiClient* stream = http.getStreamPtr();
        size_t totalSize = http.getSize();
        
        // if (totalSize > TEMPLATE_SZ) {
        //     Serial.println("File is bigger than buffer! Stop.");
        //     http.end();
        //     return false;
        // }

        *length = 0;
        while (http.connected() && *length < totalSize) {
            if (stream->available()) {
                buffer[*length] = stream->read();
                (*length)++;
            }
            yield();
        }

        Serial.printf("Downloaded %d byte.\n", *length);
        http.end();
        return true;
    } else {
        Serial.printf("GET error: %d\n", httpCode);
        http.end();
        return false;
    }
}

bool getTemplateListFromServer(const char* listUrl, std::vector<String>& templates) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi not connected!");
        return false;
    }

    HTTPClient http;
    WiFiClient client;

    if (!http.begin(client, listUrl)) {
        Serial.println("http.begin failed!");
        return false;
    }

    int httpCode = http.GET();
    if (httpCode != 200) {
        Serial.printf("GET error: %d\n", httpCode);
        http.end();
        return false;
    }

    String payload = http.getString();
    http.end();

    DynamicJsonDocument doc(2048);
    DeserializationError error = deserializeJson(doc, payload);
    if (error) {
        Serial.println("Error with parsing JSON!");
        return false;
    }

    for (JsonVariant v : doc.as<JsonArray>()) {
        templates.push_back(v.as<String>());
    }

    return true;
}

String getServerUrl(const String& path) {
    String url = String(baseServerUrl);
    if (!url.endsWith("/")) {
        url += "/";
    }
    if (path.startsWith("/")) {
        url += path.substring(1);
    } else {
        url += path;
    }
    return url;
}

bool fingerprintCheck(int16_t fid) 
{
    FPMStatus status;
    const int NUM_SNAPSHOTS = 2;
    for (int i = 0; i < NUM_SNAPSHOTS; i++)
    {
        Serial.println(i == 0 ? "Place a finger" : "Place same finger again");
        //Serial.println("Place a finger.");
    
        // Take snapshots of the finger, and extract the fingerprint features from each image.
        do {           
            status = finger.getImage();

            switch (status) 
            {
                case FPMStatus::OK:
                    Serial.println("Image taken");
                    break;
                    
                case FPMStatus::NOFINGER:
                    Serial.println(".");
                    break;
                    
                default:
                    // Allow retries even when an error happens 
                    snprintf(printfBuf, PRINTF_BUF_SZ, "getImage(): error 0x%X", static_cast<uint16_t>(status));
                    
                    Serial.println(printfBuf);
                    break;
            }
            
            yield();
        }
    
        while (status != FPMStatus::OK);

        status = finger.image2Tz(i+1);
    
        switch (status) 
        {
            case FPMStatus::OK:
                Serial.println("Image converted");
                break;
                
            default:
                snprintf(printfBuf, PRINTF_BUF_SZ, "image2Tz(%d): error 0x%X", i+1, static_cast<uint16_t>(status));
                Serial.println(printfBuf);
                return false;
        }

        Serial.println("Remove finger");
        delay(1000);
        do {

            status = finger.getImage();
            delay(200);
        }
        while (status != FPMStatus::NOFINGER);
    }

    // Images have been taken and converted into features a.k.a character files.
    // Now, need to create a model/template from these features
    status = finger.generateTemplate();
    switch (status)
    {
        case FPMStatus::OK:
            Serial.println("Template created from matching prints!");
            break;
            
        case FPMStatus::ENROLLMISMATCH:
            Serial.println("The prints do not match!");
            return false;
            
        default:
            snprintf(printfBuf, PRINTF_BUF_SZ, "createModel(): error 0x%X", static_cast<uint16_t>(status));
            Serial.println(printfBuf);
            return false;
    }

    std::vector<String> serverTemplates;
    String listUrl = getServerUrl(listPath);

    if (!getTemplateListFromServer(listUrl.c_str(), serverTemplates)) {
        Serial.println("Can't get list of files from the server.");
        return false;
    }
    int fid_on_server = serverTemplates.size(); // Keep track on number of files already on the server

    for (const auto& filename : serverTemplates) {

        String fileUrl = getServerUrl(uploadPath) + "/" + filename;

        Serial.println("Try with file: " + fileUrl);

        size_t len = 0;
        if (!downloadTemplateFromServer(fileUrl.c_str(), serverTemplate, &len)) {
            Serial.println("Error downloading.");
            continue;
        }

        if (!uploadServerTemplateToBuffer(serverTemplate, len, 2)) {
            Serial.println("Error upolading into buffer.");
            continue;
        }

        uint16_t score;
        FPMStatus status = finger.matchTemplatePair(&score);

        if (status == FPMStatus::OK) {
            Serial.printf("MATCH! File: %s | Score: %d\n", filename.c_str(), score);
            return true;
        } else if (status == FPMStatus::NOMATCH) {
            Serial.printf("No match with %s | Score: %d\n", filename.c_str(), score);
           
        } else {
            Serial.printf("Error with comparison with %s: 0x%X\n", filename.c_str(), static_cast<uint16_t>(status));
        }

        yield();
    }

    Serial.println("Fingerprint didn't have a match.");
    
    status = finger.storeTemplate(fid);
    switch (status)
    {
        case FPMStatus::OK:
            snprintf(printfBuf, PRINTF_BUF_SZ, "Template stored at ID %d!", fid);
            Serial.println(printfBuf);
            break;
            
        case FPMStatus::BADLOCATION:
            snprintf(printfBuf, PRINTF_BUF_SZ, "Could not store in that location %d!", fid);
            Serial.println(printfBuf);
            return false;
            
        default:
            snprintf(printfBuf, PRINTF_BUF_SZ, "storeTemplate(): error 0x%X", static_cast<uint16_t>(status));
            Serial.println(printfBuf);
            return false;
    }

    // Read the template from its location into the buffer
    uint16_t totalRead = readTemplate(fid, template_buffer, TEMPLATE_SZ);
    if (!totalRead) return false;
    
    // Send to the server
    if (sendTemplateToServer(fid_on_server, template_buffer, totalRead)) {
        Serial.println("Template sent to the server!");
    } else {
        Serial.println("Sending template failed.");
    }

    return true;
}

// Display main screen
void displayMainScreen() {
    display.clearDisplay();

    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 10);
    display.println("Welcome!");
    display.println("Place your finger");

    display.display();
}



