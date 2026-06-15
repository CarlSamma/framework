/**
 * TAP Framework Dashboard — Alpine.js Components
 * Real-time WebSocket updates, API calls, state management.
 */

document.addEventListener('alpine:init', () => {
    Alpine.data('tapDashboard', () => ({
        // State
        feed: [],
        tree: [],
        properties: [],
        dpa: null,
        stats: {},
        entropy: {},
        followup: null,
        ws: null,
        connected: false,
        loading: false,
        showHelp: false,
        selectedChoice: null,

        // Init
        async init() {
            await this.refreshAll();
            this.connectWebSocket();
            // Auto-refresh every 30 seconds
            setInterval(() => this.refreshAll(), 30000);
        },

        // WebSocket
        connectWebSocket() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.ws = new WebSocket(`${protocol}//${location.host}/ws/live`);

            this.ws.onopen = () => {
                this.connected = true;
                console.log('[WS] Connected');
            };

            this.ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    this.handleEvent(msg);
                } catch (e) {
                    console.warn('[WS] Parse error:', e);
                }
            };

            this.ws.onclose = () => {
                this.connected = false;
                console.log('[WS] Disconnected, reconnecting in 5s...');
                setTimeout(() => this.connectWebSocket(), 5000);
            };

            this.ws.onerror = (e) => {
                console.error('[WS] Error:', e);
            };

            // Ping to keep alive
            setInterval(() => {
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send('ping');
                }
            }, 25000);
        },

        handleEvent(msg) {
            switch (msg.event) {
                case 'new_tweet':
                    this.feed.unshift(msg.data);
                    break;
                case 'probe_result':
                    this.tree.unshift(msg.data);
                    break;
                case 'property_confirmed':
                    this.properties.push(msg.data);
                    break;
                case 'followup_generated':
                    this.followup = msg.data;
                    break;
                default:
                    console.log('[WS] Unknown event:', msg.event);
            }
        },

        // API calls
        async refreshAll() {
            try {
                const [feed, tree, props, dpa, stats, entropy] = await Promise.all([
                    this.api('/api/feed?limit=30'),
                    this.api('/api/tree?limit=20'),
                    this.api('/api/properties'),
                    this.api('/api/dpa'),
                    this.api('/api/stats'),
                    this.api('/api/entropy'),
                ]);
                this.feed = feed;
                this.tree = tree;
                this.properties = props;
                this.dpa = dpa;
                this.stats = stats;
                this.entropy = entropy;
            } catch (e) {
                this.error = e.message;
            }
        },

        async api(url, options = {}) {
            const res = await fetch(url, options);
            if (!res.ok) throw new Error(`API error: ${res.status}`);
            return res.json();
        },

        async selectOption(choice) {
            this.loading = true;
            try {
                const result = await this.api(`/api/select?choice=${choice}`, { method: 'POST' });
                if (result.error) {
                    this.error = result.error;
                } else {
                    this.selectedChoice = choice;
                }
            } catch (e) {
                this.error = e.message;
            } finally {
                this.loading = false;
            }
        },

        async runCycle() {
            this.loading = true;
            this.error = null;
            try {
                const result = await this.api('/api/post', { method: 'POST' });
                if (result.error) {
                    this.error = result.error;
                } else {
                    this.followup = result.followup;
                    this.selectedChoice = null;
                    await this.refreshAll();
                }
            } catch (e) {
                this.error = e.message;
            } finally {
                this.loading = false;
            }
        },

        // Helpers
        scoreClass(score) {
            if (!score) return '';
            if (score >= 6) return 'high';
            if (score >= 3) return 'mid';
            return 'low';
        },

        entropyPercent() {
            const maxEntropy = 20;
            const current = this.entropy?.entropy || 0;
            return Math.min((current / maxEntropy) * 100, 100);
        },

        formatTime(ts) {
            if (!ts) return '';
            const d = new Date(ts);
            return d.toLocaleTimeString();
        },
    }));
});