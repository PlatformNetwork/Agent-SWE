const assert = require("assert");
const ConfigLoader = require("../src/utils/ConfigLoader");

const originalWsPort = process.env.WS_PORT;

try {
    process.env.WS_PORT = "7890";

    const logger = {
        info: () => {},
        warn: () => {},
        error: () => {},
    };

    const loader = new ConfigLoader(logger);
    const config = loader.loadConfiguration();

    assert.strictEqual(
        config.wsPort,
        9998,
        "ConfigLoader should ignore WS_PORT and keep the fixed websocket port"
    );
} finally {
    if (originalWsPort === undefined) {
        delete process.env.WS_PORT;
    } else {
        process.env.WS_PORT = originalWsPort;
    }
}
