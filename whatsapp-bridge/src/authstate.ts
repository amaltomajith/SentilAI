import { BufferJSON, initAuthCreds, proto, type AuthenticationCreds, type AuthenticationState, type SignalDataTypeMap } from '@whiskeysockets/baileys';

/** The two calls the auth store needs from the backend (implemented by BackendClient, faked in tests). */
export interface AuthBackend {
  authGet(userId: string, names: string[]): Promise<Record<string, string | null>>;
  authSet(userId: string, items: Record<string, string | null>): Promise<void>;
}

const fix = (type: string, id: string) => `${type}-${id}`.replace(/\//g, '__').replace(/:/g, '-');

/**
 * Baileys auth state kept in the backend's encrypted blob table instead of a local folder, so a host with a wiped disk
 * (free tiers) reconnects after a restart without a new QR code. Same shape as Baileys' useMultiFileAuthState.
 */
export async function useBackendAuthState(userId: string, backend: AuthBackend): Promise<{ state: AuthenticationState; saveCreds: () => Promise<void> }> {
  const cache = new Map<string, string | null>();
  const rawCreds = (await backend.authGet(userId, ['creds'])).creds;
  const creds: AuthenticationCreds = rawCreds ? JSON.parse(rawCreds, BufferJSON.reviver) : initAuthCreds();

  return {
    state: {
      creds,
      keys: {
        get: async <T extends keyof SignalDataTypeMap>(type: T, ids: string[]) => {
          const missing = ids.filter((id) => !cache.has(fix(type, id)));
          if (missing.length) {
            const got = await backend.authGet(userId, missing.map((id) => fix(type, id)));
            for (const id of missing) cache.set(fix(type, id), got[fix(type, id)] ?? null);
          }
          const data: { [id: string]: SignalDataTypeMap[T] } = {};
          for (const id of ids) {
            const raw = cache.get(fix(type, id));
            if (!raw) continue;
            let value = JSON.parse(raw, BufferJSON.reviver);
            if (type === 'app-state-sync-key' && value) value = proto.Message.AppStateSyncKeyData.fromObject(value);
            data[id] = value;
          }
          return data;
        },
        set: async (data) => {
          const items: Record<string, string | null> = {};
          for (const [type, entries] of Object.entries(data)) {
            for (const [id, value] of Object.entries(entries ?? {})) {
              const s = value ? JSON.stringify(value, BufferJSON.replacer) : null;
              items[fix(type, id)] = s;
              cache.set(fix(type, id), s);
            }
          }
          if (Object.keys(items).length) await backend.authSet(userId, items);
        },
      },
    },
    saveCreds: async () => { await backend.authSet(userId, { creds: JSON.stringify(creds, BufferJSON.replacer) }); },
  };
}