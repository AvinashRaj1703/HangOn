package com.sos112.system;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.util.Base64;
import android.util.Log;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.TimeZone;
import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

public class SosForegroundService extends Service implements LocationListener {

    private static final String TAG = "SosForegroundService";
    private static final String CHANNEL_ID = "sos_persistent_channel";
    private static final int NOTIFICATION_ID = 112001;

    public static final String ACTION_START = "ACTION_START_SOS";
    public static final String ACTION_STOP = "ACTION_STOP_SOS";
    public static final String EXTRA_SERVER_URL = "EXTRA_SERVER_URL";
    public static final String EXTRA_TARGET_ID = "EXTRA_TARGET_ID";

    private PowerManager.WakeLock wakeLock;
    private LocationManager locationManager;
    private OkHttpClient httpClient;
    private WebSocket webSocket;
    private String serverWsUrl = "wss://hangon-k31m.onrender.com/ws/target/";
    private String targetId = "T-APP-" + System.currentTimeMillis();

    private boolean isSosActive = false;
    private boolean isRecordingAudio = false;
    private Thread audioThread;
    private Handler reconnectHandler;

    @Override
    public void onCreate() {
        super.onCreate();
        reconnectHandler = new Handler(Looper.getMainLooper());
        acquireWakeLock();
        createNotificationChannel();
        initLocationManager();
    }

    private void acquireWakeLock() {
        try {
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            if (pm != null) {
                wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "SosSystem:KeepAliveLock");
                wakeLock.acquire(24 * 60 * 60 * 1000L); // 24 hours
            }
        } catch (Exception e) {
            Log.e(TAG, "Error acquiring wake lock", e);
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "112 SOS Active Emergency System",
                    NotificationManager.IMPORTANCE_HIGH
            );
            channel.setDescription("Continuous Emergency GPS & Audio Streaming (Persistence Active)");
            channel.enableVibration(true);
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }
    }

    private Notification buildNotification() {
        Intent notificationIntent = new Intent(this, MainActivity.class);
        notificationIntent.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this, 0, notificationIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M ? PendingIntent.FLAG_IMMUTABLE : 0)
        );

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("🚨 112 SOS EMERGENCY BROADCAST ACTIVE")
                .setContentText("Continuous Live GPS & Audio Streaming active in background")
                .setSmallIcon(android.R.drawable.stat_notify_more)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_MAX)
                .setCategory(NotificationCompat.CATEGORY_ALARM)
                .setContentIntent(pendingIntent)
                .build();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null) {
            String action = intent.getAction();
            if (ACTION_STOP.equals(action)) {
                stopSosBroadcasting();
                stopForeground(true);
                stopSelf();
                return START_NOT_STICKY;
            }

            if (intent.hasExtra(EXTRA_SERVER_URL)) {
                String extraUrl = intent.getStringExtra(EXTRA_SERVER_URL);
                if (extraUrl != null && !extraUrl.isEmpty()) {
                    if (extraUrl.startsWith("ws://") && extraUrl.contains("render.com")) {
                        extraUrl = extraUrl.replace("ws://", "wss://");
                    }
                    serverWsUrl = extraUrl;
                }
            }
            if (intent.hasExtra(EXTRA_TARGET_ID)) {
                targetId = intent.getStringExtra(EXTRA_TARGET_ID);
            }
        }

        try {
            Notification notification = buildNotification();
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                try {
                    startForeground(NOTIFICATION_ID, notification,
                            ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION | ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
                } catch (Exception fgsEx) {
                    Log.w(TAG, "Fallback startForeground without strict types: " + fgsEx.getMessage());
                    try {
                        startForeground(NOTIFICATION_ID, notification);
                    } catch (Exception fallbackEx) {
                        Log.e(TAG, "Critical startForeground fallback failed", fallbackEx);
                    }
                }
            } else {
                startForeground(NOTIFICATION_ID, notification);
            }
        } catch (Exception e) {
            Log.e(TAG, "Notification startForeground failed: " + e.getMessage());
        }

        try {
            startSosBroadcasting();
        } catch (Exception e) {
            Log.e(TAG, "Error in startSosBroadcasting", e);
        }
        return START_STICKY;
    }

    private void startSosBroadcasting() {
        if (isSosActive) return;
        isSosActive = true;

        connectWebSocket();
        startLocationTracking();
        startAudioStreaming();
    }

    private void stopSosBroadcasting() {
        isSosActive = false;
        stopLocationTracking();
        stopAudioStreaming();
        if (webSocket != null) {
            try {
                webSocket.close(1000, "SOS Disarmed");
            } catch (Exception ignored) {}
            webSocket = null;
        }
    }

    private void connectWebSocket() {
        if (!isSosActive) return;

        try {
            if (httpClient == null) {
                httpClient = new OkHttpClient.Builder()
                        .pingInterval(5, TimeUnit.SECONDS)
                        .retryOnConnectionFailure(true)
                        .build();
            }

            String fullUrl = serverWsUrl;
            if (fullUrl.startsWith("ws://") && fullUrl.contains("render.com")) {
                fullUrl = fullUrl.replace("ws://", "wss://");
            }
            if (!fullUrl.endsWith("/")) fullUrl += "/";
            fullUrl += targetId;

            Request request = new Request.Builder().url(fullUrl).build();
            webSocket = httpClient.newWebSocket(request, new WebSocketListener() {
                @Override
                public void onOpen(WebSocket ws, Response response) {
                    Log.d(TAG, "Native SOS WebSocket Connected to " + serverWsUrl);
                    // Send initial handshake / SOS alert signal recognized by server
                    try {
                        JSONObject sosMsg = new JSONObject();
                        sosMsg.put("type", "sos_alert");
                        sosMsg.put("is_sos", true);
                        sosMsg.put("targetId", targetId);
                        sosMsg.put("mode", "native_background_persistence");
                        ws.send(sosMsg.toString());
                    } catch (Exception e) {
                        Log.e(TAG, "Handshake error", e);
                    }
                }

                @Override
                public void onMessage(WebSocket ws, String text) {
                    Log.d(TAG, "Server command received: " + text);
                }

                @Override
                public void onFailure(WebSocket ws, Throwable t, @Nullable Response response) {
                    Log.w(TAG, "WebSocket failure, scheduling reconnect in 3s...", t);
                    scheduleReconnect();
                }

                @Override
                public void onClosed(WebSocket ws, int code, String reason) {
                    Log.d(TAG, "WebSocket closed: " + reason);
                    if (isSosActive) scheduleReconnect();
                }
            });
        } catch (Exception e) {
            Log.e(TAG, "Error connecting WebSocket", e);
            scheduleReconnect();
        }
    }

    private void scheduleReconnect() {
        if (!isSosActive) return;
        reconnectHandler.postDelayed(() -> {
            if (isSosActive) connectWebSocket();
        }, 3000);
    }

    private void initLocationManager() {
        locationManager = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
    }

    private void startLocationTracking() {
        if (locationManager == null) return;
        try {
            if (locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                locationManager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 1000L, 1.0f, this);
            }
            if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                locationManager.requestLocationUpdates(LocationManager.NETWORK_PROVIDER, 1000L, 1.0f, this);
            }
        } catch (SecurityException se) {
            Log.e(TAG, "Location permission missing", se);
        }
    }

    private void stopLocationTracking() {
        if (locationManager != null) {
            try {
                locationManager.removeUpdates(this);
            } catch (SecurityException ignored) {}
        }
    }

    @Override
    public void onLocationChanged(Location loc) {
        if (!isSosActive || loc == null) return;

        try {
            JSONObject gpsObj = new JSONObject();
            gpsObj.put("lat", loc.getLatitude());
            gpsObj.put("lng", loc.getLongitude());
            gpsObj.put("accuracy", Math.round(loc.getAccuracy()));
            gpsObj.put("speed", loc.getSpeed());
            gpsObj.put("heading", loc.getBearing());
            gpsObj.put("alt", loc.getAltitude());

            SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US);
            sdf.setTimeZone(TimeZone.getTimeZone("UTC"));
            gpsObj.put("timestamp", sdf.format(new Date(loc.getTime())));

            JSONObject payload = new JSONObject();
            payload.put("type", "gps_update");
            payload.put("is_sos", true);
            payload.put("target_id", targetId);
            payload.put("gps", gpsObj);

            if (webSocket != null) {
                webSocket.send(payload.toString());
            }
        } catch (Exception e) {
            Log.e(TAG, "Error packaging GPS update", e);
        }
    }

    @Override public void onStatusChanged(String provider, int status, Bundle extras) {}
    @Override public void onProviderEnabled(String provider) {}
    @Override public void onProviderDisabled(String provider) {}

    private void startAudioStreaming() {
        isRecordingAudio = true;
        audioThread = new Thread(() -> {
            int sampleRate = 16000;
            int channelConfig = AudioFormat.CHANNEL_IN_MONO;
            int audioFormat = AudioFormat.ENCODING_PCM_16BIT;
            int bufferSize = AudioRecord.getMinBufferSize(sampleRate, channelConfig, audioFormat);
            if (bufferSize <= 0) bufferSize = 2048;

            AudioRecord recorder = null;
            try {
                recorder = new AudioRecord(
                        MediaRecorder.AudioSource.MIC,
                        sampleRate,
                        channelConfig,
                        audioFormat,
                        bufferSize * 2
                );

                if (recorder.getState() != AudioRecord.STATE_INITIALIZED) {
                    Log.e(TAG, "AudioRecord not initialized");
                    return;
                }

                recorder.startRecording();
                byte[] audioBuffer = new byte[bufferSize];

                while (isRecordingAudio && isSosActive) {
                    int readBytes = recorder.read(audioBuffer, 0, audioBuffer.length);
                    if (readBytes > 0 && webSocket != null) {
                        String b64Audio = Base64.encodeToString(audioBuffer, 0, readBytes, Base64.NO_WRAP);
                        JSONObject audioPayload = new JSONObject();
                        audioPayload.put("type", "audio_stream");
                        audioPayload.put("target_id", targetId);
                        audioPayload.put("data", b64Audio);
                        audioPayload.put("rate", sampleRate);
                        webSocket.send(audioPayload.toString());
                    }
                    Thread.sleep(100);
                }
            } catch (Exception e) {
                Log.e(TAG, "Audio streaming background loop error", e);
            } finally {
                if (recorder != null) {
                    try {
                        recorder.stop();
                        recorder.release();
                    } catch (Exception ignored) {}
                }
            }
        });
        audioThread.setPriority(Thread.MAX_PRIORITY);
        audioThread.start();
    }

    private void stopAudioStreaming() {
        isRecordingAudio = false;
        if (audioThread != null) {
            audioThread.interrupt();
            audioThread = null;
        }
    }

    @Override
    public void onDestroy() {
        stopSosBroadcasting();
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
