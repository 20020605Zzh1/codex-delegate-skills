// Convert a closed log with the installed Harness storage implementation.
const fs = require("node:fs");
const path = require("node:path");
const assert = require("node:assert/strict");
const zlib = require("node:zlib");

async function main() {
  const [sourceRoot, sessionId, destinationRoot] = process.argv.slice(2);
  if (!sourceRoot || !sessionId || !destinationRoot) {
    throw new Error("Expected source session store, session id and empty destination store");
  }
  const packages = path.join(path.dirname(process.execPath), "resources",
    "app.asar", "dsh", "node_modules", "@deepseek-ai");
  const { Context } = require(path.join(packages, "cordis", "lib", "index.js"));
  const { default: Persistence } = require(path.join(packages, "dsh-session-persistence-jsonl", "lib", "index.js"));
  const contexts = [new Context(), new Context()];
  let original, converted;
  try {
    const source = new Persistence(contexts[0], { root: sourceRoot, compression: "none" });
    original = await source.open(sessionId, "read");
    const snapshot = await original.read();
    const destination = new Persistence(contexts[1], { root: destinationRoot, compression: "zstd" });
    const outputPath = destination.locate(original.header).path;
    if (!fs.existsSync(outputPath)) {
      converted = await destination.create(original.header, { inheritedEventCount: original.inheritedEventCount });
      await converted.append(snapshot.events);
      await converted.flush();
      await converted.close();
      converted = undefined;
    }
    // Public Node API reads each frame independently. Verify every row, not
    // only the first frame (which contains just the Session header).
    let encoded = fs.readFileSync(outputPath);
    const decoded = [];
    while (encoded.length) {
      const frame = zlib.zstdDecompressSync(encoded, { info: true });
      if (!frame.engine.bytesWritten) throw new Error("Zstandard decoder made no progress");
      decoded.push(frame.buffer);
      encoded = encoded.subarray(frame.engine.bytesWritten);
    }
    const decompressed = Buffer.concat(decoded);
    const rawSource = fs.readFileSync(source.locate(original.header).path);
    assert.deepEqual(decompressed, rawSource);
    console.log(JSON.stringify({ status: "COMPRESSED_ALL_ROWS_READBACK_PASS", sessionId,
      eventCount: snapshot.events.length, sourceRoot, destination: outputPath,
      frameCount: decoded.length, decompressedBytes: decompressed.length, byteIdentical: true }));
  } finally {
    await converted?.close();
    await original?.close();
    for (const context of contexts) await context.fiber.dispose();
  }
}
// The Harness decompression worker is unref'ed; keep this short command alive
// until verification and handle cleanup have actually completed.
const keepAlive = setInterval(() => {}, 1000);
main().catch(error => { console.error(error.message); process.exitCode = 1; })
  .finally(() => clearInterval(keepAlive));
