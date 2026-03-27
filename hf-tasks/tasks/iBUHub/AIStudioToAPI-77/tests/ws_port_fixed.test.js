const assert = require("assert");
const WebSocket = require("ws");
const ProxyServerSystem = require("../src/core/ProxyServerSystem");

const originalWsPort = process.env.WS_PORT;
const originalPort = process.env.PORT;

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
        process.env.WS_PORT = "12345";
        process.env.PORT = "9012";

        system = new ProxyServerSystem();
        await system._startWebSocketServer();

        assert.strictEqual(
            system.config.wsPort,
            9998,
            "WS_PORT environment variable should be ignored and always use port 9998"
        );
        assert.strictEqual(
            system.config.httpPort,
            9012,
            "PORT environment variable should still be honored for HTTP server port"
        );

        await connectWebSocket("ws://127.0.0.1:9998");

        let failed = false;
        try {
            await connectWebSocket("ws://127.0.0.1:12345", 750);
        } catch (error) {
            failed = true;
        }
        assert.strictEqual(
            failed,
            true,
            "WebSocket server should not listen on overridden WS_PORT"
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
        if (originalPort === undefined) {
            delete process.env.PORT;
        } else {
            process.env.PORT = originalPort;
        }
    }
})().catch(err => {
    console.error(err);
    process.exit(1);
});
