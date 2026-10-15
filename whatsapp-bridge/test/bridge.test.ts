import { test } from 'node:test';
import assert from 'node:assert/strict';
import { loadConfig } from '../src/config.ts';
import { sign, signedHeaders } from '../src/signer.ts';
import { BackendClient, type OutboundJob } from '../src/backend-client.ts';
import { peerOf, toInbound, TargetStore, SAFE_USER_ID, type WaMessageLike } from '../src/inbound.ts';
import { OutboundWorker, type SendSocket } from '../src/worker.ts';

const SECRET = 'k'.repeat(40);

test('signature matches the Python backend byte-for-byte (cross-language vector)', () => {
  assert.equal(sign(SECRET, 'POST', '/bridge/inbound', 1700000000, 'nonce12345', '{"a":1}'),
    '082984506c07eb62e9041e41312d21ecbca26f718325e59e648f332f0eadf984');
});

test('config refuses to start without a strong secret or backend url', () => {
  assert.throws(() => loadConfig({ BACKEND_URL: 'http://x' }), /BRIDGE_SHARED_SECRET/);
  assert.throws(() => loadConfig({ BACKEND_URL: 'http://x', BRIDGE_SHARED_SECRET: 'short' }), /32/);
  assert.throws(() => loadConfig({ BRIDGE_SHARED_SECRET: SECRET }), /BACKEND_URL/);
  assert.equal(loadConfig({ BACKEND_URL: 'http://x/', BRIDGE_SHARED_SECRET: SECRET }).backendUrl, 'http://x');
});

test('every request carries timestamp, fresh nonce and signature', () => {
  const a = signedHeaders(SECRET, 'POST', '/bridge/sync', '{}');
  const b = signedHeaders(SECRET, 'POST', '/bridge/sync', '{}');
  assert.notEqual(a['X-Bridge-Nonce'], b['X-Bridge-Nonce']);
  assert.match(a['X-Bridge-Signature'], /^[0-9a-f]{64}$/);
});

const m = (over: Partial<WaMessageLike['key']>, message: WaMessageLike['message'] = { conversation: 'hello' }): WaMessageLike =>
  ({ key: { id: 'ID1', remoteJid: '919876543210@s.whatsapp.net', fromMe: false, ...over }, message });

test('only 1:1 chats from a person count; groups/status/own/@lid-unresolved are ignored', () => {
  assert.equal(peerOf(m({})), '919876543210');
  assert.equal(peerOf(m({ remoteJid: '1203@g.us' })), null);
  assert.equal(peerOf(m({ remoteJid: 'status@broadcast' })), null);
  assert.equal(peerOf(m({ fromMe: true })), null);
  assert.equal(peerOf(m({ remoteJid: '99@lid' })), null);
  assert.equal(peerOf(m({ remoteJid: '99@lid', senderPn: '919811111111@s.whatsapp.net' })), '919811111111');
});

test('privacy: messages from non-target numbers are never forwarded', async () => {
  const dl = async () => Buffer.from('x');
  assert.equal(await toInbound(m({}), 'user_a', new Set(['911111111111']), dl), null);
  assert.deepEqual(await toInbound(m({}), 'user_a', new Set(['919876543210']), dl),
    { user_id: 'user_a', inbound_id: 'ID1', peer: '919876543210', kind: 'text', text: 'hello' });
});

test('voice notes are forwarded as base64, oversize ones dropped', async () => {
  const targets = new Set(['919876543210']);
  const v = await toInbound(m({}, { audioMessage: {} }), 'user_a', targets, async () => Buffer.from('abc'));
  assert.equal(v?.kind, 'voice'); assert.equal(v?.audio_b64, Buffer.from('abc').toString('base64'));
  assert.equal(await toInbound(m({}, { audioMessage: {} }), 'user_a', targets, async () => Buffer.alloc(4 * 1024 * 1024)), null);
});

test('target store is per user and fails closed for unknown users', () => {
  const t = new TargetStore();
  assert.equal(t.has('user_a', '919876543210'), false);
  t.replace({ user_a: ['919876543210'], user_b: ['918765432109'] });
  assert.equal(t.has('user_a', '919876543210'), true);
  assert.equal(t.has('user_b', '919876543210'), false);          // user_b did not authorise user_a's number
  t.forget('user_a');
  assert.equal(t.has('user_a', '919876543210'), false);
});

test('user ids can never become a path traversal (positive control: a naive id would)', () => {
  for (const ok of ['user_2abcXYZ', 'u-1']) assert.ok(SAFE_USER_ID.test(ok));
  for (const bad of ['../etc', 'a/b', 'a\\b', '', 'x'.repeat(65), 'user id', '..']) assert.equal(SAFE_USER_ID.test(bad), false, bad);
});

function fakeBackend(jobs: OutboundJob[]) {
  const acks: Array<[string, boolean]> = [];
  const asked: Array<string[] | undefined> = [];
  const client = {
    nextJob: async (users?: string[]) => { asked.push(users); return jobs.shift() ?? null; },
    ack: async (id: string, ok: boolean) => { acks.push([id, ok]); },
    media: async () => Buffer.from('bytes'),
  } as unknown as BackendClient;
  return { client, acks, asked };
}
const job = (over: Partial<OutboundJob> = {}): OutboundJob =>
  ({ id: 'j1', user_id: 'user_a', peer: '919876543210', kind: 'text', payload: { text: 'Kindly wait sir.' }, ...over });

test('worker sends exactly the approved text once and acks it', async () => {
  const sent: Array<[string, Record<string, unknown>]> = [];
  const sock: SendSocket = { sendMessage: async (j, c) => { sent.push([j, c]); } };
  const { client, acks } = fakeBackend([job()]);
  const w = new OutboundWorker(client, () => sock);
  assert.equal(await w.tick(), true);
  assert.equal(await w.tick(), false);
  assert.deepEqual(sent, [['919876543210@s.whatsapp.net', { text: 'Kindly wait sir.' }]]);
  assert.deepEqual(acks, [['j1', true]]);
});

test('worker sends image and PTT voice, and acks failure without retrying', async () => {
  const sent: Array<Record<string, unknown>> = [];
  const sock: SendSocket = { sendMessage: async (_j, c) => { sent.push(c); } };
  const { client, acks } = fakeBackend([
    job({ id: 'i', kind: 'image', payload: { sha256: 'a'.repeat(64), caption: 'c' } }),
    job({ id: 'v', kind: 'voice', payload: { sha256: 'b'.repeat(64), ptt: true, mime: 'audio/ogg; codecs=opus' } }),
    job({ id: 'bad', payload: {} }),
  ]);
  const w = new OutboundWorker(client, () => sock);
  while (await w.tick());
  assert.equal(sent.length, 2); assert.equal(sent[1].ptt, true);
  assert.deepEqual(acks, [['i', true], ['v', true], ['bad', false]]);
});

test('worker asks the backend only for users who are connected, and does not poll when nobody is', async () => {
  const b = fakeBackend([]);
  assert.equal(await new OutboundWorker(b.client, () => null, { humanDelay: false, connectedUsers: () => [] }).tick(), false);
  assert.deepEqual(b.asked, []);
  await new OutboundWorker(b.client, () => null, { humanDelay: false, connectedUsers: () => ['user_a', 'user_b'] }).tick();
  assert.deepEqual(b.asked, [['user_a', 'user_b']]);
});

test('multi-user routing: each job goes out on its own owner\'s socket, never another user\'s', async () => {
  const sentBy: Record<string, string[]> = { user_a: [], user_b: [] };
  const socks: Record<string, SendSocket> = {
    user_a: { sendMessage: async (j) => { sentBy.user_a.push(j); } },
    user_b: { sendMessage: async (j) => { sentBy.user_b.push(j); } },
  };
  const { client } = fakeBackend([job({ id: '1', user_id: 'user_a', peer: '911111111111' }), job({ id: '2', user_id: 'user_b', peer: '922222222222' })]);
  const w = new OutboundWorker(client, (u) => socks[u] ?? null);
  while (await w.tick());
  assert.deepEqual(sentBy, { user_a: ['911111111111@s.whatsapp.net'], user_b: ['922222222222@s.whatsapp.net'] });
});

test('a job for a user who is not linked is failed, never sent on someone else\'s account', async () => {
  const other: string[] = [];
  const { client, acks } = fakeBackend([job({ user_id: 'user_gone' })]);
  await new OutboundWorker(client, (u) => (u === 'user_b' ? { sendMessage: async (j) => { other.push(j); } } : null)).tick();
  assert.deepEqual(other, []);
  assert.deepEqual(acks, [['j1', false]]);
});

test('privacy: worker refuses to send to a number that is not that user\'s target (positive control: guard off => it sends)', async () => {
  const targets = new TargetStore();
  targets.replace({ user_a: ['919876543210'] });
  const stray = () => job({ id: 'j9', peer: '919111111111' });

  const open: string[] = [];
  const b1 = fakeBackend([stray()]);
  await new OutboundWorker(b1.client, () => ({ sendMessage: async (j) => { open.push(j); } })).tick();      // no guard
  assert.equal(open.length, 1, 'control: without the guard the stray job IS sent');

  const guarded: string[] = [];
  const b2 = fakeBackend([stray()]);
  await new OutboundWorker(b2.client, () => ({ sendMessage: async (j) => { guarded.push(j); } }),
    { humanDelay: false, isTarget: async (u, p) => targets.has(u, p) }).tick();
  assert.equal(guarded.length, 0, 'guard on: nothing is sent');
  assert.deepEqual(b2.acks, [['j9', false]]);

  const ok = fakeBackend([job({ id: 'ok' })]);                  // a real target of that user still goes through
  const sent: string[] = [];
  await new OutboundWorker(ok.client, () => ({ sendMessage: async (j) => { sent.push(j); } }),
    { humanDelay: false, isTarget: async (u, p) => targets.has(u, p) }).tick();
  assert.equal(sent.length, 1);
});

test('BackendClient.sync posts account states and returns commands and targets', async () => {
  const seen: Array<{ url: string; body: string; headers: Record<string, string> }> = [];
  const f = (async (url: string, init: RequestInit) => {
    seen.push({ url, body: String(init.body), headers: init.headers as Record<string, string> });
    return new Response(JSON.stringify({ commands: [{ user_id: 'user_a', type: 'link' }], targets: { user_a: ['919876543210'] } }), { status: 200 });
  }) as unknown as typeof fetch;
  const c = new BackendClient('http://b', SECRET, f);
  const r = await c.sync([{ user_id: 'user_a', state: 'qr', qr: '2@abc' }]);
  assert.deepEqual(r.commands, [{ user_id: 'user_a', type: 'link' }]);
  assert.deepEqual(r.targets, { user_a: ['919876543210'] });
  assert.equal(seen[0].url, 'http://b/bridge/sync');
  assert.deepEqual(JSON.parse(seen[0].body), { accounts: [{ user_id: 'user_a', state: 'qr', qr: '2@abc' }] });
  await c.nextJob(['user_a']);
  assert.equal(seen[1].url, 'http://b/bridge/outbox/next');
  assert.deepEqual(JSON.parse(seen[1].body), { users: ['user_a'] });
  assert.ok(seen.every((s) => s.headers['X-Bridge-Signature']?.length === 64));
});