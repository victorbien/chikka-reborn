// Serves a throwaway in-process PostgreSQL (PGlite) with the Supabase stub and all migrations
// applied over the PostgreSQL wire protocol, so the backend and its tests can connect with asyncpg.
// Nothing is persisted and nothing leaves the machine.
//
//   node serve-db.mjs [--port=54329]
//
// Prints "READY postgresql://postgres:postgres@127.0.0.1:<port>/postgres" when listening.
//
// pglite-socket does not close the socket when a client sends Terminate ('X'), so graceful
// client disconnects (asyncpg close(), SQLAlchemy pool dispose) wait forever. A small TCP proxy
// in front of it ends the connection when it sees a Terminate message.
import net from 'node:net';
import { PGLiteSocketServer } from '@electric-sql/pglite-socket';
import { buildDatabase } from './run-db.mjs';

const portArg = process.argv.find((a) => a.startsWith('--port='));
const port = portArg ? Number(portArg.slice('--port='.length)) : 54329;
const innerPort = port + 1;

const TERMINATE = Buffer.from([0x58, 0x00, 0x00, 0x00, 0x04]);

const db = await buildDatabase({ quiet: true });
const inner = new PGLiteSocketServer({ db, port: innerPort, host: '127.0.0.1', maxConnections: 16 });
await inner.start();

const proxy = net.createServer((client) => {
  const upstream = net.connect(innerPort, '127.0.0.1');
  const closeBoth = () => {
    client.destroy();
    upstream.destroy();
  };
  client.on('data', (chunk) => {
    // asyncpg and libpq send Terminate as its own final write.
    if (chunk.length >= 5 && chunk.subarray(chunk.length - 5).equals(TERMINATE)) {
      if (chunk.length > 5) upstream.write(chunk.subarray(0, chunk.length - 5));
      setTimeout(closeBoth, 10);
      return;
    }
    upstream.write(chunk);
  });
  upstream.on('data', (chunk) => client.write(chunk));
  client.on('error', closeBoth);
  upstream.on('error', closeBoth);
  client.on('close', () => upstream.destroy());
  upstream.on('close', () => client.destroy());
});

await new Promise((resolve) => proxy.listen(port, '127.0.0.1', resolve));
console.log(`READY postgresql://postgres:postgres@127.0.0.1:${port}/postgres`);

const stop = async () => {
  proxy.close();
  await inner.stop();
  await db.close();
  process.exit(0);
};
process.on('SIGINT', stop);
process.on('SIGTERM', stop);
