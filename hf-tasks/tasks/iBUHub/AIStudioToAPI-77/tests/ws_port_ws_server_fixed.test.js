const assert = require("assert");
const WebSocket = require("ws");

const originalWsPort = process.env.WS_PORT;

const connectWebSocket = (url, timeoutMs = 2000) =>
    new Promise((resolve, reject) => {
        const ws = new WebSocket(url);
        const timer = setTimeout(() => {
            ws.terminate();
            reject(new Error("timeout"));
        }, timeoutMs);

        ws.on("open", () => {
            clearTimeout(timer);
            ws.close();
            resolve(true);
        });
        ws.on("error", err => {
            clearTimeout(timer);
            ws.close();
            reject(err);
        });
    });

(async () => {
    let system;
    try {
        process.env.WS_PORT = "45678";
        const ProxyServerSystem = require("../src/core/ProxyServerSystem");
        system = new ProxyServerSystem();

        await system._startWebSocketServer();

        assert.strictEqual(
            system.config.wsPort,
            9998,
            "WebSocket server should always start on port 9998"
        );

        await connectWebSocket("ws://127.0.0.1:9998");

        let failed = false;
        try {
            await connectWebSocket("ws://127.0.0.1:45678", 750);
        } catch (error) {
            failed = true;
        }

        assert.strictEqual(
            failed,
            true,
            "WebSocket server should not listen on the WS_PORT environment override"
        );
    } finally {
        if (system && system.wsServer) {
            system.wsServer.close();
        }
        if (originalWsPort === undefined) {
            delete process.env.WS_PORT;
        } else {
            process.env.WS_PORT = originalWsPort;
        }
    }
})().catch(err => {
    console.error(err);
    process.exit(1);
});
