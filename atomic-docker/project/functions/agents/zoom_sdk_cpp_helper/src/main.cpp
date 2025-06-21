#include "zoom_sdk_helper.h"
#include <iostream>
#include <string>
#include <vector>
#include <algorithm> // For std::transform

// Helper function to parse command line arguments
bool getCmdOption(char **begin, char **end, const std::string &option, std::string &value) {
    char **itr = std::find(begin, end, option);
    if (itr != end && ++itr != end) {
        value = *itr;
        return true;
    }
    return false;
}

bool cmdOptionExists(char** begin, char** end, const std::string& option) {
    return std::find(begin, end, option) != end;
}

void printUsage() {
    std::cerr << "Usage: zoom_sdk_helper --meeting_id <ID> --token <SDK_JWT> [--password <PASSWORD>] [--sample_rate <RATE>] [--channels <CHANNELS>]" << std::endl;
    std::cerr << "Required arguments:" << std::endl;
    std::cerr << "  --meeting_id <ID>         Zoom Meeting ID." << std::endl;
    std::cerr << "  --token <SDK_JWT>         SDK JWT for authentication." << std::endl;
    std::cerr << "Optional arguments:" << std::endl;
    std::cerr << "  --password <PASSWORD>     Meeting password, if any." << std::endl;
    std::cerr << "  --sample_rate <RATE>      Desired audio sample rate (e.g., 16000, 32000, 48000). Default: 16000." << std::endl;
    std::cerr << "  --channels <CHANNELS>       Desired audio channels (e.g., 1 for mono, 2 for stereo). Default: 1." << std::endl;
    std::cerr << "  --help                    Print this usage information." << std::endl;
}

int main(int argc, char *argv[]) {
    std::string meeting_id_str;
    std::string sdk_jwt_token_str;
    std::string meeting_password_str; // Optional
    std::string sample_rate_str = "16000"; // Default
    std::string channels_str = "1";    // Default

    if (cmdOptionExists(argv, argv + argc, "--help") || cmdOptionExists(argv, argv+argc, "-h")) {
        printUsage();
        return 0;
    }

    if (!getCmdOption(argv, argv + argc, "--meeting_id", meeting_id_str)) {
        std::cerr << "Error: --meeting_id is required." << std::endl;
        printUsage();
        return 1;
    }

    if (!getCmdOption(argv, argv + argc, "--token", sdk_jwt_token_str)) {
        std::cerr << "Error: --token is required." << std::endl;
        printUsage();
        return 1;
    }

    getCmdOption(argv, argv + argc, "--password", meeting_password_str); // Optional
    getCmdOption(argv, argv + argc, "--sample_rate", sample_rate_str); // Optional, with default
    getCmdOption(argv, argv + argc, "--channels", channels_str);       // Optional, with default

    uint32_t sample_rate = 16000;
    uint32_t channels = 1;

    try {
        sample_rate = std::stoul(sample_rate_str);
        channels = std::stoul(channels_str);
    } catch (const std::exception& e) {
        std::cerr << "Error: Invalid number for sample_rate or channels: " << e.what() << std::endl;
        printUsage();
        return 1;
    }

    if (channels != 1 && channels != 2) {
        std::cerr << "Error: --channels must be 1 (mono) or 2 (stereo)." << std::endl;
        printUsage();
        return 1;
    }
    // Add more validation for sample_rate if needed (e.g., common values)


    std::cerr << "Starting Zoom SDK Helper..." << std::endl;
    std::cerr << "  Meeting ID: " << meeting_id_str << std::endl;
    std::cerr << "  Token: " << (sdk_jwt_token_str.empty() ? "Not provided (Error)" : "[Token Provided]") << std::endl;
    if (!meeting_password_str.empty()) {
        std::cerr << "  Password: [Password Provided]" << std::endl;
    }
    std::cerr << "  Sample Rate: " << sample_rate << std::endl;
    std::cerr << "  Channels: " << channels << std::endl;


    ZoomSdkHelperApp app;

    if (!app.initializeSDK(sdk_jwt_token_str)) {
        std::cerr << "Failed to initialize or authenticate SDK." << std::endl;
        return 2;
    }

    // Authentication is now called within initializeSDK in this simulated version
    // if (!app.authenticateWithJwt(sdk_jwt_token_str)) {
    //     std::cerr << "Failed to authenticate with SDK JWT." << std::endl;
    //     return 3;
    // }

    if (!app.joinMeeting(meeting_id_str, meeting_password_str, sample_rate, channels)) {
        std::cerr << "Failed to join meeting." << std::endl;
        // app.cleanupSDK() will be called by destructor
        return 4;
    }

    // The run method will block until the meeting ends or an error occurs
    app.run();

    std::cerr << "Zoom SDK Helper finished." << std::endl;
    return 0; // Success
}
