#include "zoom_sdk_helper.h"
#include <iostream> // For cerr, cout
#include <vector>
#include <cstring>    // For strcmp, strncpy
#include <csignal>    // For signal handling
#include <chrono>
#include <thread>     // For std::this_thread::sleep_for

// --- Global application instance and signal handling ---
namespace {
    std::atomic<bool> g_terminate_flag(false);
    ZoomSdkHelperApp* g_app_instance = nullptr;

    void signalHandler(int signum) {
        std::cerr << "Signal " << signum << " received. Shutting down." << std::endl;
        if (g_app_instance) {
            g_app_instance->leaveMeeting(); // Attempt graceful leave
        }
        g_terminate_flag.store(true);
        // Potentially notify app_cv if used in main run loop outside of class
    }
} // namespace

// --- ZoomSdkHelperApp Implementation ---

ZoomSdkHelperApp::ZoomSdkHelperApp() {
    g_app_instance = this;
    // In a real SDK, we might register 'this' as the audio data receiver.
    // raw_audio_receiver_ = this; // If ZoomSdkHelperApp itself implements IAudioRawDataReceiver
}

ZoomSdkHelperApp::~ZoomSdkHelperApp() {
    cleanupSDK();
    g_app_instance = nullptr;
}

bool ZoomSdkHelperApp::initializeSDK(const std::string& sdk_jwt_token) {
    if (sdk_initialized_) {
        std::cerr << "SDK already initialized." << std::endl;
        return true;
    }

    std::cerr << "Initializing Zoom SDK (Simulation)..." << std::endl;
    // In a real SDK:
    // ZOOMSDK::SDKInitContext init_context;
    // init_context.language_id = "en-US";
    // ... other params like domain, enable_logging etc.
    // ZOOMSDK::SDKError err = ZOOMSDK::Initialize(init_context);
    // if (err != ZOOMSDK::SDKERR_SUCCESS) {
    //     std::cerr << "Failed to initialize SDK. Error: " << err << std::endl;
    //     return false;
    // }
    // auth_service_ = ZOOMSDK::GetAuthService(); // Get auth service instance
    // meeting_service_ = ZOOMSDK::GetMeetingService(); // Get meeting service
    // if(auth_service_) auth_service_->SetEvent(this); // Register for auth events
    // if(meeting_service_) meeting_service_->SetEvent(this); // Register for meeting events

    // Simulate success
    auth_service_ = reinterpret_cast<void*>(0x1); // Dummy non-null pointer
    meeting_service_ = reinterpret_cast<void*>(0x1); // Dummy non-null pointer
    sdk_initialized_ = true;
    std::cerr << "Zoom SDK initialized successfully (Simulation)." << std::endl;

    // After SDK init, proceed to authentication
    return authenticateWithJwt(sdk_jwt_token);
}

bool ZoomSdkHelperApp::authenticateWithJwt(const std::string& sdk_jwt_token) {
    if (!sdk_initialized_) {
        std::cerr << "SDK not initialized. Cannot authenticate." << std::endl;
        return false;
    }
    if (authenticated_) {
        std::cerr << "Already authenticated." << std::endl;
        return true;
    }

    std::cerr << "Authenticating with SDK JWT (Simulation)..." << std::endl;
    // In a real SDK:
    // if (!auth_service_) return false;
    // ZOOMSDK::AuthContext auth_context;
    // auth_context.jwt_token = sdk_jwt_token.c_str();
    // ZOOMSDK::SDKError err = ((ZOOMSDK::IAuthService*)auth_service_)->SDKAuth(auth_context);
    // if (err != ZOOMSDK::SDKERR_SUCCESS) {
    //     std::cerr << "SDK Authentication failed. Error: " << err << std::endl;
    //     return false;
    // }
    // The actual result comes via onAuthenticationReturn callback.
    // Here, we'll simulate a successful callback directly for simplicity.
    onAuthenticationReturn(ZOOMSDK::SDKERR_SUCCESS);
    return authenticated_.load();
}


void ZoomSdkHelperApp::onAuthenticationReturn(ZOOMSDK::SDKError ret) {
    if (ret == ZOOMSDK::SDKERR_SUCCESS) {
        std::cerr << "SDK Authentication successful." << std::endl;
        authenticated_ = true;
    } else {
        std::cerr << "SDK Authentication failed. Error code: " << ret << std::endl;
        authenticated_ = false;
        // Consider signaling failure to the main thread if it's waiting
        g_terminate_flag.store(true); // Terminate if auth fails
    }
    app_cv_.notify_all(); // Notify main thread if it's waiting
}

bool ZoomSdkHelperApp::joinMeeting(const std::string& meeting_id, const std::string& meeting_password,
                                 uint32_t desired_sample_rate, uint32_t desired_channels) {
    if (!authenticated_) {
        std::cerr << "Not authenticated. Cannot join meeting." << std::endl;
        return false;
    }
    if (in_meeting_) {
        std::cerr << "Already in a meeting." << std::endl;
        return true;
    }

    current_meeting_id_ = meeting_id;
    current_sample_rate_ = desired_sample_rate;
    current_channels_ = desired_channels;

    std::cerr << "Joining meeting: " << meeting_id << " (Simulation)..." << std::endl;
    // In a real SDK:
    // if(!meeting_service_) return false;
    // ZOOMSDK::JoinMeetingContext join_context;
    // join_context.meeting_number = meeting_id.c_str();
    // join_context.meeting_password = meeting_password.empty() ? nullptr : meeting_password.c_str();
    // join_context.display_name = "AtomAudioCapture";
    // ZOOMSDK::SDKError err = ((ZOOMSDK::IMeetingService*)meeting_service_)->JoinMeeting(join_context);
    // if (err != ZOOMSDK::SDKERR_SUCCESS) {
    //    std::cerr << "Failed to start joining meeting. Error: " << err << std::endl;
    //    return false;
    // }
    // Actual join status comes via onMeetingStatusChanged callback
    // Simulate successful join leading to status change
    onMeetingStatusChanged(/*ZOOMSDK::MEETING_STATUS_INMEETING*/ 3, ZOOMSDK::SDKERR_SUCCESS);
    return in_meeting_.load();
}

void ZoomSdkHelperApp::onMeetingStatusChanged(int status, int error_code) {
    std::cerr << "Meeting status changed. Status: " << status << ", Error: " << error_code << std::endl;
    // Example status codes (these would be defined in actual Zoom SDK headers)
    // enum SDKMeetingStatus {
    //     MEETING_STATUS_IDLE = 0,
    //     MEETING_STATUS_CONNECTING,
    //     MEETING_STATUS_WAITINGFORHOST,
    //     MEETING_STATUS_INMEETING,
    //     MEETING_STATUS_DISCONNECTING,
    //     MEETING_STATUS_RECONNECTING,
    //     // ... and more
    // };
    switch (status) {
        case 0: // IDLE (e.g. after leaving a meeting)
            if (in_meeting_) { // if we were previously in a meeting
                 std::cerr << "Left meeting." << std::endl;
                 internalUnsubscribeFromAudio(); // Simulation
            }
            in_meeting_ = false;
            break;
        case 3: // INMEETING (example value)
            if (error_code == ZOOMSDK::SDKERR_SUCCESS) {
                std::cerr << "Successfully joined meeting: " << current_meeting_id_ << std::endl;
                in_meeting_ = true;
                // Attempt to subscribe to raw audio
                if (internalSubscribeToAudio() != ZOOMSDK::SDKERR_SUCCESS) {
                    std::cerr << "Failed to subscribe to audio after joining meeting." << std::endl;
                    leaveMeeting(); // Leave if audio subscription fails
                    g_terminate_flag.store(true); // Signal main loop to exit
                } else {
                     std::cerr << "Successfully subscribed to raw audio data." << std::endl;
                }
            } else {
                std::cerr << "Error while in meeting or joining. Error code: " << error_code << std.endl;
                in_meeting_ = false;
                 g_terminate_flag.store(true); // Signal main loop to exit on error
            }
            break;
        case 1: // CONNECTING
             std::cerr << "Meeting status: Connecting..." << std::endl;
             break;
        default:
            if (error_code != ZOOMSDK::SDKERR_SUCCESS) {
                std::cerr << "Meeting error. Status: " << status << ", Error: " << error_code << std::endl;
                in_meeting_ = false; // Assume error means not in meeting or connection lost
                g_terminate_flag.store(true); // Exit on meeting errors
            }
            break;
    }
    app_cv_.notify_all(); // Notify main thread if it's waiting
}


ZOOMSDK::SDKError ZoomSdkHelperApp::internalSubscribeToAudio() {
    std::cerr << "Subscribing to raw audio (Simulation)..." << std::endl;
    // In a real SDK:
    // if (!meeting_service_) return ZOOMSDK::SDKERR_MEETING_NOT_JOINED;
    // auto* meeting_audio_ctrl = ((ZOOMSDK::IMeetingService*)meeting_service_)->GetMeetingAudioController();
    // if (meeting_audio_ctrl) {
    //     // Assuming ZoomSdkHelperApp itself inherits IAudioRawDataReceiver
    //     // or has a member that does.
    //     ZOOMSDK::SDKError err = meeting_audio_ctrl->SubsribeAudioRawData(this /*IAudioRawDataReceiver*/);
    //     return err;
    // }
    // return ZOOMSDK::SDKERR_SERVICE_FAILED;
    audio_ctrl_ = reinterpret_cast<void*>(0x1); // Simulate getting audio controller
    return ZOOMSDK::SDKERR_SUCCESS;
}

ZOOMSDK::SDKError ZoomSdkHelperApp::internalUnsubscribeFromAudio() {
    std::cerr << "Unsubscribing from raw audio (Simulation)..." << std::endl;
    // In a real SDK:
    // if (audio_ctrl_ && meeting_service_){
    //    auto* meeting_audio_ctrl = ((ZOOMSDK::IMeetingService*)meeting_service_)->GetMeetingAudioController();
    //    if(meeting_audio_ctrl) meeting_audio_ctrl->UnSubsribeAudioRawData(this);
    // }
    audio_ctrl_ = nullptr;
    return ZOOMSDK::SDKERR_SUCCESS;
}


// This would be the actual callback from Zoom SDK in a real scenario
// void ZoomSdkHelperApp::onMixedAudioRawDataReceived(ZOOMSDK::AudioRawData* data) {
//    if (data && data->buffer && data->buffer_len > 0) {
//        processAudioData(data->buffer, data->buffer_len, data->sample_rate, data->channel_num);
//    }
// }
// void ZoomSdkHelperApp::onOneWayAudioRawDataReceived(ZOOMSDK::AudioRawData* data, uint32_t node_id) {
//    // Similar handling, perhaps with node_id if needed
//    if (data && data->buffer && data->buffer_len > 0) {
//        processAudioData(data->buffer, data->buffer_len, data->sample_rate, data->channel_num);
//    }
// }

void ZoomSdkHelperApp::processAudioData(const char* data, int data_len, int sample_rate, int channels) {
    // Output raw audio data to stdout
    // std::cout.write outputs binary data.
    // Ensure that cout is not buffered in a way that delays output significantly.
    // For binary data, it's often better to use platform-specific ways to set stdout to binary mode if needed,
    // but for Linux, direct write is usually fine.
    if (data && data_len > 0) {
        std::cout.write(data, data_len);
        std::cout.flush(); // Ensure data is sent immediately
        // std::cerr << "Sent " << data_len << " bytes of audio data. SR:" << sample_rate << " CH:" << channels << std::endl;
    }
}

void ZoomSdkHelperApp::leaveMeeting() {
    if (!in_meeting_ || !sdk_initialized_) {
        // std::cerr << "Not in a meeting or SDK not initialized. Cannot leave." << std::endl;
        return;
    }
    std::cerr << "Leaving meeting (Simulation)..." << std::endl;
    // In a real SDK:
    // if (meeting_service_) {
    //    ZOOMSDK::SDKError err = ((ZOOMSDK::IMeetingService*)meeting_service_)->LeaveMeeting(ZOOMSDK::END_MEETING); // or LEAVE_MEETING
    //    if (err != ZOOMSDK::SDKERR_SUCCESS) {
    //        std::cerr << "Failed to leave meeting. Error: " << err << std::endl;
    //    }
    // }
    internalUnsubscribeFromAudio(); // Ensure audio is stopped
    in_meeting_ = false;
    // Simulate meeting status change to IDLE after leaving
    onMeetingStatusChanged(/* ZOOMSDK::MEETING_STATUS_IDLE */ 0, ZOOMSDK::SDKERR_SUCCESS);
    stop_requested_ = true; // Signal main loop to stop
    app_cv_.notify_all();
}

void ZoomSdkHelperApp::cleanupSDK() {
    if (sdk_initialized_) {
        std::cerr << "Cleaning up Zoom SDK (Simulation)..." << std::endl;
        // In a real SDK:
        // if (auth_service_) auth_service_->SetEvent(nullptr);
        // if (meeting_service_) meeting_service_->SetEvent(nullptr);
        // ZOOMSDK::CleanUp();
        sdk_initialized_ = false;
        auth_service_ = nullptr;
        meeting_service_ = nullptr;
        audio_ctrl_ = nullptr;
        std::cerr << "Zoom SDK cleaned up (Simulation)." << std::endl;
    }
}

void ZoomSdkHelperApp::mockSdkEventLoop() {
    std::cerr << "Mock SDK event loop started." << std::endl;
    // This loop simulates the SDK providing audio data periodically
    // It only runs if we are "in a meeting" and "subscribed to audio"
    auto last_audio_time = std::chrono::steady_clock::now();

    while (in_meeting_ && audio_ctrl_ && !g_terminate_flag.load() && !stop_requested_.load()) {
        auto current_time = std::chrono::steady_clock::now();
        if (std::chrono::duration_cast<std::chrono::milliseconds>(current_time - last_audio_time).count() >= 100) { // Every 100ms
            // Simulate receiving a chunk of audio data (e.g., 100ms of 16kHz, 16-bit mono audio)
            int bytes_per_sample = 2; // 16-bit
            int samples_to_send = current_sample_rate_ / 10; // 100ms worth of samples
            int data_len = samples_to_send * current_channels_ * bytes_per_sample;

            std::vector<char> mock_audio_data(data_len, 0); // Create silence
            // For testing, could fill with a simple sine wave or noise
            processAudioData(mock_audio_data.data(), data_len, current_sample_rate_, current_channels_);
            last_audio_time = current_time;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10)); // Check conditions periodically
    }
    std::cerr << "Mock SDK event loop finished." << std::endl;
}

void ZoomSdkHelperApp::run() {
    // Setup signal handlers
    signal(SIGINT, signalHandler);
    signal(SIGTERM, signalHandler);

    // Wait until in meeting, or stop is requested (e.g. auth failed)
    {
        std::unique_lock<std::mutex> lock(app_mutex_);
        app_cv_.wait(lock, [this]{ return (in_meeting_.load() && authenticated_.load()) || g_terminate_flag.load() || stop_requested_.load(); });
    }

    if (in_meeting_.load() && authenticated_.load() && !g_terminate_flag.load() && !stop_requested_.load()) {
        std::cerr << "Application run loop started. In meeting." << std::endl;
        mock_sdk_thread_ = std::thread(&ZoomSdkHelperApp::mockSdkEventLoop, this);

        // Keep main thread alive, waiting for termination signal or meeting end
        std::unique_lock<std::mutex> lock(app_mutex_);
        app_cv_.wait(lock, [this]{ return g_terminate_flag.load() || stop_requested_.load() || !in_meeting_.load(); });

        if (mock_sdk_thread_.joinable()) {
            mock_sdk_thread_.join();
        }
        std::cerr << "Application run loop finished." << std::endl;

    } else {
         std::cerr << "Application will not enter main run loop. Conditions not met (in_meeting="
                   << in_meeting_.load() << ", authenticated=" << authenticated_.load()
                   << ", g_terminate_flag=" << g_terminate_flag.load()
                   << ", stop_requested=" << stop_requested_.load() << ")" << std::endl;
    }

    // Ensure cleanup happens if not already triggered by leaveMeeting
    if (in_meeting_.load()) { // If still in meeting (e.g. g_terminate_flag was set externally)
        leaveMeeting();
    }
    cleanupSDK(); // General SDK cleanup
}
