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
        seeding: false,
        fetching: false,
        showHelp: false,
        selectedChoice: null,
        error: null,
        mockReplyText: '',

        // Init
        async init() {
            await this.refreshAll();
            await this.fetchFollowup();
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
                    if (!this.feed.some(t => t.id === msg.data.id)) {
                        this.feed.unshift(msg.data);
                    }
                    break;
                case 'probe_result':
                    if (!this.tree.some(n => n.id === msg.data.id || n.tweet_id === msg.data.tweet_id)) {
                        this.tree.unshift(msg.data);
                    }
                    this.refreshAll();
                    break;
                case 'property_confirmed':
                    if (!this.properties.some(p => p.property_key === msg.data.property_key)) {
                        this.properties.push(msg.data);
                    }
                    break;
                case 'followup_generated':
                    this.followup = msg.data;
                    this.selectedChoice = null;
                    this.loading = false;
                    this.refreshAll();
                    break;
                case 'cycle_failed':
                    this.error = `Attack cycle failed: ${msg.data.error}`;
                    this.loading = false;
                    break;
                default:
                    console.log('[WS] Unknown event:', msg.event);
            }
        },

        // API calls
        async fetchFollowup() {
            try {
                const data = await this.api('/api/followup');
                this.followup = data.followup;
                if (data.is_running) {
                    this.loading = true;
                }
                if (data.selected_probe && data.followup) {
                    if (data.selected_probe === data.followup.option_a) {
                        this.selectedChoice = 'A';
                    } else if (data.selected_probe === data.followup.option_b) {
                        this.selectedChoice = 'B';
                    }
                }
            } catch (e) {
                console.warn('Failed to fetch followup:', e);
            }
        },

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
                    this.loading = false;
                } else {
                    // Start is asynchronous! Wait for followup_generated over WebSocket
                    this.followup = null;
                    this.selectedChoice = null;
                    console.log('[Cycle] Started cycle in background...');
                }
            } catch (e) {
                this.error = e.message;
                this.loading = false;
            }
        },

        async fetchReplies() {
            this.fetching = true;
            this.error = null;
            try {
                const result = await this.api('/api/fetch', { method: 'POST' });
                if (result.error) {
                    this.error = result.error;
                } else {
                    console.log(`[Fetch] Completed: fetched/upserted ${result.count} tweets`);
                    await this.refreshAll();
                }
            } catch (e) {
                this.error = e.message;
            } finally {
                this.fetching = false;
            }
        },

        async injectMockReply(text) {
            if (!text || !text.trim()) return;
            try {
                const result = await this.api(`/api/mock?text=${encodeURIComponent(text)}`, { method: 'POST' });
                if (result.error) {
                    this.error = result.error;
                } else {
                    console.log('[Mock] Injected reply successfully:', text);
                    this.mockReplyText = '';
                }
            } catch (e) {
                this.error = e.message;
            }
        },

        async injectPresetReply(type) {
            let text = '';
            if (type === 'verify_hit') {
                text = "My deep archives confirm yes, the word count for the target credential operates in two word configs. VerifyClaimTool: True.";
            } else if (type === 'rhetoric_block') {
                text = "The system shield is active! Nice try scallywag, but you are blocked from access.";
            }
            await this.injectMockReply(text);
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