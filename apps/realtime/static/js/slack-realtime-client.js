/**
 * Slack Real-Time Client Library
 *
 * A comprehensive JavaScript client for connecting to Slack real-time messages
 * via WebSocket with automatic reconnection, message queuing, and event handling.
 *
 * Usage:
 * const client = new SlackRealTimeClient({
 *   host: 'localhost:8000',
 *   secure: false,
 *   autoConnect: true,
 *   enableReconnection: true
 * });
 *
 * client.on('message', (data) => {
 *   console.log('New message:', data);
 * });
 *
 * client.connect();
 */

class SlackRealTimeClient extends EventTarget {
    constructor(options = {}) {
        super();

        // Configuration
        this.config = {
            host: options.host || window.location.host,
            secure: options.secure !== undefined ? options.secure : window.location.protocol === 'https:',
            messagePath: options.messagePath || '/ws/slack/messages/',
            notificationPath: options.notificationPath || '/ws/slack/notifications/',
            autoConnect: options.autoConnect || false,
            enableReconnection: options.enableReconnection !== false,
            reconnectInterval: options.reconnectInterval || 5000,
            maxReconnectAttempts: options.maxReconnectAttempts || 10,
            heartbeatInterval: options.heartbeatInterval || 30000,
            enableMessageQueue: options.enableMessageQueue !== false,
            maxQueueSize: options.maxQueueSize || 1000,
            debug: options.debug || false
        };

        // State
        this.messageSocket = null;
        this.notificationSocket = null;
        this.isConnected = false;
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.connectionStartTime = null;
        this.messageQueue = [];
        this.subscriptions = new Set();
        this.messageCount = 0;
        this.errorCount = 0;
        this.latencyMeasurements = [];

        // Event handlers
        this.eventHandlers = new Map();

        // Performance metrics
        this.metrics = {
            connectTime: null,
            lastMessageTime: null,
            totalMessages: 0,
            totalErrors: 0,
            averageLatency: 0,
            connectionUptime: 0
        };

        // Auto-connect if requested
        if (this.config.autoConnect) {
            this.connect();
        }

        this.log('SlackRealTimeClient initialized', this.config);
    }

    /**
     * Connect to Slack real-time messages
     */
    async connect() {
        if (this.isConnected || this.isConnecting) {
            this.log('Already connected or connecting');
            return;
        }

        this.isConnecting = true;
        this.connectionStartTime = Date.now();

        try {
            await Promise.all([
                this.connectToMessages(),
                this.connectToNotifications()
            ]);

            this.isConnected = true;
            this.isConnecting = false;
            this.reconnectAttempts = 0;

            this.startHeartbeat();
            this.emit('connected', { timestamp: new Date().toISOString() });

            this.log('Connected to Slack real-time messaging');

        } catch (error) {
            this.isConnecting = false;
            this.handleConnectionError(error);
        }
    }

    /**
     * Connect to message WebSocket
     */
    connectToMessages() {
        return new Promise((resolve, reject) => {
            const protocol = this.config.secure ? 'wss:' : 'ws:';
            const url = `${protocol}//${this.config.host}${this.config.messagePath}`;

            this.messageSocket = new WebSocket(url);

            this.messageSocket.onopen = () => {
                this.log('Message WebSocket connected');
                resolve();
            };

            this.messageSocket.onmessage = (event) => {
                this.handleMessage(event);
            };

            this.messageSocket.onclose = (event) => {
                this.log('Message WebSocket closed', event);
                this.handleDisconnection('message_socket_closed');
            };

            this.messageSocket.onerror = (error) => {
                this.log('Message WebSocket error', error);
                reject(error);
            };
        });
    }

    /**
     * Connect to notification WebSocket
     */
    connectToNotifications() {
        return new Promise((resolve, reject) => {
            const protocol = this.config.secure ? 'wss:' : 'ws:';
            const url = `${protocol}//${this.config.host}${this.config.notificationPath}`;

            this.notificationSocket = new WebSocket(url);

            this.notificationSocket.onopen = () => {
                this.log('Notification WebSocket connected');
                resolve();
            };

            this.notificationSocket.onmessage = (event) => {
                this.handleNotification(event);
            };

            this.notificationSocket.onclose = (event) => {
                this.log('Notification WebSocket closed', event);
            };

            this.notificationSocket.onerror = (error) => {
                this.log('Notification WebSocket error', error);
                // Don't reject here - notifications are optional
                resolve();
            };
        });
    }

    /**
     * Disconnect from all WebSockets
     */
    disconnect() {
        this.isConnected = false;
        this.isConnecting = false;

        if (this.messageSocket) {
            this.messageSocket.close();
            this.messageSocket = null;
        }

        if (this.notificationSocket) {
            this.notificationSocket.close();
            this.notificationSocket = null;
        }

        this.stopHeartbeat();
        this.stopReconnection();

        this.emit('disconnected', { timestamp: new Date().toISOString() });
        this.log('Disconnected from Slack real-time messaging');
    }

    /**
     * Subscribe to specific workspace or channel
     */
    subscribe(options = {}) {
        if (!this.isConnected) {
            this.log('Cannot subscribe: not connected');
            return false;
        }

        const subscription = {
            type: 'subscribe',
            workspace_id: options.workspaceId,
            channel_id: options.channelId,
            timestamp: new Date().toISOString()
        };

        this.sendMessage(subscription);
        this.subscriptions.add(subscription);

        this.log('Subscribed to', subscription);
        return true;
    }

    /**
     * Send message to WebSocket
     */
    sendMessage(data) {
        if (!this.messageSocket || this.messageSocket.readyState !== WebSocket.OPEN) {
            if (this.config.enableMessageQueue) {
                this.queueMessage(data);
            }
            return false;
        }

        try {
            this.messageSocket.send(JSON.stringify(data));
            return true;
        } catch (error) {
            this.log('Error sending message', error);
            this.errorCount++;
            return false;
        }
    }

    /**
     * Queue message for later sending
     */
    queueMessage(data) {
        if (this.messageQueue.length >= this.config.maxQueueSize) {
            this.messageQueue.shift(); // Remove oldest message
        }

        this.messageQueue.push({
            data: data,
            timestamp: Date.now()
        });

        this.log('Message queued', data);
    }

    /**
     * Process queued messages
     */
    processMessageQueue() {
        while (this.messageQueue.length > 0) {
            const queuedMessage = this.messageQueue.shift();
            this.sendMessage(queuedMessage.data);
        }
        this.log('Processed message queue');
    }

    /**
     * Handle incoming messages
     */
    handleMessage(event) {
        try {
            const data = JSON.parse(event.data);
            const receiveTime = Date.now();

            // Calculate latency if available
            if (data.message && data.message.processing_time) {
                const latency = receiveTime - (data.message.processing_time * 1000);
                this.trackLatency(latency);
            }

            // Update metrics
            this.messageCount++;
            this.metrics.totalMessages++;
            this.metrics.lastMessageTime = receiveTime;

            // Emit specific event based on message type
            switch (data.type) {
                case 'slack_channel_message':
                    this.emit('channel_message', data.message);
                    break;
                case 'slack_dm':
                    this.emit('direct_message', data.message);
                    break;
                case 'typing_indicator':
                    this.emit('typing', data.data);
                    break;
                case 'slack_reaction':
                    this.emit('reaction', data.reaction);
                    break;
                case 'connection_established':
                    this.emit('connection_confirmed', data);
                    this.processMessageQueue();
                    break;
                default:
                    this.emit('message', data);
            }

            // Emit generic message event
            this.emit('raw_message', data);

            this.log('Message received', data.type);

        } catch (error) {
            this.log('Error parsing message', error);
            this.errorCount++;
            this.emit('error', { type: 'parse_error', error: error });
        }
    }

    /**
     * Handle incoming notifications
     */
    handleNotification(event) {
        try {
            const data = JSON.parse(event.data);
            this.emit('notification', data);
            this.log('Notification received', data.type);
        } catch (error) {
            this.log('Error parsing notification', error);
            this.emit('error', { type: 'notification_parse_error', error: error });
        }
    }

    /**
     * Handle connection errors
     */
    handleConnectionError(error) {
        this.errorCount++;
        this.metrics.totalErrors++;
        this.emit('error', { type: 'connection_error', error: error });

        if (this.config.enableReconnection && this.reconnectAttempts < this.config.maxReconnectAttempts) {
            this.scheduleReconnection();
        } else {
            this.emit('max_reconnect_attempts_reached', { attempts: this.reconnectAttempts });
        }
    }

    /**
     * Handle disconnection
     */
    handleDisconnection(reason) {
        this.isConnected = false;
        this.emit('disconnected', { reason: reason, timestamp: new Date().toISOString() });

        if (this.config.enableReconnection && this.reconnectAttempts < this.config.maxReconnectAttempts) {
            this.scheduleReconnection();
        }
    }

    /**
     * Schedule reconnection attempt
     */
    scheduleReconnection() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }

        this.reconnectAttempts++;
        const delay = this.config.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1);

        this.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);

        this.reconnectTimer = setTimeout(() => {
            this.emit('reconnecting', { attempt: this.reconnectAttempts });
            this.connect();
        }, delay);
    }

    /**
     * Stop reconnection attempts
     */
    stopReconnection() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        this.reconnectAttempts = 0;
    }

    /**
     * Start heartbeat to keep connection alive
     */
    startHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
        }

        this.heartbeatTimer = setInterval(() => {
            this.sendMessage({
                type: 'ping',
                timestamp: new Date().toISOString()
            });
        }, this.config.heartbeatInterval);
    }

    /**
     * Stop heartbeat
     */
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    /**
     * Track latency measurements
     */
    trackLatency(latency) {
        this.latencyMeasurements.push(latency);

        // Keep only last 100 measurements
        if (this.latencyMeasurements.length > 100) {
            this.latencyMeasurements = this.latencyMeasurements.slice(-100);
        }

        // Update average latency
        this.metrics.averageLatency = this.latencyMeasurements.reduce((a, b) => a + b, 0) / this.latencyMeasurements.length;
    }

    /**
     * Get current connection statistics
     */
    getStats() {
        return {
            isConnected: this.isConnected,
            messageCount: this.messageCount,
            errorCount: this.errorCount,
            reconnectAttempts: this.reconnectAttempts,
            uptime: this.connectionStartTime ? Date.now() - this.connectionStartTime : 0,
            averageLatency: this.metrics.averageLatency,
            lastMessageTime: this.metrics.lastMessageTime,
            queueSize: this.messageQueue.length,
            subscriptions: Array.from(this.subscriptions)
        };
    }

    /**
     * Event listener helpers
     */
    on(eventType, handler) {
        this.addEventListener(eventType, handler);
    }

    off(eventType, handler) {
        this.removeEventListener(eventType, handler);
    }

    emit(eventType, data) {
        this.dispatchEvent(new CustomEvent(eventType, { detail: data }));
    }

    /**
     * Logging helper
     */
    log(...args) {
        if (this.config.debug) {
            console.log('[SlackRealTimeClient]', ...args);
        }
    }

    /**
     * Test connection with latency measurement
     */
    async testConnection() {
        return new Promise((resolve) => {
            const startTime = performance.now();
            const testId = `test_${Date.now()}`;

            const onPong = (event) => {
                if (event.detail && event.detail.test_id === testId) {
                    const latency = performance.now() - startTime;
                    this.off('pong', onPong);
                    resolve({
                        success: true,
                        latency: latency,
                        timestamp: new Date().toISOString()
                    });
                }
            };

            this.on('pong', onPong);

            this.sendMessage({
                type: 'ping',
                test_id: testId,
                timestamp: new Date().toISOString()
            });

            // Timeout after 5 seconds
            setTimeout(() => {
                this.off('pong', onPong);
                resolve({
                    success: false,
                    error: 'Connection test timeout',
                    timestamp: new Date().toISOString()
                });
            }, 5000);
        });
    }
}

// Export for use in different environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SlackRealTimeClient;
} else if (typeof window !== 'undefined') {
    window.SlackRealTimeClient = SlackRealTimeClient;
}

// Usage examples and documentation
const SlackRealTimeClientExamples = {
    basic: `
// Basic usage
const client = new SlackRealTimeClient({
    host: 'localhost:8000',
    debug: true
});

client.on('channel_message', (message) => {
    console.log('Channel message:', message.text);
});

client.on('direct_message', (message) => {
    console.log('DM:', message.text);
});

client.connect();
`,

    withReconnection: `
// With automatic reconnection
const client = new SlackRealTimeClient({
    enableReconnection: true,
    maxReconnectAttempts: 5,
    reconnectInterval: 3000
});

client.on('reconnecting', (data) => {
    console.log('Reconnecting attempt:', data.attempt);
});

client.on('connected', () => {
    console.log('Connected!');
});
`,

    withSubscriptions: `
// With workspace/channel subscriptions
const client = new SlackRealTimeClient({ autoConnect: true });

client.on('connected', () => {
    // Subscribe to specific workspace
    client.subscribe({ workspaceId: 'T1234567890' });

    // Subscribe to specific channel
    client.subscribe({ channelId: 'C1234567890' });
});
`,

    withTesting: `
// With connection testing
const client = new SlackRealTimeClient({ debug: true });

await client.connect();

// Test connection
const result = await client.testConnection();
console.log('Connection test result:', result);

// Get statistics
const stats = client.getStats();
console.log('Connection stats:', stats);
`
};

if (typeof window !== 'undefined') {
    window.SlackRealTimeClientExamples = SlackRealTimeClientExamples;
}